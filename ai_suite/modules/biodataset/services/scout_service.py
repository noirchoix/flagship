from __future__ import annotations
from typing import Any, Dict, List
import json
import requests
from urllib.parse import quote
from ai_suite.modules.biodataset.core.config import settings
from ai_suite.modules.biodataset.schemas.bio import ScoutRequest, EndpointPlan, PreviewResponse, ArtifactBundle, ScoutResponse
from ai_suite.modules.biodataset.services.ncbi_catalog import infer_domain, infer_id_type, match_candidates

class BioScoutService:
    def __init__(self):
        self.base = settings.ncbi_api_base.rstrip('/')

    def health(self) -> Dict[str, Any]:
        return {
            'ok': True,
            'service': 'biodataset_scout',
            'ncbi_base': self.base,
            'live_preview_enabled': bool(settings.allow_live_preview),
            'api_key_configured': bool(settings.ncbi_api_key),
        }

    def scout(self, req: ScoutRequest) -> ScoutResponse:
        domain = req.domain if req.domain != 'auto' else infer_domain(f'{req.objective} {req.organism} {req.identifier}')
        id_type = req.identifier_type if req.identifier_type != 'auto' else infer_id_type(req.identifier, req.objective)
        identifier = self._identifier(req, id_type)
        goal = self._goal(req)
        candidates = match_candidates(domain, goal, id_type)
        if not candidates:
            candidates = match_candidates(domain, 'metadata_report', 'auto')

        plans = [self._to_plan(row, identifier, req) for row in candidates]
        primary = plans[0] if plans else EndpointPlan(label='Taxon suggestion', method='GET', path=f'/taxonomy/taxon_suggest/{quote(identifier)}', reason='Fallback when identifiers are ambiguous.')
        preview = self._preview(primary, req.run_live_preview)
        expected = self._expected_outputs(plans, req)
        ingestion = self._ingestion_plan(domain, req)
        risks = self._risk_notes(req, primary)
        artifacts = self._artifacts(req, domain, id_type, identifier, plans, expected, ingestion, risks)
        title = self._title(domain, goal, identifier)
        summary = f'Plan NCBI Datasets acquisition for {domain} data using {primary.method} {primary.path}. Start with preview/metadata calls before any bulk download.'
        return ScoutResponse(title=title, summary=summary, endpoint_plan=plans, expected_outputs=expected, ingestion_plan=ingestion, risk_notes=risks, preview=preview, artifacts=artifacts)

    def _identifier(self, req: ScoutRequest, id_type: str) -> str:
        value = (req.identifier or req.organism or '').strip()
        if not value:
            return 'human' if 'human' in req.objective.lower() else '9606'
        return value

    def _goal(self, req: ScoutRequest) -> str:
        if req.output_goal == 'download_package' and not req.include_sequences:
            return 'download_summary'
        return req.output_goal

    def _to_plan(self, row: Dict[str, Any], identifier: str, req: ScoutRequest) -> EndpointPlan:
        path = row['path_template']
        taxon = (req.organism or req.identifier or '9606').strip()
        safe_identifier = quote(identifier, safe=',')
        path = path.replace('{identifier}', safe_identifier).replace('{taxon}', quote(taxon, safe=','))
        params: Dict[str, Any] = {}
        if settings.ncbi_api_key:
            params['api_key'] = '${NCBI_API_KEY}'
        safe_default = 'download' not in path or 'summary' in path
        return EndpointPlan(label=row['label'], method=row['method'], path=path, reason=row['reason'], parameters=params, body=None, safe_default=safe_default)

    def _preview(self, plan: EndpointPlan, requested: bool) -> PreviewResponse:
        if not requested:
            return PreviewResponse(attempted=False, ok=False, note='Live preview was not requested. The app generated a safe endpoint and ingestion plan only.')
        if not settings.allow_live_preview:
            return PreviewResponse(attempted=False, ok=False, note='Live preview is disabled by server configuration.')
        if not plan.safe_default:
            return PreviewResponse(attempted=False, ok=False, note='Live preview skipped because the selected endpoint may download a large package. Use a download_summary endpoint first.')
        try:
            headers = {'Accept': 'application/json'}
            params = {k: v for k, v in plan.parameters.items() if not str(v).startswith('${')}
            if settings.ncbi_api_key:
                params['api_key'] = settings.ncbi_api_key
            resp = requests.request(plan.method, self.base + plan.path, headers=headers, params=params, json=plan.body, timeout=settings.max_preview_seconds)
            sample: Any
            ctype = resp.headers.get('content-type', '')
            if 'json' in ctype:
                parsed = resp.json()
                sample = self._sample_json(parsed)
            else:
                sample = resp.text[:1200]
            return PreviewResponse(attempted=True, ok=resp.ok, status_code=resp.status_code, note='Preview request completed.', sample=sample)
        except Exception as exc:
            return PreviewResponse(attempted=True, ok=False, note=f'Preview failed: {exc}')

    def _sample_json(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._sample_json(v) for k, v in list(data.items())[:8]}
        if isinstance(data, list):
            return [self._sample_json(x) for x in data[:3]]
        return data

    def _expected_outputs(self, plans: List[EndpointPlan], req: ScoutRequest) -> List[str]:
        out = ['NCBI JSON metadata report', 'dataset_manifest.json', 'README_DATA.md', 'ncbi_fetch_plan.py']
        if req.include_sequences:
            out.extend(['sequence FASTA package', 'downloaded NCBI data package ZIP'])
        if req.include_annotation:
            out.extend(['annotation report metadata', 'GFF/GTF ingestion notes where available'])
        return list(dict.fromkeys(out))

    def _ingestion_plan(self, domain: str, req: ScoutRequest) -> List[str]:
        steps = [
            'Start with metadata or download_summary endpoint to validate identifiers and estimate scope.',
            'Persist raw JSON responses under data/raw/ncbi/ with date-stamped filenames.',
            'Normalize records to JSONL for auditability before tabular conversion.',
            'Load metadata JSONL into DuckDB tables for filtering, joins, and reproducible EDA.',
            'Store bulky sequence/annotation files outside SQLite; keep file paths and checksums in the manifest.',
        ]
        if domain in {'genome', 'virus', 'organelle'}:
            steps.append('For sequence packages, keep FASTA/GFF files in partitioned folders by taxon/accession and register them in dataset_manifest.json.')
        if domain == 'gene':
            steps.append('Split gene metadata, product reports, and sequence files into separate normalized tables keyed by GeneID/accession.')
        if req.prefer_cli:
            steps.append('Use the NCBI Datasets CLI for large downloads and the REST API for planning, previews, and metadata checks.')
        return steps

    def _risk_notes(self, req: ScoutRequest, plan: EndpointPlan) -> List[str]:
        notes = [
            'NCBI data is public, but downstream use should still record source, retrieval date, accession IDs, and citation details.',
            'Avoid bulk downloads until download_summary has been reviewed for package contents and expected size.',
            'Use an NCBI API key for higher throughput and responsible usage if running repeated requests.',
            'Pin retrieval parameters in the manifest so later results are reproducible even when records are revised.',
        ]
        if not plan.safe_default:
            notes.insert(1, 'The selected primary endpoint is a package download endpoint; treat it as a human-approved action, not a default preview call.')
        return notes

    def _artifacts(self, req: ScoutRequest, domain: str, id_type: str, identifier: str, plans: List[EndpointPlan], expected: List[str], ingestion: List[str], risks: List[str]) -> ArtifactBundle:
        manifest = {
            'name': self._slug(req.objective),
            'source': 'NCBI Datasets v2 REST API',
            'domain': domain,
            'identifier_type': id_type,
            'identifier': identifier,
            'objective': req.objective,
            'endpoint_plan': [p.model_dump() for p in plans],
            'expected_outputs': expected,
            'retrieval_policy': {'start_with_preview': True, 'bulk_download_requires_human_approval': True, 'store_raw_responses': True},
        }
        readme = self._readme(req, manifest, ingestion, risks)
        fetch_py = self._fetch_script(plans, manifest['name'])
        duckdb_sql = self._duckdb_sql(manifest['name'])
        checklist = self._checklist(risks)
        curl_md = self._curl_examples(plans)
        return ArtifactBundle(readme_data_md=readme, dataset_manifest_json=json.dumps(manifest, indent=2), ncbi_fetch_plan_py=fetch_py, duckdb_ingestion_sql=duckdb_sql, quality_checklist_md=checklist, curl_examples_md=curl_md)

    def _readme(self, req: ScoutRequest, manifest: Dict[str, Any], ingestion: List[str], risks: List[str]) -> str:
        endpoints = '\n'.join([f"- `{p['method']} {p['path']}` — {p['reason']}" for p in manifest['endpoint_plan']])
        steps = '\n'.join([f'{i+1}. {s}' for i, s in enumerate(ingestion)])
        risk_text = '\n'.join([f'- {r}' for r in risks])
        return f"""# README_DATA — {manifest['name']}

## Objective

{req.objective}

## Source

NCBI Datasets v2 REST API.

## Recommended endpoint plan

{endpoints}

## Acquisition policy

Start with metadata and download-summary calls. Do not run package download endpoints until a human confirms scope, file types, and expected storage impact.

## Ingestion plan

{steps}

## Risk and reproducibility notes

{risk_text}
"""

    def _fetch_script(self, plans: List[EndpointPlan], name: str) -> str:
        plan_json = json.dumps([p.model_dump() for p in plans], indent=2)
        return f'''from __future__ import annotations
import json
import os
from pathlib import Path
import requests

BASE_URL = os.getenv("NCBI_API_BASE", "https://api.ncbi.nlm.nih.gov/datasets/v2").rstrip("/")
API_KEY = os.getenv("NCBI_API_KEY", "")
OUT_DIR = Path("data/raw/ncbi/{name}")
OUT_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS = {plan_json}

def fetch_endpoint(endpoint: dict, index: int) -> None:
    if not endpoint.get("safe_default", True):
        print(f"SKIP bulk endpoint {{endpoint['method']}} {{endpoint['path']}}. Review download_summary first.")
        return
    params = {{}}
    if API_KEY:
        params["api_key"] = API_KEY
    response = requests.request(endpoint["method"], BASE_URL + endpoint["path"], params=params, json=endpoint.get("body"), timeout=60)
    response.raise_for_status()
    output = OUT_DIR / f"{{index:02d}}_{{endpoint['label'].lower().replace(' ', '_')}}.json"
    output.write_text(json.dumps(response.json(), indent=2), encoding="utf-8")
    print(f"saved {{output}}")

if __name__ == "__main__":
    for idx, endpoint in enumerate(ENDPOINTS, start=1):
        fetch_endpoint(endpoint, idx)
'''

    def _duckdb_sql(self, name: str) -> str:
        return f'''-- DuckDB ingestion sketch for {name}
INSTALL json;
LOAD json;

CREATE SCHEMA IF NOT EXISTS ncbi;

-- Replace the glob with the raw files produced by ncbi_fetch_plan.py
CREATE OR REPLACE TABLE ncbi.raw_json AS
SELECT filename, json AS payload
FROM read_json_objects('data/raw/ncbi/{name}/*.json', filename=true);

-- Keep extraction explicit per endpoint after inspecting payload shape.
-- Example pattern:
-- CREATE OR REPLACE TABLE ncbi.records AS
-- SELECT filename, payload->'reports' AS reports
-- FROM ncbi.raw_json;
'''

    def _checklist(self, risks: List[str]) -> str:
        base = [
            '[ ] Identifier validated through taxonomy/accession check where applicable.',
            '[ ] Metadata or download_summary reviewed before bulk download.',
            '[ ] Retrieval date, endpoint, parameters, and API version recorded.',
            '[ ] Raw JSON retained unchanged under data/raw/.',
            '[ ] Checksums recorded for downloaded packages and sequence files.',
            '[ ] License/source/citation notes included in downstream report.',
        ]
        return '# Data Quality Checklist\n\n' + '\n'.join(base + [f'[ ] {r}' for r in risks]) + '\n'

    def _curl_examples(self, plans: List[EndpointPlan]) -> str:
        lines = ['# NCBI REST examples', '']
        for p in plans:
            safe = ' # safe preview' if p.safe_default else ' # bulk download: confirm before running'
            lines.append(f"```bash\ncurl -L \"${{NCBI_API_BASE:-https://api.ncbi.nlm.nih.gov/datasets/v2}}{p.path}\"{safe}\n```\n")
        return '\n'.join(lines)

    def _title(self, domain: str, goal: str, identifier: str) -> str:
        return f'{domain.title()} {goal.replace("_", " ")} plan for {identifier}'

    def _slug(self, text: str) -> str:
        slug = ''.join(ch.lower() if ch.isalnum() else '_' for ch in text.strip())
        while '__' in slug:
            slug = slug.replace('__','_')
        return slug.strip('_')[:70] or 'ncbi_dataset_plan'

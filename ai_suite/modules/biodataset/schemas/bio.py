from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Domain = Literal['genome', 'gene', 'virus', 'taxonomy', 'biosample', 'organelle', 'auto']
OutputGoal = Literal['metadata_report', 'download_summary', 'download_package', 'annotation_report', 'sequence_report', 'product_report', 'taxonomy_report']
IdentifierType = Literal['taxon', 'accession', 'gene_id', 'gene_symbol', 'biosample', 'bioproject', 'assembly_name', 'auto']

class ScoutRequest(BaseModel):
    objective: str = Field(min_length=3, max_length=3000)
    domain: Domain = 'auto'
    identifier_type: IdentifierType = 'auto'
    identifier: str = Field(default='', max_length=500)
    organism: str = Field(default='', max_length=300)
    output_goal: OutputGoal = 'metadata_report'
    include_sequences: bool = False
    include_annotation: bool = True
    prefer_cli: bool = False
    run_live_preview: bool = False

class EndpointPlan(BaseModel):
    label: str
    method: Literal['GET','POST']
    path: str
    reason: str
    parameters: Dict[str, Any] = {}
    body: Optional[Dict[str, Any]] = None
    safe_default: bool = True

class ArtifactBundle(BaseModel):
    readme_data_md: str
    dataset_manifest_json: str
    ncbi_fetch_plan_py: str
    duckdb_ingestion_sql: str
    quality_checklist_md: str
    curl_examples_md: str

class PreviewResponse(BaseModel):
    attempted: bool
    ok: bool
    status_code: Optional[int] = None
    note: str
    sample: Any = None

class ScoutResponse(BaseModel):
    title: str
    summary: str
    endpoint_plan: List[EndpointPlan]
    expected_outputs: List[str]
    ingestion_plan: List[str]
    risk_notes: List[str]
    preview: PreviewResponse
    artifacts: ArtifactBundle

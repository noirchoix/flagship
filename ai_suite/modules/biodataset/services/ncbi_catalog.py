from __future__ import annotations
from typing import Any, Dict, List

CATALOG: List[Dict[str, Any]] = [
    {
        'domain': 'genome', 'goal': 'metadata_report', 'id_type': 'accession',
        'label': 'Genome assembly report by accession', 'method': 'GET',
        'path_template': '/genome/accession/{identifier}/dataset_report',
        'outputs': ['Genome assembly metadata JSON', 'assembly identifiers', 'organism metadata', 'annotation metadata'],
        'reason': 'Best first call when you already have one or more GCF/GCA assembly accessions.'
    },
    {
        'domain': 'genome', 'goal': 'download_summary', 'id_type': 'accession',
        'label': 'Genome package download summary by accession', 'method': 'GET',
        'path_template': '/genome/accession/{identifier}/download_summary',
        'outputs': ['Package preview', 'estimated files', 'available sequence/annotation assets'],
        'reason': 'Safe preview before requesting a potentially large genome data package.'
    },
    {
        'domain': 'genome', 'goal': 'download_package', 'id_type': 'accession',
        'label': 'Genome data package by accession', 'method': 'GET',
        'path_template': '/genome/accession/{identifier}/download',
        'outputs': ['NCBI genome data package ZIP', 'sequence FASTA', 'annotation assets', 'metadata'],
        'reason': 'Use only after reviewing the download summary and confirming file size/scope.'
    },
    {
        'domain': 'genome', 'goal': 'annotation_report', 'id_type': 'accession',
        'label': 'Genome annotation report by accession', 'method': 'GET',
        'path_template': '/genome/accession/{identifier}/annotation_report',
        'outputs': ['Annotation report JSON', 'gene/feature annotation metadata'],
        'reason': 'Use when the research need is focused on annotation metadata rather than full sequence packages.'
    },
    {
        'domain': 'genome', 'goal': 'sequence_report', 'id_type': 'accession',
        'label': 'Genome sequence report by accession', 'method': 'GET',
        'path_template': '/genome/accession/{identifier}/sequence_reports',
        'outputs': ['Sequence report JSON', 'sequence accessions', 'assembly sequence metadata'],
        'reason': 'Use to inspect genome sequence composition before downstream FASTA/GFF ingestion.'
    },
    {
        'domain': 'genome', 'goal': 'metadata_report', 'id_type': 'taxon',
        'label': 'Genome assembly report by taxon', 'method': 'GET',
        'path_template': '/genome/taxon/{identifier}/dataset_report',
        'outputs': ['Genome assemblies for a taxon', 'assembly summaries', 'organism metadata'],
        'reason': 'Best first call when starting from an organism name or taxonomic identifier.'
    },
    {
        'domain': 'gene', 'goal': 'metadata_report', 'id_type': 'gene_id',
        'label': 'Gene report by GeneID', 'method': 'GET',
        'path_template': '/gene/id/{identifier}/dataset_report',
        'outputs': ['Gene metadata JSON', 'locus information', 'organism metadata'],
        'reason': 'Best first call when you have NCBI GeneID values.'
    },
    {
        'domain': 'gene', 'goal': 'product_report', 'id_type': 'gene_id',
        'label': 'Gene product report by GeneID', 'method': 'GET',
        'path_template': '/gene/id/{identifier}/product_report',
        'outputs': ['Transcript/protein product metadata', 'accessions', 'product names'],
        'reason': 'Use for workflows that need transcript or protein products associated with genes.'
    },
    {
        'domain': 'gene', 'goal': 'download_summary', 'id_type': 'gene_id',
        'label': 'Gene package download summary by GeneID', 'method': 'GET',
        'path_template': '/gene/id/{identifier}/download_summary',
        'outputs': ['Gene package preview', 'sequence/product availability'],
        'reason': 'Safe preview before downloading gene sequence packages.'
    },
    {
        'domain': 'gene', 'goal': 'metadata_report', 'id_type': 'gene_symbol',
        'label': 'Gene report by symbol and taxon', 'method': 'GET',
        'path_template': '/gene/symbol/{identifier}/taxon/{taxon}/dataset_report',
        'outputs': ['Gene metadata for symbol within taxon', 'matched gene records'],
        'reason': 'Use when the user has a gene symbol and an organism/taxon context.'
    },
    {
        'domain': 'virus', 'goal': 'metadata_report', 'id_type': 'accession',
        'label': 'Virus data report by nucleotide accession', 'method': 'GET',
        'path_template': '/virus/accession/{identifier}/dataset_report',
        'outputs': ['Virus genome metadata JSON', 'nucleotide accession metadata'],
        'reason': 'Best first call for virus records when you already have accessions.'
    },
    {
        'domain': 'virus', 'goal': 'download_summary', 'id_type': 'taxon',
        'label': 'Virus genome package summary by taxon', 'method': 'GET',
        'path_template': '/virus/taxon/{identifier}/genome',
        'outputs': ['Virus genome package preview', 'available genome records'],
        'reason': 'Safe preview before virus genome package download.'
    },
    {
        'domain': 'taxonomy', 'goal': 'taxonomy_report', 'id_type': 'taxon',
        'label': 'Taxonomy data report by taxon', 'method': 'GET',
        'path_template': '/taxonomy/taxon/{identifier}/dataset_report',
        'outputs': ['Taxonomy metadata JSON', 'lineage and names'],
        'reason': 'Use to validate organism identity and taxonomic lineage before genome/gene acquisition.'
    },
    {
        'domain': 'taxonomy', 'goal': 'taxonomy_report', 'id_type': 'auto',
        'label': 'Taxon suggest by partial name', 'method': 'GET',
        'path_template': '/taxonomy/taxon_suggest/{identifier}',
        'outputs': ['Suggested taxonomy names and IDs'],
        'reason': 'Use when the input is an organism name rather than a confirmed taxon ID.'
    },
    {
        'domain': 'biosample', 'goal': 'metadata_report', 'id_type': 'biosample',
        'label': 'BioSample report by accession', 'method': 'GET',
        'path_template': '/biosample/accession/{identifier}/biosample_report',
        'outputs': ['BioSample metadata JSON', 'sample attributes'],
        'reason': 'Use when the workflow needs sample provenance and attributes.'
    },
    {
        'domain': 'organelle', 'goal': 'metadata_report', 'id_type': 'accession',
        'label': 'Organelle data report by accession', 'method': 'GET',
        'path_template': '/organelle/accessions/{identifier}/dataset_report',
        'outputs': ['Organelle genome metadata JSON'],
        'reason': 'Use for RefSeq organelle genome metadata by nucleotide accession.'
    },
]

def infer_domain(text: str) -> str:
    lower = text.lower()
    if any(x in lower for x in ['virus', 'viral', 'sars', 'covid', 'coronavirus']):
        return 'virus'
    if any(x in lower for x in ['gene', 'ortholog', 'protein', 'transcript', 'symbol']):
        return 'gene'
    if any(x in lower for x in ['taxonomy', 'taxon', 'lineage', 'organism name']):
        return 'taxonomy'
    if any(x in lower for x in ['biosample', 'sample metadata', 'sample attribute']):
        return 'biosample'
    if any(x in lower for x in ['mitochond', 'chloroplast', 'organelle']):
        return 'organelle'
    return 'genome'

def infer_id_type(identifier: str, objective: str) -> str:
    text = f'{identifier} {objective}'.lower()
    clean = identifier.strip()
    if clean.isdigit():
        if 'gene' in objective.lower() or len(clean) > 5:
            return 'gene_id'
        return 'taxon'
    if clean.upper().startswith(('GCF_', 'GCA_')):
        return 'accession'
    if clean.upper().startswith(('SAMN', 'SAME', 'SAMD')):
        return 'biosample'
    if any(x in text for x in ['symbol', 'gene symbol']):
        return 'gene_symbol'
    return 'auto'

def match_candidates(domain: str, goal: str, id_type: str) -> list[dict[str, Any]]:
    scored = []
    for row in CATALOG:
        score = 0
        if row['domain'] == domain: score += 4
        if row['goal'] == goal: score += 3
        if row['id_type'] == id_type: score += 3
        if row['id_type'] == 'auto': score += 1
        if goal == 'download_package' and row['goal'] == 'download_summary': score += 2
        scored.append((score, row))
    return [r for _, r in sorted(scored, key=lambda x: x[0], reverse=True)[:4] if _ > 0]

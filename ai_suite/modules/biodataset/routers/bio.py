from fastapi import APIRouter
from ai_suite.modules.biodataset.schemas.bio import ScoutRequest, ScoutResponse
from ai_suite.modules.biodataset.services.scout_service import BioScoutService

router = APIRouter(prefix='/api/v1/bio-scout', tags=['bio dataset scout'])
service = BioScoutService()

@router.get('/health')
def health():
    return service.health()

@router.post('/plan', response_model=ScoutResponse)
def plan(payload: ScoutRequest):
    return service.scout(payload)

@router.get('/domains')
def domains():
    return {
        'domains': ['genome', 'gene', 'virus', 'taxonomy', 'biosample', 'organelle'],
        'output_goals': ['metadata_report', 'download_summary', 'download_package', 'annotation_report', 'sequence_report', 'product_report', 'taxonomy_report'],
        'identifier_types': ['taxon', 'accession', 'gene_id', 'gene_symbol', 'biosample', 'bioproject', 'assembly_name', 'auto']
    }

from __future__ import annotations
from fastapi import APIRouter, UploadFile, File
from ai_suite.modules.shipgate.core.config import settings
from ai_suite.modules.shipgate.repositories.store import Store
from ai_suite.modules.shipgate.services.repo_service import RepoService
from ai_suite.modules.shipgate.services.audit_service import AuditService
from ai_suite.modules.shipgate.schemas.shipgate import HealthResponse, UploadedRepository, FileListResponse, AuditRequest, AuditResponse, SkillCard

store=Store(settings.db_path)
repo_service=RepoService(store)
audit_service=AuditService(store, repo_service)

router=APIRouter(prefix='/api/v1/shipgate', tags=['shipgate'])

@router.get('/health', response_model=HealthResponse)
def health():
    return audit_service.health()

@router.post('/upload', response_model=UploadedRepository)
async def upload(file: UploadFile = File(...)):
    return await repo_service.upload(file)

@router.get('/files/{session_id}', response_model=FileListResponse)
def files(session_id: str):
    fs=repo_service.list_files(session_id)
    return {'session_id':session_id, 'files':fs, 'default_targets':repo_service.default_targets(fs)}

@router.post('/audit', response_model=AuditResponse)
def audit(req: AuditRequest):
    return audit_service.run(req)

@router.get('/sessions')
def sessions():
    return {'sessions': store.sessions()}

@router.get('/skills', response_model=list[SkillCard])
def skills():
    return audit_service.skills()

@router.get('/memory/{session_id}')
def memory(session_id: str):
    return {'session_id':session_id, 'memory': store.memory(session_id)}

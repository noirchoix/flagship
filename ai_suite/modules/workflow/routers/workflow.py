from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from ai_suite.modules.workflow.repositories.store import Store
from ai_suite.modules.workflow.services.context_service import ContextService
from ai_suite.modules.workflow.services.workflow_service import WorkflowService
from ai_suite.modules.workflow.schemas.workflow import (
    FilesResponse,
    HealthResponse,
    NodeTypeCard,
    TemplateCard,
    UploadedContext,
    WorkflowRequest,
    WorkflowRunResponse,
)

router = APIRouter(prefix='/api/v1/workflows', tags=['ai workflow builder'])
store = Store()
context_service = ContextService(store)
workflow_service = WorkflowService(store, context_service)


def _http_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get('/health', response_model=HealthResponse)
def health():
    mode = workflow_service._llm_mode()
    return {
        'ok': True,
        'ai_enabled': mode != 'offline',
        'provider': mode,
        'sessions': store.count('sessions'),
        'workflows': store.count('workflows'),
    }


@router.get('/templates', response_model=list[TemplateCard])
def templates():
    return workflow_service.templates()


@router.get('/node-types', response_model=list[NodeTypeCard])
def node_types():
    return workflow_service.node_types()


@router.post('/upload', response_model=UploadedContext)
async def upload(file: UploadFile = File(...)):
    try:
        return await context_service.upload(file)
    except Exception as exc:
        raise _http_error(exc)


@router.get('/files/{session_id}', response_model=FilesResponse)
def files(session_id: str):
    try:
        return context_service.files(session_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/run', response_model=WorkflowRunResponse)
def run(payload: WorkflowRequest):
    try:
        return workflow_service.run(payload.model_dump())
    except Exception as exc:
        raise _http_error(exc)

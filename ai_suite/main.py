from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from ai_suite.core.config import settings
from ai_suite.core.memory import clear_module_cache, memory_snapshot

STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep startup light. Individual modules initialize their own SQLite/runtime folders lazily.
    yield
    try:
        from ai_suite.modules.research.api.llms.calls import close_deepseek_client
        await close_deepseek_client()
    except Exception:
        pass


app = FastAPI(
    title="Flagship AI Suite API",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[settings.request_id_header],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts_list)


@app.middleware("http")
async def request_context(request: Request, call_next: Callable):
    request_id = request.headers.get(settings.request_id_header) or uuid.uuid4().hex[:12]
    try:
        response = await call_next(request)
    except Exception as exc:
        response = JSONResponse(
            status_code=500,
            content={
                "detail": "Internal Server Error",
                "request_id": request_id,
                "error": str(exc) if settings.environment != "production" else None,
            },
        )
    response.headers[settings.request_id_header] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    origin = request.headers.get("origin")
    allowed = settings.cors_list
    if origin and ("*" in allowed or origin.rstrip("/") in allowed):
        response.headers.setdefault("Access-Control-Allow-Origin", origin)
        response.headers.setdefault("Access-Control-Allow-Credentials", "true")
        response.headers.setdefault("Vary", "Origin")
    return response


@app.get("/")
def root():
    return {"ok": True, "service": "Flagship AI Suite API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"ok": True, "service": "Flagship AI Suite API", "uptime_seconds": int(time.time() - STARTED_AT)}


@app.get("/readiness")
def readiness():
    return {
        "ok": True,
        "environment": settings.environment,
        "cors_origins": settings.cors_list,
        "modules": ["workflow", "biodataset", "research", "flavourdb", "shipgate"],
        "memory_safe_mode": settings.memory_safe_mode,
    }


@app.get("/api/v1/suite/status")
def suite_status():
    return {
        "ok": True,
        "service": "Flagship AI Suite API",
        "version": "1.1.0",
        "uptime_seconds": int(time.time() - STARTED_AT),
        "modules": {
            "workflow": "/api/v1/workflows",
            "biodataset": "/api/v1/bio-scout",
            "research": "/api",
            "flavourdb": "/api/scrape",
            "shipgate": "/api/v1/shipgate",
        },
        "memory": memory_snapshot() if settings.memory_debug else None,
    }


@app.get("/api/v1/suite/memory")
def memory():
    if not settings.memory_debug:
        return {"enabled": False, "hint": "Set AI_SUITE_MEMORY_DEBUG=true to expose RSS details."}
    return memory_snapshot()


@app.post("/api/v1/suite/clear-cache")
def clear_cache():
    return clear_module_cache()


# Module routers. Keep original route surfaces where frontends expect them.
from ai_suite.modules.workflow.routers.workflow import router as workflow_router
from ai_suite.modules.biodataset.routers.bio import router as biodataset_router
from ai_suite.modules.flavourdb.router import router as flavourdb_router
from ai_suite.modules.research.api.main import app as research_app
from ai_suite.modules.shipgate.routers.shipgate import router as shipgate_router

app.include_router(workflow_router)
app.include_router(biodataset_router)
app.include_router(flavourdb_router, prefix="/api")
app.include_router(shipgate_router)
app.mount("/research-app", research_app)  # direct mounted app for debugging, not used by frontend

# Re-expose only research API routes at their original root-level /api paths.
# This avoids duplicating the suite docs/openapi/root routes.
for route in list(research_app.router.routes):
    if getattr(route, "path", "").startswith("/api"):
        app.router.routes.append(route)

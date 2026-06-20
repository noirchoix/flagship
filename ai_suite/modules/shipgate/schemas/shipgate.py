from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

Severity = Literal['blocker', 'warning', 'suggestion', 'nit', 'pass']
Agent = Literal[
    'environment_auditor', 'build_auditor', 'deployment_auditor', 'security_auditor',
    'runtime_auditor', 'frontend_release_auditor', 'database_storage_auditor',
    'documentation_auditor', 'rag_readiness_auditor', 'launch_plan_writer'
]

class HealthResponse(BaseModel):
    ok: bool
    ai_enabled: bool
    provider: str
    audits: int
    version: str = '1.0.0'

class UploadedRepository(BaseModel):
    session_id: str
    repo_name: str
    file_count: int
    detected_stack: list[str]
    default_targets: list[str]

class RepoFile(BaseModel):
    path: str
    size: int
    kind: str

class FileListResponse(BaseModel):
    session_id: str
    files: list[RepoFile]
    default_targets: list[str]

class AuditRequest(BaseModel):
    session_id: str
    objective: str = 'Assess this repository for production launch readiness.'
    target_files: list[str] = Field(default_factory=list)
    deployment_target: str = 'auto'
    use_llm: bool = True

class Finding(BaseModel):
    severity: Severity
    agent: Agent
    title: str
    file: str | None = None
    evidence: str
    why_it_matters: str
    recommendation: str
    command: str | None = None

class EnvVariable(BaseModel):
    name: str
    exposure: Literal['public', 'server', 'unknown']
    required: bool
    source: str
    note: str

class CommandBlock(BaseModel):
    label: str
    command: str
    purpose: str

class LaunchPlan(BaseModel):
    deployment_target: str
    readiness: Literal['blocked', 'caution', 'ready']
    environment_matrix: list[EnvVariable]
    build_commands: list[CommandBlock]
    smoke_tests: list[CommandBlock]
    rollback_plan: list[str]
    predeploy_checklist: list[str]
    postdeploy_checklist: list[str]

class AgentTrace(BaseModel):
    agent: Agent
    status: Literal['pass', 'warn', 'blocked']
    findings: int
    summary: str

class AuditResponse(BaseModel):
    session_id: str
    score: int
    readiness: Literal['blocked', 'caution', 'ready']
    summary: str
    findings: list[Finding]
    launch_plan: LaunchPlan
    traces: list[AgentTrace]
    markdown_report: str

class SkillCard(BaseModel):
    name: str
    incorporated_as: str
    purpose: str

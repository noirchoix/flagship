from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

NodeType = Literal["trigger", "context", "agent", "tool", "condition", "approval", "test", "security", "report", "export"]
RunStatus = Literal["ready", "running", "needs_approval", "passed", "failed", "skipped"]
Severity = Literal["blocker", "warning", "suggestion", "nit", "pass"]
DecisionValue = Literal["yes", "no"]


class HealthResponse(BaseModel):
    ok: bool
    ai_enabled: bool
    provider: str
    sessions: int
    workflows: int


class TemplateCard(BaseModel):
    id: str
    name: str
    summary: str
    use_case: str
    nodes: list[str]


class NodeTypeCard(BaseModel):
    id: NodeType
    name: str
    description: str


class UploadedContext(BaseModel):
    session_id: str
    repo_name: str
    file_count: int
    default_targets: list[str]
    detected_stack: list[str]


class RepoFile(BaseModel):
    path: str
    kind: str
    size: int


class FilesResponse(BaseModel):
    session_id: str
    files: list[RepoFile]
    default_targets: list[str]


class HumanDecision(BaseModel):
    id: str
    question: str
    answer: DecisionValue


class WorkflowRequest(BaseModel):
    session_id: str | None = None
    objective: str = Field(min_length=5)
    template_ids: list[str] = Field(default_factory=list)
    target_files: list[str] = Field(default_factory=list)
    require_approval: bool = True
    use_llm: bool = True
    human_decisions: list[HumanDecision] = Field(default_factory=list)


class WorkflowNode(BaseModel):
    id: str
    type: NodeType
    title: str
    instruction: str
    input_from: list[str] = Field(default_factory=list)
    guardrail: str | None = None
    output_key: str
    implementation: list[str] = Field(default_factory=list)


class WorkflowEdge(BaseModel):
    source: str
    target: str
    label: str = "next"


class WorkflowDefinition(BaseModel):
    workflow_id: str
    title: str
    objective: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    export_json: str
    export_yaml: str


class RunTrace(BaseModel):
    node_id: str
    title: str
    status: RunStatus
    summary: str
    output: dict[str, Any] = Field(default_factory=dict)


class WorkflowFinding(BaseModel):
    severity: Severity
    title: str
    detail: str
    recommendation: str


class WorkflowArtifact(BaseModel):
    name: str
    kind: Literal["skill_md", "technical_schema", "n8n_readme", "zapier_make_readme", "mcp_contract", "runbook"]
    content: str


class WorkflowRunResponse(BaseModel):
    workflow: WorkflowDefinition
    traces: list[RunTrace]
    findings: list[WorkflowFinding]
    artifacts: list[WorkflowArtifact]
    report_markdown: str

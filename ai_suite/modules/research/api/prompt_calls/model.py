# -------------------------------------------------------------------
# Pydantic models for request/response
# -------------------------------------------------------------------
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


class TagIn(BaseModel):
    name: str
    value: str


class PromptBuilderRequest(BaseModel):
    tags: List[TagIn]
    pattern_names: List[str]


class PromptBuilderResponse(BaseModel):
    prompt_text: str
    score: float
    accepted: bool
    download_url: Optional[str]
    framework_blend: List[str] = []
    prompt_spec_md: str = ""
    scoring_rubric_yaml: str = ""
    prompt_eval_suite_json: str = ""
    failure_analysis_md: str = ""
    recommendations: List[str] = []
    structured_spec: Dict[str, Any] = {}


@dataclass
class PromptResult:
    prompt_text: str
    score: float
    accepted: bool
    file_path: str | None

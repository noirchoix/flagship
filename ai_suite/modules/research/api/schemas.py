# api/schemas.py

from pydantic import BaseModel
from typing import Optional, Literal

# Match your TaskType definition
TaskType = Literal[
    "short_summary",
    "long_summary",
    "research_summary",
    "math_proof",
    "prompt_draft",
]


class UploadResponse(BaseModel):
    document_id: int
    title: str
    filename: str


class GenerateRequest(BaseModel):
    document_id: int
    task_type: TaskType
    output_format: Optional[str] = None
    extra_instructions: Optional[str] = None


class GenerateResponse(BaseModel):
    job_id: int
    download_url: str
    result_preview: str

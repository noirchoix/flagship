from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from typing import Optional

# Local imports
from ai_suite.modules.research.api.db import get_db, Document, Job, init_db
from ai_suite.modules.research.api.schemas import UploadResponse, GenerateRequest, GenerateResponse
from ai_suite.modules.research.api.functions import (
    extract_text_from_pdf,
    extract_text_from_docx,
    write_txt,
    write_docx,
    write_latex_math_proof,
    write_latex_research_summary,
    compile_tex_to_pdf,
    retrieve_scholar_articles,
)
from ai_suite.modules.research.api.prompt_calls.prompt_patterns import PROMPT_OUTPUT_DIR
from ai_suite.modules.research.api.prompt_calls.advanced_builder import build_advanced_prompt

from ai_suite.modules.research.api.prompt_calls.model import TagIn, PromptBuilderRequest, PromptBuilderResponse



from ai_suite.modules.research.api.prompt_calls.prompt import build_prompt
from ai_suite.modules.research.api.llms.calls import call_deepseek

load_dotenv()


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")


# ------------------------------------------------------------
# FASTAPI APP
# ------------------------------------------------------------
app = FastAPI(title="Research Assistant Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize DB tables
init_db()


# ------------------------------------------------------------
# STATIC PATHS
# ------------------------------------------------------------
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = Path(os.getenv("RESEARCH_UPLOAD_DIR", "./data/research/uploads"))
OUTPUT_DIR = Path(os.getenv("RESEARCH_OUTPUT_DIR", "./data/research/outputs"))

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------

@app.post("/api/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a PDF or Word document, extract text, and store a DB record.

    The backend is normally started from the repository root as:
        python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8009

    Browser-uploaded Office files do not always provide a reliable MIME type,
    especially after GitHub/download/repackaging. Validate primarily by file
    extension and then let the extractor raise a clear error if the document is
    malformed.
    """
    original_name = file.filename or "uploaded_file"
    suffix = Path(original_name).suffix.lower()

    allowed_suffixes = {".pdf", ".docx", ".doc"}
    if suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=400,
            detail="Only PDF or Word documents are supported for research upload. Use .pdf, .docx, or .doc.",
        )

    file_path = UPLOAD_DIR / f"{datetime.utcnow().timestamp()}{suffix}"
    try:
        with file_path.open("wb") as f:
            f.write(await file.read())

        if suffix == ".pdf":
            title, text = extract_text_from_pdf(file_path)
        else:
            title, text = extract_text_from_docx(file_path)
    except Exception as exc:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not read uploaded document: {exc}")

    doc = Document(
        filename=original_name,
        title=title or original_name,
        content=text or "",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return UploadResponse(
        document_id=doc.id,
        title=doc.title,
        filename=doc.filename,
    )


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_task(payload: GenerateRequest, db: Session = Depends(get_db)):
    """
    Runs an LLM task (summary, proof, etc.) → creates file → DB job record.
    """
    doc = db.query(Document).filter(Document.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    task = payload.task_type
    output_format = (payload.output_format or "").lower()

    # Default output formats
    if task == "short_summary":
        output_format = "txt"
    elif task == "long_summary":
        output_format = "docx"
    elif task == "research_summary":
        if output_format not in ("docx", "pdf", ""):
            raise HTTPException(status_code=400, detail="Invalid research_summary format.")
        if not output_format:
            output_format = "docx"
    elif task == "math_proof":
        if output_format not in ("tex", "pdf", ""):
            raise HTTPException(status_code=400, detail="Invalid math_proof format.")
        if not output_format:
            output_format = "pdf"
    elif task == "prompt_draft":
        output_format = "txt"

    # Build prompt + call DeepSeek
    prompt = build_prompt(task, doc.title, doc.content, payload.extra_instructions)
    result_text = await call_deepseek(prompt)

    # Determine file prefix
    prefix = f"{datetime.utcnow().timestamp()}_{task}"

    # ------------------------------------------------------
    # Write file based on task
    # ------------------------------------------------------
    if task in ("short_summary", "prompt_draft"):
        file_path = write_txt(result_text, prefix)

    elif task == "long_summary":
        file_path = write_docx(result_text, prefix, doc.title)

    elif task == "research_summary":
        if output_format == "docx":
            file_path = write_docx(result_text, prefix, f"Research Summary: {doc.title}")
        else:
            # PDF via LaTeX
            tex_path = write_latex_research_summary(result_text, prefix, doc.title)
            ok, pdf_path = compile_tex_to_pdf(str(tex_path))
            if not ok:
                raise HTTPException(status_code=500, detail=f"LaTeX compile failed: {pdf_path}")
            file_path = Path(pdf_path)

    elif task == "math_proof":
        tex_path = write_latex_math_proof(result_text, prefix, doc.title)
        if output_format == "tex":
            file_path = tex_path
        else:
            ok, pdf_path = compile_tex_to_pdf(str(tex_path))
            if not ok:
                raise HTTPException(status_code=500, detail=f"LaTeX compile failed: {pdf_path}")
            file_path = Path(pdf_path)

    # Store job in DB
    job = Job(
        document_id=doc.id,
        task_type=task,
        output_format=output_format,
        prompt=prompt,
        result_text=result_text,
        file_path=str(file_path),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    preview = result_text[:1000]
    download_url = f"/api/jobs/{job.id}/download"

    return GenerateResponse(
        job_id=job.id,
        download_url=download_url,
        result_preview=preview,
    )


@app.get("/api/jobs/{job_id}/download")
async def download_job(job_id: int, db: Session = Depends(get_db)):
    """
    Download the generated output file (.txt, .docx, .tex, .pdf)
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    path = Path(job.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing.")

    media = "text/plain"
    if path.suffix == ".pdf":
        media = "application/pdf"
    elif path.suffix == ".docx":
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif path.suffix == ".tex":
        media = "application/x-tex"

    return FileResponse(path, media_type=media, filename=path.name)


@app.get("/api/related")
async def related_articles(
    query: str,
    start_year: int = 2020,
    end_year: int = datetime.utcnow().year,
    num: int = 5,
):
    """
    SerpAPI-based related article search (Google Scholar)
    """
    if not SERPAPI_API_KEY:
        raise HTTPException(status_code=500, detail="SERPAPI_API_KEY missing")

    try:
        articles = retrieve_scholar_articles(
            [query],
            date_window=(start_year, end_year),
            num_of_articles=num,
            api_key=SERPAPI_API_KEY,
            extra_params={"as_rr": 1},
        )
        return {"query": query, "articles": articles}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)



# TTS ROUTER
@app.post("/api/jobs/{job_id}/audio")
async def job_audio(job_id: int, db: Session = Depends(get_db)):
    # tts import
    from ai_suite.modules.research.api.tts import text_to_audio_eleven, AUDIO_DIR
    """
    Convert a generated job's result_text into a TTS MP3 and return it.

    Flow:
    - Look up the Job in the DB (must already exist from /api/generate).
    - If an audio file for this job already exists, reuse it (cheap replay).
    - Otherwise, call ElevenLabs via text_to_audio_eleven and save to disk.
    - Stream the MP3 back as a FileResponse.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # You can customize the naming pattern if you like
    filename = f"job_{job_id}_tts.mp3"
    out_path = AUDIO_DIR / filename

    # Simple caching: if we've already generated audio for this job, reuse it
    if not out_path.exists():
        await text_to_audio_eleven(job.result_text, str(out_path))

    return FileResponse(
        str(out_path),
        media_type="audio/mpeg",
        filename=filename,
    )

@app.get("/api/jobs/{job_id}/audio")
async def job_audio_stream(job_id: int, db: Session = Depends(get_db)):
    # tts import
    from ai_suite.modules.research.api.tts import text_to_audio_eleven, AUDIO_DIR
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    filename = f"job_{job_id}_tts.mp3"
    out_path = AUDIO_DIR / filename

    if not out_path.exists():
        await text_to_audio_eleven(job.result_text, str(out_path))

    return FileResponse(
        str(out_path),
        media_type="audio/mpeg",
        filename=filename,
    )

# -------------------------------------------------------------------
# POST /api/prompt-builder
# -------------------------------------------------------------------

@app.post("/api/prompt-builder", response_model=PromptBuilderResponse)
async def prompt_builder_endpoint(payload: PromptBuilderRequest) -> PromptBuilderResponse:
    if not payload.tags:
        raise HTTPException(status_code=400, detail="At least one tag is required")
    if not payload.pattern_names:
        raise HTTPException(status_code=400, detail="At least one pattern name is required")

    # Convert TagIn -> Tag dataclass
    tags = [TagIn(name=t.name.strip(), value=t.value.strip()) for t in payload.tags]

    try:
        result = await build_advanced_prompt(tags, payload.pattern_names)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # generic safety net
        raise HTTPException(status_code=500, detail=f"Prompt generation failed: {e}")

    download_url: Optional[str] = None
    if result.accepted and result.file_path:
        # We serve files via /api/prompt-files/{filename}
        filename = Path(result.file_path).name
        download_url = f"/api/prompt-files/{filename}"

    artifacts = getattr(result, "artifacts", {}) or {}

    return PromptBuilderResponse(
        prompt_text=result.prompt_text,
        score=result.score,
        accepted=result.accepted,
        download_url=download_url,
        framework_blend=getattr(result, "framework_blend", []) or [],
        prompt_spec_md=artifacts.get("prompt_spec_md", ""),
        scoring_rubric_yaml=artifacts.get("scoring_rubric_yaml", ""),
        prompt_eval_suite_json=artifacts.get("prompt_eval_suite_json", ""),
        failure_analysis_md=artifacts.get("failure_analysis_md", ""),
        recommendations=getattr(result, "recommendations", []) or [],
        structured_spec=artifacts.get("structured_spec", {}),
    )


# -------------------------------------------------------------------
# GET /api/prompt-files/{filename}
# -------------------------------------------------------------------

@app.get("/api/prompt-files/{filename}")
async def download_prompt_file(filename: str):
    """
    Download an accepted prompt as a .txt file.
    """
    # Basic sanitization: no path separators
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = PROMPT_OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path,
        media_type="text/plain",
        filename=filename,
    )

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "research-api",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }

@app.get("/health")
def health():
    return {"status": "ok"}

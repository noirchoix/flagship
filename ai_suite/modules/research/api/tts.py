# api/tts.py

import os
import re
import uuid
import tempfile
import subprocess
import shutil
from typing import List, Optional, Tuple, cast
from time import monotonic
from io import BytesIO
import asyncio
import logging
from pathlib import Path

import httpx
import PyPDF2
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tts")

# ==== CONFIG ====
ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY", "")
VOICE_ID = os.environ.get("ELEVEN_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
MODEL_ID = os.environ.get("ELEVEN_MODEL_ID", "eleven_multilingual_v2")
MAX_CHARS = int(os.environ.get("TTS_MAX_CHARS", "2000"))
CONCURRENCY = int(os.environ.get("TTS_CONCURRENCY", "4"))

BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

client = ElevenLabs(api_key=ELEVEN_API_KEY)

# ==== FFMPEG AUDIO MERGE UTILITIES ====

def _resolve_ffmpeg() -> Optional[str]:
    """Return an ffmpeg executable path without importing pydub/audioop."""
    candidates = [
        os.environ.get("FFMPEG_BINARY"),
        shutil.which("ffmpeg"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return shutil.which("ffmpeg")


def _concat_manifest_line(path: Path) -> str:
    """Build an ffmpeg concat-demuxer-safe file line for Windows/POSIX paths."""
    normalized = path.resolve().as_posix().replace("'", "'\\''")
    return f"file '{normalized}'\n"


def concat_mp3_bytes_with_ffmpeg(mp3_bytes_list: List[bytes], out_path: str) -> str:
    """
    Concatenate ElevenLabs MP3 byte chunks using ffmpeg directly.

    This intentionally avoids pydub because pydub imports audioop/pyaudioop,
    which breaks on Python 3.13 when audioop was removed from the stdlib.
    """
    if not mp3_bytes_list:
        raise ValueError("No MP3 chunks to merge.")

    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Single chunk: write directly. No ffmpeg required.
    if len(mp3_bytes_list) == 1:
        output.write_bytes(mp3_bytes_list[0])
        return str(output)

    ffmpeg = _resolve_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "Audio merge requires ffmpeg because pydub/audioop is no longer used. "
            "Install ffmpeg and ensure it is on PATH, or set FFMPEG_BINARY."
        )

    with tempfile.TemporaryDirectory(prefix="tts_mp3_concat_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        manifest = tmp_root / "chunks.txt"
        manifest_lines: List[str] = []

        for idx, blob in enumerate(mp3_bytes_list):
            chunk_path = tmp_root / f"chunk_{idx:04d}.mp3"
            chunk_path.write_bytes(blob)
            manifest_lines.append(_concat_manifest_line(chunk_path))

        manifest.write_text("".join(manifest_lines), encoding="utf-8")

        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(manifest),
            "-c", "copy",
            str(output),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "ffmpeg failed to merge TTS audio chunks. "
                f"stderr: {proc.stderr.strip() or proc.stdout.strip()}"
            )

    return str(output)


def concat_mp3_files_with_ffmpeg(file_paths: List[str], out_path: str) -> str:
    """Concatenate existing MP3 files using ffmpeg directly."""
    if not file_paths:
        raise ValueError("No MP3 files to merge.")

    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if len(file_paths) == 1:
        source = Path(file_paths[0])
        if source.resolve() != output.resolve():
            output.write_bytes(source.read_bytes())
        return str(output)

    ffmpeg = _resolve_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "Audio merge requires ffmpeg because pydub/audioop is no longer used. "
            "Install ffmpeg and ensure it is on PATH, or set FFMPEG_BINARY."
        )

    with tempfile.TemporaryDirectory(prefix="tts_file_concat_") as tmp_dir:
        manifest = Path(tmp_dir) / "chunks.txt"
        manifest.write_text(
            "".join(_concat_manifest_line(Path(p)) for p in file_paths),
            encoding="utf-8",
        )
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(manifest),
            "-c", "copy",
            str(output),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "ffmpeg failed to merge page audio files. "
                f"stderr: {proc.stderr.strip() or proc.stdout.strip()}"
            )

    return str(output)


# ==== TEXT UTILITIES (all O(n)) ====
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def cleanup_text(raw: str) -> str:
    if not raw:
        return ""
    txt = re.sub(r"-\s*\n\s*", "", raw)
    txt = re.sub(r"\s*\n\s*", " ", txt)
    txt = re.sub(r"\s{2,}", " ", txt)
    return txt.strip()


def sentences(text: str) -> List[str]:
    text = cleanup_text(text)
    if not text:
        return []
    sents = _SENTENCE_SPLIT.split(text)
    return [s.strip() for s in sents if s.strip()]


def pack_sentences(sents: List[str], limit: int) -> List[str]:
    """Greedy pack sentences into chunks <= limit chars (linear time)."""
    chunks: List[str] = []
    cur = ""
    for s in sents:
        if not cur:
            cur = s
        elif len(cur) + 1 + len(s) <= limit:
            cur += " " + s
        else:
            chunks.append(cur)
            cur = s
        if len(cur) > limit:
            words = cur.split()
            cur = ""
            for w in words:
                if not cur:
                    cur = w
                elif len(cur) + 1 + len(w) <= limit:
                    cur += " " + w
                else:
                    chunks.append(cur)
                    cur = w
    if cur:
        chunks.append(cur)
    return chunks


def chunk_text_for_tts(text: str, limit: int = MAX_CHARS) -> List[str]:
    sents = sentences(text)
    if not sents:
        return []
    return pack_sentences(sents, limit)


# ==== ELEVENLABS TTS (async + concurrent) ====
ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
HEADERS = {
    "xi-api-key": ELEVEN_API_KEY,
    "Accept": "audio/mpeg",
    "Content-Type": "application/json",
}


async def tts_request(text: str) -> bytes:
    """
    Single TTS call to ElevenLabs; returns MP3 bytes.
    Uses the official ElevenLabs Python client under the hood.
    """
    if not ELEVEN_API_KEY:
        raise RuntimeError("Missing ELEVEN_API_KEY")

    def _call() -> bytes:
        with client.text_to_speech.with_raw_response.convert(
            text=text,
            voice_id=VOICE_ID,
            model_id=MODEL_ID,
        ) as response:
            char_cost = response.headers.get("x-character-count")
            logger.debug("ElevenLabs char cost: %s", char_cost)
            data = response.data
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
            try:
                return b"".join(data)
            except TypeError:
                buf = BytesIO()
                for chunk in data:
                    buf.write(chunk)
                return buf.getvalue()

    return await asyncio.to_thread(_call)


async def text_to_audio_eleven(text: str, out_path: Optional[str] = None) -> str:
    """
    Chunk text, generate MP3 chunks concurrently, and merge using ffmpeg.
    Returns the output file path.
    """
    chunks = chunk_text_for_tts(text, limit=MAX_CHARS)
    logger.info("eleven: chunks=%d limit=%d concurrency=%d", len(chunks), MAX_CHARS, CONCURRENCY)
    if not chunks:
        raise ValueError("No speakable content after cleanup/splitting.")
    print(f"ElevenLabs: {len(chunks)} chunk(s), limit={MAX_CHARS}, concurrency={CONCURRENCY}")

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _task(i: int, t: str):
        async with sem:
            try:
                audio = await tts_request(t)
                logger.debug("eleven: chunk%d ok bytes=%d", i, len(audio))
                return i, audio
            except Exception as e:
                logger.error("eleven: chunk%d failed %s", i, e)
                raise

    tasks = [asyncio.create_task(_task(i, t)) for i, t in enumerate(chunks)]
    results = await asyncio.gather(*tasks)

    results.sort(key=lambda x: x[0])
    mp3_bytes_list = [b for _, b in results]

    if not out_path:
        filename = f"{uuid.uuid4().hex}.mp3"
        out_path = str(AUDIO_DIR / filename)

    final_path = concat_mp3_bytes_with_ffmpeg(mp3_bytes_list, out_path)
    print(f"Final audio => {final_path}")
    return final_path


# Optional: PDF → Audio utility
async def pdf_to_audio_file(pdf_bytes: bytes, merge: bool = True) -> dict:
    """
    Take a PDF as bytes, extract text per page, run TTS, return dict with
    'mode' and file URLs (relative paths).
    """
    t0 = monotonic()
    req_id = uuid.uuid4().hex[:8]
    logger.info("pdf-to-audio[%s]: starting", req_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf_path = tmp.name
        tmp.write(pdf_bytes)

    try:
        reader = PyPDF2.PdfReader(pdf_path)
        pages: List[Tuple[int, str]] = []
        for i, page in enumerate(reader.pages):
            txt = cleanup_text(page.extract_text() or "")
            if txt:
                pages.append((i, txt))
        logger.info("pdf-to-audio[%s]: extracted text pages=%d", req_id, len(pages))
    finally:
        try:
            os.remove(pdf_path)
        except Exception:
            logger.warning("pdf-to-audio[%s]: could not remove temp pdf", req_id)

    if not pages:
        return {"error": "No text could be extracted from the PDF."}

    base_id = uuid.uuid4().hex
    file_paths: List[str] = []

    async def render_one(idx: int, text: str) -> Tuple[int, str]:
        out_filename = f"{base_id}_page{idx + 1}.mp3"
        out_full_path = AUDIO_DIR / out_filename
        ts = monotonic()
        logger.info("pdf-to-audio[%s]: TTS start page=%d", req_id, idx + 1)
        await text_to_audio_eleven(text, str(out_full_path))
        logger.info(
            "pdf-to-audio[%s]: TTS ok page=%d ms=%d out=%s",
            req_id, idx + 1, int((monotonic() - ts) * 1000), out_full_path
        )
        return idx, str(out_full_path)

    t_tts = monotonic()
    tasks = [render_one(i, t) for i, t in pages]
    gathered = await asyncio.gather(*tasks, return_exceptions=True)
    logger.info(
        "pdf-to-audio[%s]: TTS total ms=%d",
        req_id, int((monotonic() - t_tts) * 1000)
    )

    ok_results: List[Tuple[int, str]] = []
    failed_count = 0
    for r in gathered:
        if isinstance(r, Exception):
            failed_count += 1
            logger.exception("pdf-to-audio[%s]: TTS page failed", req_id, exc_info=r)
        else:
            ok_results.append(cast(Tuple[int, str], r))

    if not ok_results:
        return {"error": "TTS failed for all pages. Check server logs for details."}

    ok_results.sort(key=lambda x: x[0])

    for _, out_path in ok_results:
        file_paths.append(out_path)

    if merge and file_paths:
        t_merge = monotonic()
        merged_name = f"{base_id}_merged.mp3"
        merged_path = AUDIO_DIR / merged_name
        try:
            concat_mp3_files_with_ffmpeg(file_paths, str(merged_path))
        except Exception as e:
            logger.exception("pdf-to-audio[%s]: merge failed", req_id)
            return {
                "mode": "split",
                "files": file_paths,
                "warning": f"Page audio generated, but merge failed: {e}",
            }
        logger.info(
            "pdf-to-audio[%s]: merged parts=%d ms=%d -> %s",
            req_id, len(file_paths), int((monotonic() - t_merge) * 1000), merged_path
        )
        logger.info(
            "pdf-to-audio[%s]: DONE mode=merged total_ms=%d",
            req_id, int((monotonic() - t0) * 1000)
        )
        return {"mode": "merged", "file": str(merged_path), "parts": file_paths}

    logger.info(
        "pdf-to-audio[%s]: DONE mode=split files=%d total_ms=%d",
        req_id, len(file_paths), int((monotonic() - t0) * 1000)
    )
    return {"mode": "split", "files": file_paths}

import os
import time
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal, Tuple

import httpx


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Cache controls (set via env if you want)
DEEPSEEK_CACHE_ENABLED = os.getenv("DEEPSEEK_CACHE_ENABLED", "true").lower() == "true"
DEEPSEEK_CACHE_TTL_SECONDS = int(os.getenv("DEEPSEEK_CACHE_TTL_SECONDS", "3600"))  # 1h default
DEEPSEEK_CACHE_MAX_ITEMS = int(os.getenv("DEEPSEEK_CACHE_MAX_ITEMS", "512"))

# Timeouts
DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "120"))

TaskPreset = Literal[
    "code_math",
    "data_analysis",
    "general",
    "translation",
    "creative",
    "summaries",
    "default",
]


def _temperature_for_preset(preset: TaskPreset) -> float:
    """
    Temperature guidance (approximate; adjust as you learn real behavior per model).
    """
    if preset == "code_math":
        return 0.0
    if preset == "data_analysis":
        return 1.0
    if preset == "general":
        return 1.3
    if preset == "translation":
        return 1.3
    if preset == "creative":
        return 1.5
    if preset == "summaries":
        # summaries: stable, coherent, low hallucination
        return 0.6
    return 0.6  # "default"


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


@dataclass
class _CacheEntry:
    value: str
    expires_at: float


# Simple in-memory TTL cache (per-process).
# If you need multi-worker / cross-instance caching, plug in Redis later.
_DEEPSEEK_CACHE: Dict[Tuple[str, float, str], _CacheEntry] = {}

# Shared HTTP client (connection pooling)
_HTTP_CLIENT: Optional[httpx.AsyncClient] = None


async def _get_http_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
        _HTTP_CLIENT = httpx.AsyncClient(timeout=DEEPSEEK_TIMEOUT_SECONDS)
    return _HTTP_CLIENT


def _cache_get(key: Tuple[str, float, str]) -> Optional[str]:
    if not DEEPSEEK_CACHE_ENABLED:
        return None
    entry = _DEEPSEEK_CACHE.get(key)
    if not entry:
        return None
    if time.time() >= entry.expires_at:
        _DEEPSEEK_CACHE.pop(key, None)
        return None
    return entry.value


def _cache_set(key: Tuple[str, float, str], value: str) -> None:
    if not DEEPSEEK_CACHE_ENABLED:
        return
    # basic eviction: if too many items, drop oldest-ish by expiry
    if len(_DEEPSEEK_CACHE) >= DEEPSEEK_CACHE_MAX_ITEMS:
        # remove a few expired; if none expired, remove one arbitrary oldest by expires_at
        now = time.time()
        expired_keys = [k for k, v in _DEEPSEEK_CACHE.items() if v.expires_at <= now]
        for k in expired_keys[:32]:
            _DEEPSEEK_CACHE.pop(k, None)
        if len(_DEEPSEEK_CACHE) >= DEEPSEEK_CACHE_MAX_ITEMS:
            oldest_key = min(_DEEPSEEK_CACHE.items(), key=lambda kv: kv[1].expires_at)[0]
            _DEEPSEEK_CACHE.pop(oldest_key, None)

    _DEEPSEEK_CACHE[key] = _CacheEntry(value=value, expires_at=time.time() + DEEPSEEK_CACHE_TTL_SECONDS)


async def call_deepseek(
    prompt: str,
    *,
    temperature: Optional[float] = None,
    preset: TaskPreset = "default",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Call DeepSeek Chat Completions with:
      - optional TTL cache
      - pooled HTTP client
      - temperature presets + overrides
      - optional max_tokens cap for cost control

    Notes:
      - To align with DeepSeek R1 guidance, we avoid system prompts and keep all instructions in user content.
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    use_model = model or DEEPSEEK_MODEL
    temp = float(_temperature_for_preset(preset) if temperature is None else temperature)

    key = (use_model, temp, _prompt_hash(prompt))
    cached = _cache_get(key)
    if cached is not None:
        return cached

    client = await _get_http_client()

    payload: Dict[str, Any] = {
        "model": use_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temp,
    }
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)

    resp = await client.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        json=payload,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"DeepSeek error: {resp.status_code} {resp.text}")

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"DeepSeek response parsing error: {e}; payload={data}")

    _cache_set(key, content)
    return content


async def close_deepseek_client() -> None:
    """
    Call this on shutdown if you want clean closing.
    """
    global _HTTP_CLIENT
    if _HTTP_CLIENT and not _HTTP_CLIENT.is_closed:
        await _HTTP_CLIENT.aclose()
    _HTTP_CLIENT = None

from __future__ import annotations

import gc
import os
import sys
from typing import Any

_ACTIVE_MODULE: str | None = None


def rss_mb() -> float:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        with open("/proc/self/statm", "r", encoding="utf-8") as fh:
            resident_pages = int(fh.read().split()[1])
        return round((resident_pages * page_size) / 1024 / 1024, 2)
    except Exception:
        pass
    try:
        import psutil  # type: ignore
        return round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return 0.0


def clear_module_cache(module: str | None = None) -> dict[str, Any]:
    cleared: list[str] = []
    # Current suite mostly uses module-level services and sqlite/files. We clear known in-memory caches only.
    try:
        from ai_suite.modules.research.api.llms.calls import _DEEPSEEK_CACHE
        _DEEPSEEK_CACHE.clear()
        cleared.append("research.deepseek_cache")
    except Exception:
        pass
    collected = gc.collect()
    return {"cleared": cleared, "gc_collected": collected, "memory": memory_snapshot()}


def set_active_module(name: str) -> None:
    global _ACTIVE_MODULE
    _ACTIVE_MODULE = name


def memory_snapshot() -> dict[str, Any]:
    return {"pid": os.getpid(), "rss_mb": rss_mb(), "active_module": _ACTIVE_MODULE, "python": sys.version.split()[0]}

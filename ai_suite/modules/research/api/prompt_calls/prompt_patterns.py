"""
Core utilities for pattern-based prompt generation.

Responsibilities:
- Load prompt pattern definitions from two CSV files:
    * prompt_patterns_detailed.csv
    * react_patterns.csv
- Build a tag context from UI tags.
- Build a pattern context from selected pattern names.
- Assemble a meta-prompt and call DeepSeek directly.
- Score the generated prompt.
- Save accepted prompts as .txt files for download.
"""

from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import pandas as pd
from ai_suite.modules.research.api.prompt_calls.model import TagIn, PromptResult
from ai_suite.modules.research.api.prompt_calls.score import score_generated_prompt
from ai_suite.modules.research.api.llms.calls import call_deepseek
import json

# -------------------------------------------------------------------
# Paths and config
# -------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"           # optional; adjust if needed
CSV_DETAILED = DATA_DIR / "prompt_patterns_detailed.csv"
CSV_REACT = DATA_DIR / "react_prompt_patterns.csv"

PROMPT_OUTPUT_DIR = BASE_DIR / "prompt_outputs"
PROMPT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Prompt builder uses the same DeepSeek provider as document generation.
# Optional override allows prompt-builder tuning without introducing another LLM vendor.
PROMPT_BUILDER_MODEL_ID = os.getenv("PROMPT_BUILDER_MODEL_ID", "").strip() or None
PROMPT_BUILDER_MAX_TOKENS = int(os.getenv("PROMPT_BUILDER_MAX_TOKENS", "4096"))
PROMPT_BUILDER_TEMPERATURE = float(os.getenv("PROMPT_BUILDER_TEMPERATURE", "0.7"))


MIN_PROMPT_SCORE = 0.6  # acceptance threshold


# Helpers 
# -------------------------------------------------------------------
def _parse_jsonish(value: Any, default: Any) -> Any:
    """
    CSV cells may store JSON as strings. This helper parses JSON when possible.
    Accepts: list/dict already, JSON strings, or fallback to default.
    """
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            return json.loads(s)
        except Exception:
            return default
    return default


def tags_to_dict(tags: List[TagIn]) -> Dict[str, str]:
    return {t.name.strip(): t.value.strip() for t in tags if t.name and t.value}


def extract_required_slot_maybe(pattern_row: Dict[str, Any], slot_name: str) -> Optional[Dict[str, Any]]:
    """
    Non-fatal slot lookup. Returns slot dict if found, else None.

    Supports multiple possible column names because CSV schemas vary.
    """
    # Try common column candidates
    candidates = [
        "required_slots",
        "slots_required",
        "required_inputs",
        "inputs_required",
    ]

    for col in candidates:
        raw = pattern_row.get(col)
        slots = _parse_jsonish(raw, default=[])
        if not slots:
            continue

        # Case A: list of strings
        if isinstance(slots, list) and slots and isinstance(slots[0], str):
            if slot_name in slots:
                return {"name": slot_name, "description": "", "required": True}
            continue

        # Case B: list of dicts
        if isinstance(slots, list):
            for s in slots:
                if isinstance(s, dict) and s.get("name") == slot_name:
                    return s

    return None


def enforce_ask_for_input(pattern_row: Dict[str, Any], tags: List[TagIn]) -> str:
    """
    Enforces Ask-for-Input even if CSV slot metadata is missing.
    Priority:
      1) tags['input_label_X']
      2) tags['input_label']
      3) CSV slot description (if present)
      4) generic fallback
    """
    tag_map = tags_to_dict(tags)

    slot_def = extract_required_slot_maybe(pattern_row, "input_label_X")
    slot_desc = (slot_def or {}).get("description", "") if slot_def else ""

    input_label = (
        tag_map.get("input_label_X")
        or tag_map.get("input_label")
        or slot_desc
        or "the required input"
    ).strip()

    return f"""
[ENFORCEMENT: Ask for Input]

Before producing the final deliverable, the assistant MUST request the user's input labeled:
- {input_label}

Rules:
- If this input has NOT been provided, respond ONLY by asking for it.
- Do NOT invent or assume the missing input.
- After receiving it, proceed with the task and then ask whether the user wants to provide another {input_label} or stop (if applicable).

Output constraint:
- When input is missing, output MUST contain only the request for {input_label} and nothing else.
""".strip()



def build_enforcement_context(pattern_rows: List[Dict[str, Any]], tags: List[TagIn]) -> str:
    """
    Build a combined enforcement section from all selected pattern rows.
    """
    blocks: List[str] = []

    for row in pattern_rows:
        name = (row.get("pattern_name") or "").strip()

        if name == "Ask for Input":
            blocks.append(enforce_ask_for_input(row, tags))

        # Add future enforcers here, e.g.:
        # if name == "Fact Check List": blocks.append(enforce_fact_check_list(row, tags))
        # if name == "Semantic Filter": blocks.append(enforce_semantic_filter(row, tags))
        # if name == "Tail Generation": blocks.append(enforce_tail_generation(row, tags))

    return "\n\n".join(b for b in blocks if b.strip())



# Pattern loading
# -------------------------------------------------------------------

def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Pattern CSV not found: {path}")
    df = pd.read_csv(path)
    # normalise column names a bit
    df.columns = [c.strip() for c in df.columns]
    return df


# Load at import time so we only hit disk once
DETAILED_DF = _load_csv(CSV_DETAILED)
REACT_DF = _load_csv(CSV_REACT)

# Combined view with a "source" column
ALL_PATTERNS_DF = pd.concat(
    [
        DETAILED_DF.assign(source="detailed"),
        REACT_DF.assign(source="react"),
    ],
    ignore_index=True,
)


def get_patterns_by_name(names: Iterable[str]) -> List[Dict[str, Any]]:
    """
    Look up patterns by pattern_name from both CSVs.
    Returns a list of plain dict rows.
    """
    name_set = {n.strip() for n in names}
    if not name_set:
        return []

    subset = ALL_PATTERNS_DF[ALL_PATTERNS_DF["pattern_name"].isin(name_set)]
    rows = subset.to_dict(orient="records")

    # Pandas returns list[dict[Hashable, Any]], which we know are str keys here.
    return cast(List[Dict[str, Any]], rows)


# -------------------------------------------------------------------
# Context builders
# -------------------------------------------------------------------

def build_tag_context(tags: List[TagIn]) -> str:
    """
    Turn a list of Tag objects into the <tag> context block.
    """
    lines: List[str] = []
    for t in tags:
        if not t.value.strip():
            continue
        lines.append(f"<{t.name}> {t.value}")
    return "\n".join(lines)


def build_pattern_context(pattern_rows: List[Dict[str, Any]]) -> str:
    """
    Turn pattern rows from the CSV into a compact textual "pattern brief"
    for the prompt generator model.

    We rely on the following columns being present in the CSV:
    - pattern_name
    - pattern_family
    - primary_purpose
    - core_mechanism
    - example_prompt_skeleton
    Any missing column is treated as empty text.
    """
    parts: List[str] = []

    for row in pattern_rows:
        # Some columns may be JSON strings; that's fine for a model.
        name = str(row.get("pattern_name", "")).strip()
        family = str(row.get("pattern_family", "")).strip()
        purpose = str(row.get("primary_purpose", "")).strip()
        mech = str(row.get("core_mechanism", "")).strip()
        skeleton = str(row.get("example_prompt_skeleton", "")).strip()

        parts.append(
            f"Pattern name: {name}\n"
            f"Family: {family}\n"
            f"Primary purpose: {purpose}\n"
            f"Core mechanism: {mech}\n"
            f"Example skeleton:\n{skeleton}\n"
            "----\n"
        )

    return "".join(parts)


def build_prompt_generator_instruction(
    tag_context: str,
    pattern_context: str,
    enforcement_context: str = "",
) -> str:
    enforcement_block = f"\n\n{enforcement_context}\n" if enforcement_context.strip() else ""

    return f"""
You are an expert prompt engineer. Your job is to produce a single high-quality prompt that the user can reuse.

<Tag Context>
{tag_context}
</Tag Context>

<Pattern Embeddings>
{pattern_context}
</Pattern Embeddings>
{enforcement_block}

Return ONLY the final prompt text. Do not explain your reasoning. Do not add commentary.
""".strip()


# -------------------------------------------------------------------
# DeepSeek prompt-generation call
# -------------------------------------------------------------------

async def call_deepseek_prompt_generator(meta_prompt: str) -> str:
    """
    Generate the final prompt text through DeepSeek only.

    This deliberately reuses api.llms.calls.call_deepseek so production LLM
    traffic is controlled by the same DEEPSEEK_* environment variables and
    provider code path used by the document-generation endpoints.
    """
    provider_prompt = (
        "You are an expert prompt engineer. Given the meta-prompt, produce a "
        "single, ready-to-use prompt. Output only the final prompt text, with "
        "no explanations or commentary.\n\n"
        f"{meta_prompt}"
    )
    return await call_deepseek(
        provider_prompt,
        temperature=PROMPT_BUILDER_TEMPERATURE,
        preset="creative",
        model=PROMPT_BUILDER_MODEL_ID,
        max_tokens=PROMPT_BUILDER_MAX_TOKENS,
    )


# -------------------------------------------------------------------
# Scoring & saving
# -------------------------------------------------------------------




def save_prompt_to_txt(prompt_text: str) -> str:
    """
    Save the prompt text into a timestamped .txt file under PROMPT_OUTPUT_DIR.
    Returns the absolute filesystem path.
    """
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"prompt_{ts}.txt"
    path = PROMPT_OUTPUT_DIR / filename
    path.write_text(prompt_text, encoding="utf-8")
    return str(path)


# -------------------------------------------------------------------
# High-level orchestrator
# -------------------------------------------------------------------

async def generate_prompt_from_patterns(
    tags: List[TagIn],
    pattern_names: List[str],
    min_score: float = MIN_PROMPT_SCORE,
) -> PromptResult:
    if not tags:
        raise ValueError("At least one tag is required")
    if not pattern_names:
        raise ValueError("At least one pattern name is required")

    tag_context = build_tag_context(tags)
    pattern_rows = get_patterns_by_name(pattern_names)
    if not pattern_rows:
        raise ValueError("No patterns found for the given names")

    pattern_context = build_pattern_context(pattern_rows)

    # NEW: enforcement derived from CSV + tags
    enforcement_context = build_enforcement_context(pattern_rows, tags)

    meta_prompt = build_prompt_generator_instruction(
        tag_context=tag_context,
        pattern_context=pattern_context,
        enforcement_context=enforcement_context,  # NEW
    )

    prompt_text = await call_deepseek_prompt_generator(meta_prompt)
    score = score_generated_prompt(prompt_text)

    if score >= min_score:
        file_path = save_prompt_to_txt(prompt_text)
        accepted = True
    else:
        file_path = None
        accepted = False

    return PromptResult(
        prompt_text=prompt_text,
        score=score,
        accepted=accepted,
        file_path=file_path,
    )



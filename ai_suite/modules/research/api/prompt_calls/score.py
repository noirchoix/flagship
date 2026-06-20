import re
from typing import Final


def score_generated_prompt(text: str) -> float:
    """
    Heuristically score a generated prompt for quality.

    Dimensions (derived from prompt-engineering best practices):
    - Length sanity (not too short / not excessively long)
    - Clear role / goal / task specification
    - Use of strong action verbs and specific output instructions
    - Presence of context / input sections
    - Use of variables / placeholders to make the prompt reusable
    - Preference for positive instructions over long lists of "do not"
    - Penalties for meta-talk about the prompt itself

    Returns:
        float in [0.0, 1.0]
    """

    # --------- basic normalization ----------
    raw = text or ""
    stripped = raw.strip()
    lower = stripped.lower()
    tokens = stripped.split()
    n_tokens = len(tokens)

    # start from a baseline; we will add/subtract around this
    score: float = 0.5

    # --------- 1. length sanity (Google: control length, avoid vague prompts) ----------
    # ideal: ~60–400 tokens; we give soft penalties outside this band
    if n_tokens == 0:
        return 0.0

    if n_tokens < 40:
        score -= 0.25
    elif 40 <= n_tokens <= 400:
        score += 0.15
    elif n_tokens > 600:
        score -= 0.25

    # --------- 2. explicit role / task / goal  ----------
    # good prompts set context and goal clearly.
    if re.search(r"\byou are\b", lower):
        score += 0.15
    if re.search(r"\byour role\b|\bact as\b|\brole:\b", lower):
        score += 0.1
    if re.search(r"\btask:\b|\bgoal:\b|\bobjective:\b", lower):
        score += 0.1

    # --------- 3. strong action verbs & specific output instructions ----------
    # Based on "use verbs that describe the action" and "be specific about the output".
    ACTION_VERBS: Final = [
        "act", "analyze", "categorize", "classify", "contrast", "compare",
        "create", "describe", "define", "evaluate", "extract", "find",
        "generate", "identify", "list", "organize", "parse", "predict",
        "provide", "rank", "recommend", "return", "retrieve", "rewrite",
        "select", "show", "sort", "summarize", "translate", "write"
    ]
    # Check if at least one of these appears near the beginning (first ~30 tokens)
    first_slice = " ".join(tokens[:30]).lower()
    action_hits = sum(1 for v in ACTION_VERBS if v in first_slice)
    if action_hits >= 1:
        score += 0.1
    if action_hits >= 3:
        score += 0.05  # prompt is clearly "doing something"

    # "Be specific about the output"
    if re.search(r"\bformat\b|\bstructured\b|\bsections?\b|\bheadings?\b", lower):
        score += 0.1
    if re.search(r"\bjson\b|\btable\b|\bbullet points?\b|\bmarkdown\b", lower):
        score += 0.1
    if re.search(r"\bnumbered steps\b|\bstep[- ]by[- ]step\b", lower):
        score += 0.1

    # --------- 4. context / input / constraints sections ----------
    # Good prompts usually separate context, input, constraints.
    if re.search(r"\bcontext:\b|\bbackground:\b|\binput:\b", lower):
        score += 0.1
    if re.search(r"\bconstraints?:\b|\brules:\b|\bguidelines:\b", lower):
        score += 0.05

    # --------- 5. variables / placeholders (parameters) ----------
    # Using variables/slots (e.g., {topic}) is considered a best practice.
    if re.search(r"\{[a-z0-9_]+\}", stripped, flags=re.IGNORECASE):
        score += 0.1
    if re.search(r"<[a-z0-9_ ]+>", stripped, flags=re.IGNORECASE):
        score += 0.05

    # --------- 6. preference for positive instructions over "do not" ----------
    # The whitepaper recommends instructions > constraints.
    do_count = len(re.findall(r"\bdo\b", lower))
    do_not_count = len(re.findall(r"\bdo not\b|\bdon't\b", lower))
    if do_count > 0:
        score += 0.05  # at least some explicit "do" instruction

    # If there are many "do not" clauses compared to positive "do" instructions, penalize.
    if do_not_count > 0 and do_not_count > do_count:
        score -= 0.15
    if do_not_count >= 3:
        score -= 0.1

    # --------- 7. structural cues from pattern-style prompts ----------
    # Prompts that look like pattern-based instructions (multiple numbered requirements).
    numbered_lines = len(re.findall(r"^\s*\d+\.", stripped, flags=re.MULTILINE))
    if numbered_lines >= 3:
        score += 0.1

    # --------- 8. penalties for meta-talk and vagueness ----------
    # Meta-talk about "this prompt" etc. usually indicates leakage from the tool.
    if "as a prompt engineer" in lower:
        score -= 0.3
    if "in this prompt" in lower or "this prompt should" in lower:
        score -= 0.2

    # Overuse of vague "etc." and "and so on" is a signal of under-specification
    etc_count = lower.count("etc.")
    if etc_count >= 2:
        score -= 0.1
    if "and so on" in lower:
        score -= 0.05

    # --------- 9. mild reward if it looks like a pattern-based design ----------
    # e.g., mentions of role, context, constraints and output all together
    has_role = "you are" in lower or "act as" in lower
    has_context = "context:" in lower or "background:" in lower
    has_output = "output:" in lower or "return" in lower or "produce" in lower
    if has_role and has_context and has_output:
        score += 0.15

    # --------- clamp to [0, 1] ----------
    if score < 0.0:
        score = 0.0
    if score > 1.0:
        score = 1.0
    return score

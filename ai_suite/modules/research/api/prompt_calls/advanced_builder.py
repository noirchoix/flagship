from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ai_suite.modules.research.api.prompt_calls.model import TagIn, PromptResult
from ai_suite.modules.research.api.prompt_calls.prompt_patterns import PROMPT_OUTPUT_DIR
from ai_suite.modules.research.api.prompt_calls.score import score_generated_prompt


FRAMEWORK_HINTS: Dict[str, Dict[str, str]] = {
    "RTF": {"use": "role-based execution", "shape": "Role → Task → Format"},
    "RISEN": {"use": "multi-phase project delivery", "shape": "Role → Instructions → Steps → End goal → Narrowing"},
    "RODES": {"use": "architecture, design, and complex analysis", "shape": "Role → Objective → Details → Examples → Sense check"},
    "RISE": {"use": "research, diagnosis, investigation", "shape": "Research → Investigate → Synthesize → Evaluate"},
    "RACE": {"use": "audience-aware communication", "shape": "Role → Audience → Context → Expectation"},
    "STAR": {"use": "contextual problem solving", "shape": "Situation → Task → Action → Result"},
    "SOAP": {"use": "incident/documentation style outputs", "shape": "Subjective → Objective → Assessment → Plan"},
    "CLEAR": {"use": "goal setting and measurable outcomes", "shape": "Collaborative → Limited → Emotional → Appreciable → Refinable"},
    "GROW": {"use": "coaching and development plans", "shape": "Goal → Reality → Options → Will"},
    "Chain-of-Thought": {"use": "step-by-step reasoning and debugging", "shape": "Problem → Reasoning steps → Validated answer"},
    "Few-shot": {"use": "format consistency and edge cases", "shape": "Examples → New input → Expected output"},
    "Template": {"use": "reusable production prompts", "shape": "Variables → Sections → Output contract"},
}

PATTERN_TO_FRAMEWORK = {
    "Chain-of-Thought": "Chain-of-Thought",
    "Template Pattern": "Template",
    "Recipe Pattern": "RISEN",
    "Alternative Approaches": "RODES",
    "Ask for Input": "GROW",
    "Fact Check List": "RISE",
    "Semantic Filter": "RISE",
    "Menu Actions": "RACE",
    "Meta Language Creation": "Template",
    "Tail Generation": "CLEAR",
    "ReAct": "RISE",
}


def _tag_map(tags: List[TagIn]) -> Dict[str, str]:
    return {t.name.strip().lower(): t.value.strip() for t in tags if t.name.strip() and t.value.strip()}


def _first_value(tag_map: Dict[str, str], keys: List[str], fallback: str = "") -> str:
    for key in keys:
        value = tag_map.get(key)
        if value:
            return value
    return fallback


def _infer_frameworks(pattern_names: List[str], tag_map: Dict[str, str]) -> List[str]:
    chosen: List[str] = []
    for name in pattern_names:
        fw = PATTERN_TO_FRAMEWORK.get(name)
        if fw and fw not in chosen:
            chosen.append(fw)

    source = " ".join([*pattern_names, *tag_map.values()]).lower()
    inferred = [
        ("Chain-of-Thought", ["debug", "reason", "step", "diagnose", "error", "bug"]),
        ("RODES", ["architecture", "design", "system", "strategy", "technical"]),
        ("RISE", ["research", "investigate", "evidence", "source", "analysis"]),
        ("RACE", ["email", "presentation", "audience", "executive", "stakeholder"]),
        ("Few-shot", ["example", "format", "extract", "classify", "label"]),
        ("Template", ["reusable", "template", "variable", "production", "schema"]),
    ]
    for framework, keywords in inferred:
        if framework not in chosen and any(k in source for k in keywords):
            chosen.append(framework)

    if not chosen:
        chosen = ["RTF", "RODES", "Template"]
    elif "RTF" not in chosen:
        chosen.insert(0, "RTF")

    return chosen[:4]


def _as_yaml_list(items: List[str], indent: int = 2) -> str:
    pad = " " * indent
    if not items:
        return f"{pad}[]"
    return "\n".join(f"{pad}- {item}" for item in items)


def _build_optimized_prompt(tag_map: Dict[str, str], frameworks: List[str], pattern_names: List[str]) -> str:
    objective = _first_value(tag_map, ["objective", "goal", "task", "topic", "prompt", "usecase", "use_case"], "{describe_the_task}")
    audience = _first_value(tag_map, ["audience", "user", "reader"], "the intended user or reviewer")
    context = _first_value(tag_map, ["context", "background", "source", "document"], "{provide_relevant_context_or_input}")
    output = _first_value(tag_map, ["output", "format", "deliverable"], "a structured Markdown response with clear sections, examples where useful, and a final checklist")
    constraints = _first_value(tag_map, ["constraints", "rules", "limits", "requirements"], "be specific, avoid unsupported claims, ask for critical missing inputs, and keep the result directly usable")
    examples = _first_value(tag_map, ["examples", "example", "few_shot"], "{optional_examples_or_edge_cases}")

    framework_note = ", ".join(frameworks)
    pattern_note = ", ".join(pattern_names) if pattern_names else "auto-selected prompt patterns"

    prompt = f"""You are a senior prompt systems architect and domain expert for the task below.

Objective:
{objective}

Audience:
{audience}

Context:
{context}

Prompting strategy to apply:
Use a blended structure based on {framework_note}. Incorporate the useful behavior of these selected patterns: {pattern_note}. Do not mention the framework names in the final user-facing answer unless the user explicitly asks.

Instructions:
1. Identify the user's real intent and the expected outcome.
2. Ask at most three clarifying questions only if missing information would materially change the answer.
3. If enough information is available, proceed without unnecessary questions.
4. Work through the task in a disciplined sequence: understand context, decide the approach, produce the deliverable, then validate it against the objective.
5. Use examples or edge cases when they improve reliability or format consistency.
6. Apply a sense-check before the final answer: verify correctness, completeness, constraints, and output format.

Constraints:
{constraints}

Examples or edge cases:
{examples}

Output format:
{output}
""".strip()
    return prompt


def _build_test_cases(tag_map: Dict[str, str], objective: str) -> List[Dict[str, Any]]:
    domain = _first_value(tag_map, ["domain", "topic", "usecase", "use_case"], "general")
    return [
        {
            "id": "happy_path",
            "input": f"A clear, complete request about {objective}",
            "expected_behavior": "Produces the requested output in the specified structure without asking unnecessary questions.",
            "checks": ["task_completed", "format_followed", "constraints_respected"],
        },
        {
            "id": "missing_context",
            "input": f"An underspecified request in the {domain} domain",
            "expected_behavior": "Asks only the critical clarification questions needed to proceed safely.",
            "checks": ["max_three_questions", "no_unfounded_assumptions"],
        },
        {
            "id": "edge_case",
            "input": "A request with conflicting constraints or incomplete source material",
            "expected_behavior": "Names the conflict, proposes a safe interpretation, and does not fabricate missing facts.",
            "checks": ["conflict_detected", "safe_fallback", "no_hallucination"],
        },
    ]


def _build_artifacts(prompt_text: str, tag_map: Dict[str, str], frameworks: List[str], pattern_names: List[str], score: float) -> Dict[str, Any]:
    objective = _first_value(tag_map, ["objective", "goal", "task", "topic", "prompt", "usecase", "use_case"], "Prompt optimization task")
    rubric = {
        "accuracy": "Output must address the actual user objective without unsupported claims.",
        "completeness": "Output must cover the required deliverable, constraints, and edge cases.",
        "format_compliance": "Output must follow the requested structure and file/artifact format.",
        "clarification_discipline": "Clarifying questions are used only when materially necessary and capped at three.",
        "reusability": "Prompt should be reusable with variables/placeholders where appropriate.",
        "safety_grounding": "Prompt should avoid unsafe actions, secret exposure, and invented evidence.",
    }
    test_cases = _build_test_cases(tag_map, objective)
    spec = {
        "name": "optimized_prompt_spec",
        "objective": objective,
        "framework_blend": frameworks,
        "selected_patterns": pattern_names,
        "quality_score": round(score, 3),
        "rubric": rubric,
        "test_cases": test_cases,
        "prompt_text": prompt_text,
    }
    scoring_yaml = "scoring_rubric:\n" + "\n".join(f"  {k}: {v}" for k, v in rubric.items())
    eval_json = json.dumps({"test_cases": test_cases, "rubric": rubric}, indent=2)
    failure_md = "\n".join([
        "# Failure Analysis",
        "",
        "Potential failure modes to test before production use:",
        "",
        "- **Over-clarification**: the prompt asks questions even when enough context exists.",
        "- **Under-specification**: output format or constraints are not enforced.",
        "- **Example pollution**: few-shot examples bias the model away from the actual task.",
        "- **Unsupported claims**: model invents facts when source material is incomplete.",
        "- **Long prompt drift**: the final output ignores later constraints because the prompt is too large.",
        "",
        "Mitigation: run the prompt against the included evaluation cases and revise any section that fails the rubric.",
    ])
    spec_md = "\n".join([
        "# PROMPT_SPEC.md",
        "",
        f"## Objective\n{objective}",
        "",
        f"## Framework blend\n{', '.join(frameworks)}",
        "",
        f"## Selected patterns\n{', '.join(pattern_names) if pattern_names else 'Auto-selected'}",
        "",
        "## Production prompt",
        "```text",
        prompt_text,
        "```",
        "",
        "## Evaluation rubric",
        *[f"- **{k}**: {v}" for k, v in rubric.items()],
        "",
        "## Regression cases",
        *[f"- `{case['id']}`: {case['expected_behavior']}" for case in test_cases],
    ])
    return {
        "prompt_spec_md": spec_md,
        "scoring_rubric_yaml": scoring_yaml,
        "prompt_eval_suite_json": eval_json,
        "failure_analysis_md": failure_md,
        "structured_spec": spec,
    }


async def build_advanced_prompt(tags: List[TagIn], pattern_names: List[str]) -> PromptResult:
    tag_map = _tag_map(tags)
    frameworks = _infer_frameworks(pattern_names, tag_map)
    prompt_text = _build_optimized_prompt(tag_map, frameworks, pattern_names)
    score = score_generated_prompt(prompt_text)
    accepted = score >= 0.6

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_path: str | None = None
    if accepted:
        path = PROMPT_OUTPUT_DIR / f"prompt_spec_{timestamp}.txt"
        artifacts = _build_artifacts(prompt_text, tag_map, frameworks, pattern_names, score)
        path.write_text(artifacts["prompt_spec_md"], encoding="utf-8")
        file_path = str(path)

    result = PromptResult(
        prompt_text=prompt_text,
        score=score,
        accepted=accepted,
        file_path=file_path,
    )
    # Attach rich artifacts dynamically so existing imports stay backward-compatible.
    artifacts = _build_artifacts(prompt_text, tag_map, frameworks, pattern_names, score)
    setattr(result, "framework_blend", frameworks)
    setattr(result, "artifacts", artifacts)
    setattr(result, "recommendations", [
        "Run the included regression cases before using this prompt in production.",
        "Keep stable instructions at the top and move dynamic user inputs to variables/placeholders.",
        "Use low temperature for evaluation and cache only deterministic prompt outputs.",
    ])
    return result

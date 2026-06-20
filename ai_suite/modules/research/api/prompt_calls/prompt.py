# ============================================================
# PROMPT BUILDERS
# ============================================================

from ai_suite.modules.research.api.prompt_calls.store import PROMPT_PATTERNS_DETAILED, react_patterns  # kept for future use
from typing import Optional


def build_prompt(
    task_type: str,
    title: str,
    content: str,
    extra_instructions: Optional[str] = None,
) -> str:
    """
    Build a high-quality, structured prompt for the given task type.

    Common structure (aligned with prompt-engineering best practices):
      - ROLE: who the model should be
      - CONTEXT: document title and content
      - TASK: what to produce
      - OUTPUT FORMAT: structure, length, style
      - CONSTRAINTS: what to avoid / guard rails
      - OPTIONAL: Additional user instructions
    """

    base_context = (
        "CONTEXT:\n"
        f"- You are given a research document.\n"
        f"- Title: {title}\n\n"
        "Document content:\n"
        f"{content}\n"
    )

    extra_block = (
        f"\nADDITIONAL INSTRUCTIONS:\n{extra_instructions}\n"
        if extra_instructions
        else ""
    )

    # ---------------- short summary ----------------
    if task_type == "short_summary":
        return (
            "ROLE:\n"
            "You are an expert research assistant who writes concise, faithful summaries for busy researchers.\n\n"
            "TASK:\n"
            "Summarize the core problem, approach, and main findings of the document.\n\n"
            "OUTPUT FORMAT:\n"
            "- 2–3 short paragraphs.\n"
            "- Plain English, suitable for a technically literate but non-expert reader.\n"
            "- Focus on: (1) problem/motivation, (2) method at a high level, (3) key results and implications.\n\n"
            "CONSTRAINTS:\n"
            "- Do NOT invent facts, datasets, or results that are not clearly supported by the document.\n"
            "- Do NOT include implementation details, equations, or citations; keep it high-level.\n"
            "- Do NOT mention that you are an AI model or refer to “this prompt”.\n\n"
            f"{base_context}"
            f"{extra_block}"
        )

    # ---------------- long summary ----------------
    if task_type == "long_summary":
        return (
            "ROLE:\n"
            "You are an expert peer-reviewer summarizing a research article for a technical audience.\n\n"
            "TASK:\n"
            "Write a detailed but readable summary of the article.\n\n"
            "OUTPUT FORMAT:\n"
            "- Target length: approximately 800–1500 words.\n"
            "- Use clear section headings with the following structure:\n"
            "  1. Background and Motivation\n"
            "  2. Problem Statement\n"
            "  3. Methods and Experimental Setup\n"
            "  4. Results and Evaluation\n"
            "  5. Limitations\n"
            "  6. Implications and Future Work\n"
            "- Use paragraphs and bullet points where helpful.\n\n"
            "CONSTRAINTS:\n"
            "- Do NOT fabricate experimental results, datasets, or citations.\n"
            "- If information is missing or unclear in the document, state that it is unspecified instead of guessing.\n"
            "- Do NOT talk about the prompt itself or your reasoning process; present only the final summary.\n\n"
            f"{base_context}"
            f"{extra_block}"
        )

    # ---------------- research summary (advanced) ----------------
    if task_type == "research_summary":
        return (
            "ROLE:\n"
            "You are a senior researcher preparing an advanced technical summary of this article for expert readers.\n\n"
            "TASK:\n"
            "Produce an in-depth research summary that highlights novelty, methodology, and evidence.\n\n"
            "OUTPUT FORMAT:\n"
            "- Use the following structure with headings and bullets where appropriate:\n"
            "  1. Formal Problem Definition\n"
            "  2. Key Novel Contributions (what is new vs prior work)\n"
            "  3. Technical Approach and Design Choices\n"
            "  4. Evaluation Setup (datasets, baselines, metrics)\n"
            "  5. Strongest Results and Evidence\n"
            "  6. Limitations and Open Questions\n"
            "- Write in precise, technical language suitable for a researcher or engineer.\n"
            "- Refer to equations or algorithms in words only; do not introduce new math notation.\n\n"
            "CONSTRAINTS:\n"
            "- Base all claims strictly on the document; if a detail is not stated, say that it is not specified.\n"
            "- Avoid generic phrases like “etc.” and “and so on”; be as concrete as the text allows.\n"
            "- Do NOT refer to “this prompt” or describe how you are generating the answer.\n\n"
            f"{base_context}"
            f"{extra_block}"
        )

    # ---------------- mathematical proof ----------------
    if task_type == "math_proof":
        return (
            "ROLE:\n"
            "You are a logician and mathematician translating technical claims into structured, LaTeX-formatted mathematics.\n\n"
            "TASK:\n"
            "Extract the core theoretical claims from the document and rewrite them as a structured mathematical treatment.\n\n"
            "OUTPUT FORMAT (LaTeX BODY ONLY):\n"
            "- Do NOT include a preamble, \\documentclass, or \\begin{document}/\\end{document}.\n"
            "- Structure the output as:\n"
            "  \\section*{Key Definitions}\n"
            "    - Formal definitions using LaTeX math environments.\n"
            "  \\section*{Assumptions}\n"
            "    - A1, A2, ... with clear statements and domains.\n"
            "  \\section*{Main Theorems}\n"
            "    - Theorem / Proposition statements using quantifiers (\\forall, \\exists) and logical connectives\n"
            "      (\\land, \\lor, \\rightarrow, \\neg).\n"
            "  \\section*{Proof Sketches}\n"
            "    - Step-by-step proof sketches for each main result.\n\n"
            "CONSTRAINTS:\n"
            "- Annotate the domain of every quantified variable so that the meaning is unambiguous.\n"
            "- Do NOT invent new assumptions or theorems that are not reasonably implied by the text.\n"
            "- Use clear, readable LaTeX; avoid unnecessary macros or packages.\n"
            "- Output only LaTeX body content as described above.\n\n"
            f"{base_context}"
            f"{extra_block}"
        )

    # ---------------- prompt_draft ----------------
    if task_type == "prompt_draft":
        return (
            "ROLE:\n"
            "You are an expert prompt engineer designing reusable prompts for large language models.\n\n"
            "TASK:\n"
            "Based on the article and context above, create 3–5 high-quality prompt patterns for analyzing, summarizing,\n"
            "or transforming research articles on this topic.\n\n"
            "OUTPUT FORMAT:\n"
            "- For EACH pattern, use the following structure:\n"
            "  Name: <short descriptive name>\n"
            "  Purpose: <one-sentence description of what this prompt is for>\n"
            "  Prompt:\n"
            "    <full prompt text, ready to paste into an LLM>\n"
            "  When to use: <one-line guidance on scenarios where this prompt is ideal>\n"
            "- Use placeholders in {curly_braces} for parameters such as {document_title}, {research_question}, {audience}.\n"
            "- Number the patterns (Pattern 1, Pattern 2, ...).\n\n"
            "CONSTRAINTS:\n"
            "- Follow prompt-engineering best practices: clear role, explicit task, constraints, and output format.\n"
            "- Avoid meta-talk like “in this prompt” or “as a prompt engineer” inside the generated prompts themselves.\n"
            "- Do NOT reference the internal scoring or evaluation logic of any system.\n\n"
            f"{base_context}"
            f"{extra_block}"
        )

    raise ValueError(f"Unknown task_type: {task_type}")

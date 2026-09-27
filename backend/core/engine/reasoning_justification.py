"""
Reasoning Dimension 4: Justification Quality (LLM, Phase 2, optional).

Analyzes team_notes and stakeholder communications for reasoning depth:
- Surface (0-25): bare statements
- Evidence-based (26-50): references simulation data
- Multi-perspective (51-75): considers tradeoffs and alternatives
- Framework-grounded (76-100): applies strategic frameworks with data

This module provides:
1. Prompt builder for the analyst LLM call
2. Response parser to extract structured scores
3. Template fallback when LLM is unavailable

Pure function — no I/O, no database access.
"""
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class JustificationInput:
    team_notes: str = ''  # From DecisionSubmission.team_notes
    communications: List[str] = field(default_factory=list)  # TeamCommunication contents
    decision_summary: str = ''  # Compiled summary of decisions this round
    language: str = 'en'


@dataclass
class JustificationResult:
    score: float  # 0-100
    depth_label: str  # surface/evidence_based/multi_perspective/framework_grounded
    evidence: List[str] = field(default_factory=list)
    feedback: str = ''
    raw_response: str = ''


# ── Prompt builder ──

JUSTIFICATION_SYSTEM_PROMPT = (
    "You are a strategic management professor evaluating the quality of a "
    "student team's strategic reasoning in a global business simulation. "
    "Analyze their justification notes and communications for depth of reasoning.\n\n"
    "Score on this rubric:\n"
    "- 0-25 (Surface): Bare statements with no reasoning ('We entered China')\n"
    "- 26-50 (Evidence-based): References simulation data ('Revenue dropped 15% so we cut marketing')\n"
    "- 51-75 (Multi-perspective): Considers tradeoffs and alternatives\n"
    "- 76-100 (Framework-grounded): Applies strategic frameworks (Porter, PESTEL, etc.) with data\n\n"
    "Respond ONLY in valid JSON:\n"
    '{"score": <int 0-100>, "depth": "<surface|evidence_based|multi_perspective|framework_grounded>", '
    '"evidence": ["<quote or observation>", ...], "feedback": "<2-3 sentences>"}'
)


def build_justification_prompt(inp: JustificationInput) -> dict:
    """
    Build the LLM prompt for justification analysis.

    Returns dict with 'system_prompt' and 'prompt' keys ready for LLM call.
    """
    parts = []

    if inp.team_notes:
        parts.append(f"=== Team Decision Notes ===\n{inp.team_notes}")

    if inp.communications:
        comms_text = "\n---\n".join(inp.communications)
        parts.append(f"=== Stakeholder Communications ===\n{comms_text}")

    if inp.decision_summary:
        parts.append(f"=== Decision Summary ===\n{inp.decision_summary}")

    if not parts:
        return {
            'system_prompt': JUSTIFICATION_SYSTEM_PROMPT,
            'prompt': 'No notes or communications were submitted. Score accordingly.',
        }

    content = "\n\n".join(parts)

    language_instruction = ''
    if inp.language == 'zh-CN':
        language_instruction = "\n\n请完全使用简体中文回复。使用专业的商业术语。"

    return {
        'system_prompt': JUSTIFICATION_SYSTEM_PROMPT,
        'prompt': (
            f"Evaluate the strategic reasoning depth of this team:\n\n"
            f"{content}\n\n"
            f"Score their justification quality (0-100) and classify depth."
            f"{language_instruction}"
        ),
    }


def parse_justification_response(raw_text: str) -> JustificationResult:
    """
    Parse LLM response into structured JustificationResult.

    Handles JSON extraction from potential markdown-wrapped responses.
    """
    text = raw_text.strip()

    # Strip markdown code fences
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()

    try:
        parsed = json.loads(text)
        score = max(0, min(100, int(parsed.get('score', 25))))
        depth = parsed.get('depth', _depth_from_score(score))
        evidence = parsed.get('evidence', [])
        if isinstance(evidence, str):
            evidence = [evidence]
        feedback = parsed.get('feedback', '')

        return JustificationResult(
            score=float(score),
            depth_label=depth,
            evidence=evidence,
            feedback=feedback,
            raw_response=raw_text,
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        # Fallback: try to extract score from text
        return template_fallback_score('')


def _depth_from_score(score: int) -> str:
    if score >= 76:
        return 'framework_grounded'
    elif score >= 51:
        return 'multi_perspective'
    elif score >= 26:
        return 'evidence_based'
    return 'surface'


def template_fallback_score(team_notes: str) -> JustificationResult:
    """
    Template-based fallback when LLM is unavailable.

    Uses simple heuristics on the text content:
    - Length
    - Presence of numbers/data references
    - Presence of framework keywords
    """
    if not team_notes:
        return JustificationResult(
            score=10.0,
            depth_label='surface',
            evidence=[],
            feedback='No justification notes were submitted.',
        )

    words = team_notes.split()
    word_count = len(words)
    text_lower = team_notes.lower()

    score = 15.0  # Base for having notes

    # Length bonus
    if word_count >= 200:
        score += 15.0
    elif word_count >= 100:
        score += 10.0
    elif word_count >= 50:
        score += 5.0

    # Data references (numbers, percentages, dollar amounts)
    import re
    data_refs = len(re.findall(r'\d+%|\$[\d,.]+|\d+\.\d+', team_notes))
    if data_refs >= 5:
        score += 20.0
    elif data_refs >= 2:
        score += 10.0
    elif data_refs >= 1:
        score += 5.0

    # Framework keywords
    framework_keywords = [
        'porter', 'pestel', 'swot', 'value chain', 'competitive advantage',
        'differentiation', 'cost leadership', 'five forces', 'bcg matrix',
        'ansoff', 'blue ocean', 'resource-based', 'stakeholder',
        'tradeoff', 'trade-off', 'alternatively', 'on the other hand',
        'compared to', 'risk-reward', 'scenario analysis',
    ]
    framework_hits = sum(1 for kw in framework_keywords if kw in text_lower)
    if framework_hits >= 3:
        score += 25.0
    elif framework_hits >= 1:
        score += 10.0

    # Tradeoff language
    tradeoff_keywords = ['however', 'although', 'while', 'despite', 'alternatively',
                          'on the other hand', 'weighing', 'balance']
    tradeoff_hits = sum(1 for kw in tradeoff_keywords if kw in text_lower)
    if tradeoff_hits >= 2:
        score += 10.0
    elif tradeoff_hits >= 1:
        score += 5.0

    score = min(score, 100.0)
    depth = _depth_from_score(int(score))

    evidence = []
    if data_refs > 0:
        evidence.append(f'Contains {data_refs} data reference(s)')
    if framework_hits > 0:
        evidence.append(f'References {framework_hits} strategic framework(s)')

    return JustificationResult(
        score=score,
        depth_label=depth,
        evidence=evidence,
        feedback=f'Template-based assessment (word count: {word_count}).',
    )

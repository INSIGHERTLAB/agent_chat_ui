from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from elia_chat.research_models import ChatContext, ResearchInfo


def normalize_research_for_save(
    research: ResearchInfo,
    thread_id: str,
) -> tuple[ResearchInfo, list[str]]:
    fixed = replace(research)
    warnings: list[str] = []

    if not fixed.research_id.strip():
        fixed.research_id = f"research_{thread_id.replace('-', '_')}"
        warnings.append("research_id was empty and has been auto-filled")

    if fixed.version is None or fixed.version < 1:
        fixed.version = 1
        warnings.append("version was empty/invalid and has been set to 1")

    if not fixed.title.strip():
        fixed.title = fixed.research_id
        warnings.append("title was empty and has been auto-filled")

    if not fixed.goal.strip():
        fixed.goal = "Collect discovery insights for this interview"
        warnings.append("goal was empty and has been auto-filled")

    if not fixed.product_name.strip():
        fixed.product_name = "Unknown product"
        warnings.append("product_name was empty and has been auto-filled")

    if not fixed.segment.strip():
        fixed.segment = "Unknown segment"
        warnings.append("segment was empty and has been auto-filled")

    if fixed.fit_criteria is None:
        fixed.fit_criteria = []

    if fixed.questions is None:
        fixed.questions = []

    return fixed, warnings


def normalize_context(context: ChatContext) -> ChatContext:
    fixed = replace(context)
    if not fixed.source:
        fixed.source = "telegram"
    return fixed


def utc_now_short() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class ResearchQuestionDTO:
    position: int
    text: str
    goal: str


@dataclass
class ResearchInfo:
    research_id: str = ""
    profile_version_id: str | None = None
    version: int | None = None

    title: str = ""
    description: str | None = None
    goal: str = ""
    hypothesis: str | None = None

    product_name: str = ""
    company_name: str | None = None
    company_context: str | None = None

    segment: str = ""
    problem_context: str | None = None
    fit_criteria: list[str] = field(default_factory=list)

    contact_origin: str | None = None
    questions: list[ResearchQuestionDTO] = field(default_factory=list)


@dataclass
class ChatContext:
    source: str = "telegram"
    phone: str = ""
    peer: str = ""
    chat_id: str | None = None


@dataclass
class ThreadMessage:
    role: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreadState:
    thread_id: str
    research: ResearchInfo = field(default_factory=ResearchInfo)
    context: ChatContext = field(default_factory=ChatContext)
    messages: list[ThreadMessage] = field(default_factory=list)
    started: bool = False
    started_research_id: str | None = None
    last_saved_at: str | None = None
    research_saved: bool = False

    @property
    def title(self) -> str:
        if self.research.title:
            return self.research.title
        if self.research.research_id:
            return self.research.research_id
        return "Untitled thread"


@dataclass
class AppState:
    threads: list[ThreadState] = field(default_factory=list)
    selected_thread_id: str | None = None



def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def thread_to_dict(thread: ThreadState) -> dict[str, Any]:
    return asdict(thread)


def thread_from_dict(data: dict[str, Any]) -> ThreadState:
    research_raw = data.get("research", {})
    questions = [
        ResearchQuestionDTO(**q)
        for q in research_raw.get("questions", [])
        if isinstance(q, dict)
    ]
    research = ResearchInfo(
        research_id=research_raw.get("research_id", ""),
        profile_version_id=research_raw.get("profile_version_id"),
        version=research_raw.get("version"),
        title=research_raw.get("title", ""),
        description=research_raw.get("description"),
        goal=research_raw.get("goal", ""),
        hypothesis=research_raw.get("hypothesis"),
        product_name=research_raw.get("product_name", ""),
        company_name=research_raw.get("company_name"),
        company_context=research_raw.get("company_context"),
        segment=research_raw.get("segment", ""),
        problem_context=research_raw.get("problem_context"),
        fit_criteria=list(research_raw.get("fit_criteria", [])),
        contact_origin=research_raw.get("contact_origin"),
        questions=questions,
    )
    context_raw = data.get("context", {})
    context = ChatContext(
        source=context_raw.get("source", "telegram"),
        phone=context_raw.get("phone", ""),
        peer=context_raw.get("peer", ""),
        chat_id=context_raw.get("chat_id"),
    )
    messages = [
        ThreadMessage(
            role=m.get("role", "assistant"),
            text=m.get("text", ""),
            meta=m.get("meta", {}),
        )
        for m in data.get("messages", [])
        if isinstance(m, dict)
    ]
    return ThreadState(
        thread_id=data.get("thread_id", "thread-unknown"),
        research=research,
        context=context,
        messages=messages,
        started=bool(data.get("started", False)),
        started_research_id=data.get("started_research_id"),
        last_saved_at=data.get("last_saved_at"),
        research_saved=bool(data.get("research_saved", False)),
    )

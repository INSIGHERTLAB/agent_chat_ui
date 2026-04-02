from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from elia_chat.research_models import (
    AppState,
    ChatContext,
    ResearchInfo,
    ResearchQuestionDTO,
    ThreadState,
    thread_from_dict,
    thread_to_dict,
)


class LocalStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("APP_STATE_PATH", "./data/state.json"))

    def load(self) -> AppState:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return self._bootstrap()
        except json.JSONDecodeError:
            return self._bootstrap()

        threads = [
            self._apply_thread_defaults(thread_from_dict(item))
            for item in raw.get("threads", [])
            if isinstance(item, dict)
        ]
        if not threads:
            return self._bootstrap()

        state = AppState(threads=threads, selected_thread_id=raw.get("selected_thread_id"))
        if not state.selected_thread_id:
            state.selected_thread_id = state.threads[0].thread_id
        return state

    def save(self, state: AppState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "threads": [thread_to_dict(t) for t in state.threads],
            "selected_thread_id": state.selected_thread_id,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def new_thread(self) -> ThreadState:
        thread_id = f"thread-{uuid4().hex[:8]}"
        research_id = f"research_{thread_id.replace('-', '_')}"
        return ThreadState(
            thread_id=thread_id,
            research=ResearchInfo(
                research_id=research_id,
                profile_version_id="00000000-0000-0000-0000-000000000000",
                version=1,
                title=f"New research {research_id[-8:]}",
                description="Interview script for early discovery calls",
                goal="Collect discovery insights for this interview",
                hypothesis="Users waste time on manual repetitive workflow",
                product_name="Unknown product",
                company_name="Unknown company",
                company_context="B2B SaaS, early stage",
                segment="Unknown segment",
                problem_context="Manual process is slow and error-prone",
                fit_criteria=[
                    "Has clear pain point",
                    "Uses alternative solution now",
                ],
                contact_origin="inbound_demo",
                questions=[
                    ResearchQuestionDTO(
                        position=1,
                        text="Расскажите, как вы сейчас решаете эту задачу?",
                        goal="Понять текущий процесс",
                    ),
                    ResearchQuestionDTO(
                        position=2,
                        text="Что в этом процессе раздражает больше всего?",
                        goal="Выявить ключевую боль",
                    ),
                ],
            ),
            context=ChatContext(source="telegram", phone="+70000000000", peer="demo_peer"),
        )

    def _bootstrap(self) -> AppState:
        thread = self.new_thread()
        return AppState(threads=[thread], selected_thread_id=thread.thread_id)

    def _apply_thread_defaults(self, thread: ThreadState) -> ThreadState:
        if not thread.research.research_id:
            default = self.new_thread()
            thread.research.research_id = default.research.research_id
        if not thread.research.title:
            thread.research.title = f"New research {thread.research.research_id[-8:]}"
        if not thread.research.goal:
            thread.research.goal = "Collect discovery insights for this interview"
        if not thread.research.description:
            thread.research.description = "Interview script for early discovery calls"
        if not thread.research.hypothesis:
            thread.research.hypothesis = "Users waste time on manual repetitive workflow"
        if not thread.research.product_name:
            thread.research.product_name = "Unknown product"
        if not thread.research.company_name:
            thread.research.company_name = "Unknown company"
        if not thread.research.company_context:
            thread.research.company_context = "B2B SaaS, early stage"
        if not thread.research.segment:
            thread.research.segment = "Unknown segment"
        if not thread.research.problem_context:
            thread.research.problem_context = "Manual process is slow and error-prone"
        if not thread.research.contact_origin:
            thread.research.contact_origin = "inbound_demo"
        if not thread.research.questions:
            thread.research.questions = [
                ResearchQuestionDTO(
                    position=1,
                    text="Расскажите, как вы сейчас решаете эту задачу?",
                    goal="Понять текущий процесс",
                )
            ]
        if not thread.research.fit_criteria:
            thread.research.fit_criteria = ["Has clear pain point"]
        if not thread.context.phone:
            thread.context.phone = "+70000000000"
        if not thread.context.peer:
            thread.context.peer = "demo_peer"
        return thread

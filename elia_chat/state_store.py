from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from elia_chat.research_models import AppState, ThreadState, thread_from_dict, thread_to_dict


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

        threads = [thread_from_dict(item) for item in raw.get("threads", []) if isinstance(item, dict)]
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
        return ThreadState(thread_id=f"thread-{uuid4().hex[:8]}")

    def _bootstrap(self) -> AppState:
        thread = self.new_thread()
        return AppState(threads=[thread], selected_thread_id=thread.thread_id)

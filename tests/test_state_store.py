from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from elia_chat.research_models import AppState, ThreadState
from elia_chat.state_store import LocalStore


class LocalStoreTests(unittest.TestCase):
    def test_new_thread_has_prefilled_research_data(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            store = LocalStore(str(path))
            thread = store.new_thread()

            self.assertTrue(thread.research.research_id.startswith("research_thread_"))
            self.assertEqual(thread.research.version, 1)
            self.assertTrue(thread.research.questions)
            self.assertTrue(thread.research.fit_criteria)
            self.assertTrue(thread.research.description)
            self.assertTrue(thread.research.hypothesis)
            self.assertTrue(thread.research.company_name)

    def test_thread_title_fallback_order(self) -> None:
        thread = ThreadState(thread_id="t1")
        self.assertEqual(thread.title, "Untitled thread")

        thread.research.research_id = "research_42"
        self.assertEqual(thread.title, "research_42")

        thread.research.title = "Discovery interview"
        self.assertEqual(thread.title, "Discovery interview")

    def test_bootstrap_when_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            store = LocalStore(str(path))
            state = store.load()

            self.assertEqual(len(state.threads), 1)
            self.assertIsNotNone(state.selected_thread_id)

    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            store = LocalStore(str(path))

            state = AppState(
                threads=[
                    ThreadState(thread_id="thread-1", started=True, started_research_id="r1"),
                    ThreadState(thread_id="thread-2"),
                ],
                selected_thread_id="thread-2",
            )
            store.save(state)

            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["selected_thread_id"], "thread-2")

            loaded = store.load()
            self.assertEqual(len(loaded.threads), 2)
            self.assertEqual(loaded.selected_thread_id, "thread-2")
            self.assertEqual(loaded.threads[0].started_research_id, "r1")

    def test_load_applies_defaults_to_legacy_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "selected_thread_id": "thread-x",
                        "threads": [{"thread_id": "thread-x", "research": {}, "context": {}}],
                    }
                ),
                encoding="utf-8",
            )
            store = LocalStore(str(path))
            state = store.load()
            thread = state.threads[0]
            self.assertTrue(thread.research.research_id)
            self.assertTrue(thread.research.goal)
            self.assertTrue(thread.context.phone)
            self.assertTrue(thread.research.problem_context)


if __name__ == "__main__":
    unittest.main()

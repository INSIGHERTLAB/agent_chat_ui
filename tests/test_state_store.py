from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from elia_chat.research_models import AppState, ThreadState
from elia_chat.state_store import LocalStore


class LocalStoreTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

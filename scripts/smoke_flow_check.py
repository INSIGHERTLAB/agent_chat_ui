from __future__ import annotations

"""Lightweight smoke check for prototype flow components.

This does not start Textual UI, but validates key non-UI flow pieces:
- local state bootstrap/save/load
- prompt payload conversion and guards
- agent pipeline parsing semantics
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from elia_chat.research_models import AppState, ResearchInfo, ThreadState
from elia_chat.services import parse_agent_pipeline
from elia_chat.state_store import LocalStore


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "state.json"
        store = LocalStore(str(path))

        state = store.load()
        assert len(state.threads) == 1, "bootstrap thread missing"

        state.threads[0].research = ResearchInfo(
            research_id="research_smoke_001",
            title="Smoke title",
            goal="Smoke goal",
            product_name="Smoke product",
            segment="B2B",
        )
        store.save(state)

        loaded = store.load()
        assert loaded.threads[0].research.research_id == "research_smoke_001"

    pipeline = {
        "pipeline": [
            {"type": "trigger", "trigger": ""},
            {
                "type": "batch",
                "messages": [
                    {"type": "text", "text": "hello"},
                    {"type": "sticker"},
                ],
            },
        ]
    }
    parsed = parse_agent_pipeline(pipeline)
    assert len(parsed) == 2
    assert parsed[0].text == "hello"
    assert parsed[1].text == "[sticker]"

    print(json.dumps({"ok": True, "checks": ["state", "pipeline"]}))


if __name__ == "__main__":
    main()

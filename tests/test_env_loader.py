from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from elia_chat.env_loader import load_dotenv


class EnvLoaderTests(unittest.TestCase):
    def test_load_dotenv_sets_values(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dotenv = Path(td) / ".env"
            dotenv.write_text("AGENTS__INTERVIEW__URL=http://localhost:5025\nAGENT_ENDPOINT=interview\n", encoding="utf-8")

            os.environ.pop("AGENTS__INTERVIEW__URL", None)
            os.environ.pop("AGENT_ENDPOINT", None)

            load_dotenv(dotenv)
            self.assertEqual(os.getenv("AGENTS__INTERVIEW__URL"), "http://localhost:5025")
            self.assertEqual(os.getenv("AGENT_ENDPOINT"), "interview")

    def test_existing_env_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dotenv = Path(td) / ".env"
            dotenv.write_text("AGENTS__INTERVIEW__URL=http://localhost:5025\n", encoding="utf-8")

            os.environ["AGENTS__INTERVIEW__URL"] = "http://already-set:9999"
            load_dotenv(dotenv)
            self.assertEqual(os.getenv("AGENTS__INTERVIEW__URL"), "http://already-set:9999")


if __name__ == "__main__":
    unittest.main()

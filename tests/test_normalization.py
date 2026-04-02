from __future__ import annotations

import unittest

from elia_chat.normalization import normalize_context, normalize_research_for_save
from elia_chat.research_models import ChatContext, ResearchInfo


class NormalizationTests(unittest.TestCase):
    def test_normalize_research_autofills_required_fields(self) -> None:
        research = ResearchInfo()
        fixed, warnings = normalize_research_for_save(research, "thread-abc123")

        self.assertTrue(fixed.research_id.startswith("research_thread_abc123"))
        self.assertEqual(fixed.version, 1)
        self.assertEqual(fixed.title, fixed.research_id)
        self.assertTrue(fixed.goal)
        self.assertEqual(fixed.product_name, "Unknown product")
        self.assertEqual(fixed.segment, "Unknown segment")
        self.assertGreaterEqual(len(warnings), 1)

    def test_normalize_context_defaults_source(self) -> None:
        context = ChatContext(source="", phone="", peer="")
        fixed = normalize_context(context)
        self.assertEqual(fixed.source, "telegram")


if __name__ == "__main__":
    unittest.main()

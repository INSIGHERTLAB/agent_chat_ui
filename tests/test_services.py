from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, patch

from elia_chat.research_models import ChatContext, ResearchInfo
from elia_chat.services import AgentClient, PromptServiceClient, parse_agent_pipeline


class AgentClientTests(unittest.TestCase):
    def test_agent_url_priority(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AGENTS__INTERVIEW__URL": "http://priority.local:9000",
                "AGENT_URL": "http://fallback.local:3000",
                "AGENT_ENDPOINT": "interview",
            },
            clear=False,
        ):
            client = AgentClient()
            self.assertEqual(client.url, "http://priority.local:9000/interview")
            self.assertEqual(client.base_url_source, "AGENTS__INTERVIEW__URL")
            self.assertTrue(client.has_base_url_conflict)

    def test_agent_url_fallback(self) -> None:
        with patch.dict(os.environ, {"AGENTS__INTERVIEW__URL": "", "AGENT_URL": "http://fallback.local:3000"}, clear=False):
            client = AgentClient()
            self.assertEqual(client.url, "http://fallback.local:3000/interview")
            self.assertEqual(client.base_url_source, "AGENT_URL")
            self.assertFalse(client.has_base_url_conflict)

    def test_build_payload_contract(self) -> None:
        client = AgentClient()
        payload = client.build_payload(
            research_id="research_1",
            context=ChatContext(source="telegram", phone="+100", peer="42", chat_id=None),
            message_type="first_message",
            content=[{"type": "text", "text": "hello", "urls": None}],
        )
        income = payload["income"]
        self.assertEqual(income["message_type"], "first_message")
        self.assertEqual(income["research_id"], "research_1")
        self.assertEqual(income["message"]["context"]["peer"], "42")

    def test_send_text_rejects_unknown_message_type(self) -> None:
        client = AgentClient()
        with self.assertRaises(ValueError):
            import asyncio
            asyncio.run(
                client.send_text(
                    message_text="x",
                    research_id="r1",
                    context=ChatContext(source="telegram", phone="", peer="", chat_id=None),
                    message_type="unknown_type",
                )
            )


class PromptServiceClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_research_research_id_mismatch_guard(self) -> None:
        client = PromptServiceClient()
        with self.assertRaises(ValueError):
            await client.save_research(ResearchInfo(research_id=""))

    async def test_exists_endpoint(self) -> None:
        client = PromptServiceClient()
        with patch("elia_chat.services._json_request", new=AsyncMock(return_value={"exists": True})) as mocked:
            result = await client.prompt_exists("r1")
            self.assertEqual(result["exists"], True)
            mocked.assert_awaited_once()

    async def test_versions_endpoint(self) -> None:
        client = PromptServiceClient()
        with patch("elia_chat.services._json_request", new=AsyncMock(return_value={"versions": [1, 2]})) as mocked:
            result = await client.versions("r1")
            self.assertEqual(result["versions"], [1, 2])
            args, kwargs = mocked.await_args
            self.assertEqual(args[0], "GET")
            self.assertTrue(args[1].endswith("/researches/r1/prompt/versions"))
            self.assertEqual(kwargs, {})


class AgentClientAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_text_uses_empty_content_for_generator_modes(self) -> None:
        client = AgentClient()
        with patch("elia_chat.services._json_request", new=AsyncMock(return_value={"ok": True})) as mocked:
            await client.send_text(
                message_text="",
                research_id="r1",
                context=ChatContext(source="telegram", phone="", peer="", chat_id=None),
                message_type="ping_message",
            )
            args, _kwargs = mocked.await_args
            payload = args[2]
            self.assertEqual(payload["income"]["message_type"], "ping_message")
            self.assertEqual(payload["income"]["message"]["content"], [])


class PipelineParserTests(unittest.TestCase):
    def test_ignores_trigger_and_parses_batch(self) -> None:
        payload = {
            "research_id": "r1",
            "pipeline": [
                {"type": "trigger", "trigger": ""},
                {
                    "type": "batch",
                    "messages": [
                        {"type": "text", "text": "hello", "action": {"type": "typing", "duration_seconds": 2}},
                        {"type": "image", "action": {"type": "typing", "duration_seconds": 1}},
                    ],
                },
            ],
        }

        items = parse_agent_pipeline(payload)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].text, "hello")
        self.assertEqual(items[0].meta.get("action"), "typing ~2s")
        self.assertEqual(items[1].text, "[image]")

    def test_handles_invalid_shapes(self) -> None:
        self.assertEqual(parse_agent_pipeline({"pipeline": "oops"}), [])
        self.assertEqual(parse_agent_pipeline({"pipeline": ["bad-step"]}), [])


if __name__ == "__main__":
    unittest.main()

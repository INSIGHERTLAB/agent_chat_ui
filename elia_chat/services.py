from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from urllib import request, error

from elia_chat.research_models import ChatContext, ResearchInfo, ThreadMessage


class PromptServiceClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("PROMPT_SERVICE_URL", "http://localhost:8001").rstrip("/")

    async def save_research(self, research: ResearchInfo) -> dict:
        if not research.research_id:
            raise ValueError("research_id is required")
        body = _research_to_payload(research)
        path_id = research.research_id
        if body.get("research_id") != path_id:
            raise ValueError("research_id in path and body must match")
        url = f"{self.base_url}/researches/{path_id}/prompt"
        return await _json_request("PUT", url, body)

    async def load_research(self, research_id: str) -> dict:
        if not research_id:
            raise ValueError("research_id is required")
        url = f"{self.base_url}/researches/{research_id}/prompt"
        return await _json_request("GET", url)

    async def prompt_exists(self, research_id: str) -> dict:
        url = f"{self.base_url}/researches/{research_id}/prompt/exists"
        return await _json_request("GET", url)

    async def latest_version(self, research_id: str) -> dict:
        url = f"{self.base_url}/researches/{research_id}/prompt/latest-version"
        return await _json_request("GET", url)

    async def versions(self, research_id: str) -> dict:
        url = f"{self.base_url}/researches/{research_id}/prompt/versions"
        return await _json_request("GET", url)

    async def version_by_number(self, research_id: str, version: int) -> dict:
        url = f"{self.base_url}/researches/{research_id}/prompt/versions/{version}"
        return await _json_request("GET", url)


class AgentClient:
    def __init__(self) -> None:
        interview_url = os.getenv("AGENTS__INTERVIEW__URL")
        fallback_url = os.getenv("AGENT_URL")
        self.has_base_url_conflict = bool(
            interview_url and fallback_url and interview_url.rstrip("/") != fallback_url.rstrip("/")
        )
        if interview_url:
            base = interview_url
            self.base_url_source = "AGENTS__INTERVIEW__URL"
        elif fallback_url:
            base = fallback_url
            self.base_url_source = "AGENT_URL"
        else:
            base = "http://localhost:3000"
            self.base_url_source = "default"
        endpoint = os.getenv("AGENT_ENDPOINT", "interview")
        self.base_url = base.rstrip("/")
        self.endpoint = endpoint.lstrip("/")
        self.url = f"{self.base_url}/{self.endpoint}"

    async def send_text(
        self,
        message_text: str,
        research_id: str,
        context: ChatContext,
        is_first_message: bool,
    ) -> dict:
        payload = self.build_payload(
            research_id=research_id,
            context=context,
            is_first_message=is_first_message,
            content=[{"type": "text", "text": message_text, "urls": None}],
        )
        return await _json_request("POST", self.url, payload)

    def build_payload(
        self,
        research_id: str,
        context: ChatContext,
        is_first_message: bool,
        content: list[dict],
    ) -> dict:
        return {
            "income": {
                "message_type": "first_message" if is_first_message else "user_reply",
                "research_id": research_id,
                "message": {
                    "context": {
                        "source": context.source,
                        "phone": context.phone,
                        "peer": context.peer,
                        "chat_id": context.chat_id,
                    },
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "external_message_id": None,
                    "content": content,
                },
            }
        }


def parse_agent_pipeline(response: dict) -> list[ThreadMessage]:
    out: list[ThreadMessage] = []
    pipeline = response.get("pipeline", [])
    if not isinstance(pipeline, list):
        return out

    for step in pipeline:
        if not isinstance(step, dict):
            continue
        if step.get("type") != "batch":
            continue
        messages = step.get("messages", [])
        if not isinstance(messages, list):
            continue
        for message in messages:
            if not isinstance(message, dict):
                continue
            mtype = message.get("type")
            action = message.get("action") or {}
            action_label = ""
            if action.get("type") == "typing":
                duration = action.get("duration_seconds")
                action_label = f"typing ~{duration}s" if duration else "typing"

            if mtype == "text":
                text = message.get("text", "")
                meta = {"action": action_label} if action_label else {}
                out.append(ThreadMessage(role="assistant", text=text, meta=meta))
            elif mtype in {"voice", "image", "sticker"}:
                out.append(
                    ThreadMessage(
                        role="assistant",
                        text=f"[{mtype}]",
                        meta={"action": action_label} if action_label else {},
                    )
                )
    return out


def _research_to_payload(research: ResearchInfo) -> dict:
    return {
        "research_id": research.research_id,
        "profile_version_id": research.profile_version_id,
        "version": research.version,
        "title": research.title,
        "description": research.description,
        "goal": research.goal,
        "hypothesis": research.hypothesis,
        "product_name": research.product_name,
        "company_name": research.company_name,
        "company_context": research.company_context,
        "segment": research.segment,
        "problem_context": research.problem_context,
        "fit_criteria": research.fit_criteria,
        "contact_origin": research.contact_origin,
        "questions": [
            {"position": q.position, "text": q.text, "goal": q.goal}
            for q in research.questions
        ],
    }


async def _json_request(method: str, url: str, body: dict | None = None) -> dict:
    return await asyncio.to_thread(_json_request_sync, method, url, body)


def _json_request_sync(method: str, url: str, body: dict | None = None) -> dict:
    payload = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        payload = json.dumps(body).encode("utf-8")

    req = request.Request(url=url, method=method.upper(), data=payload, headers=headers)
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

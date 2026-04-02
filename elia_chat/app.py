from __future__ import annotations

from dataclasses import dataclass

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Footer, Header, Input, Label, OptionList, Static, TextArea

from elia_chat.research_models import (
    AppState,
    ChatContext,
    ResearchInfo,
    ResearchQuestionDTO,
    ThreadMessage,
    ThreadState,
    now_iso,
)
from elia_chat.services import AgentClient, PromptServiceClient, parse_agent_pipeline
from elia_chat.state_store import LocalStore


class ThreadList(OptionList):
    class ThreadSelected(Message):
        def __init__(self, thread_id: str) -> None:
            self.thread_id = thread_id
            super().__init__()

    @on(OptionList.OptionSelected)
    def selected(self, event: OptionList.OptionSelected) -> None:
        option = self.get_option_at_index(event.option_index)
        self.post_message(self.ThreadSelected(str(option.id)))


class ResearchSidebar(Vertical):
    class SaveRequested(Message):
        pass

    class LoadRequested(Message):
        pass

    FIELDS = [
        "research_id",
        "profile_version_id",
        "version",
        "title",
        "description",
        "goal",
        "hypothesis",
        "product_name",
        "company_name",
        "company_context",
        "segment",
        "problem_context",
        "contact_origin",
        "phone",
        "peer",
        "chat_id",
    ]

    def compose(self) -> ComposeResult:
        yield Label("Research", classes="panel-title")
        for field in self.FIELDS:
            yield Input(placeholder=field, id=f"field-{field}")

        fit = TextArea(id="field-fit_criteria")
        fit.border_title = "fit_criteria (one per line)"
        yield fit

        questions = TextArea(id="field-questions")
        questions.border_title = "questions (text || goal)"
        yield questions

        yield Label("metadata", id="metadata")
        yield Button("Save research", id="save-research", variant="success")
        yield Button("Load by ID", id="load-research")

    def fill(self, thread: ThreadState) -> None:
        r = thread.research
        c = thread.context
        values = {
            "research_id": r.research_id,
            "profile_version_id": r.profile_version_id or "",
            "version": "" if r.version is None else str(r.version),
            "title": r.title,
            "description": r.description or "",
            "goal": r.goal,
            "hypothesis": r.hypothesis or "",
            "product_name": r.product_name,
            "company_name": r.company_name or "",
            "company_context": r.company_context or "",
            "segment": r.segment,
            "problem_context": r.problem_context or "",
            "contact_origin": r.contact_origin or "",
            "phone": c.phone,
            "peer": c.peer,
            "chat_id": c.chat_id or "",
        }
        for key, value in values.items():
            self.query_one(f"#field-{key}", Input).value = value

        self.query_one("#field-fit_criteria", TextArea).text = "\n".join(r.fit_criteria)
        self.query_one("#field-questions", TextArea).text = "\n".join(
            f"{q.text} || {q.goal}" for q in sorted(r.questions, key=lambda x: x.position)
        )
        self._update_metadata(thread)

    def to_models(self) -> tuple[ResearchInfo, ChatContext]:
        data = {f: self.query_one(f"#field-{f}", Input).value.strip() for f in self.FIELDS}

        fit_criteria = [line.strip() for line in self.query_one("#field-fit_criteria", TextArea).text.splitlines() if line.strip()]
        questions: list[ResearchQuestionDTO] = []
        for idx, line in enumerate(self.query_one("#field-questions", TextArea).text.splitlines(), start=1):
            if not line.strip():
                continue
            if "||" in line:
                text, goal = [part.strip() for part in line.split("||", 1)]
            else:
                text, goal = line.strip(), ""
            questions.append(ResearchQuestionDTO(position=idx, text=text, goal=goal))

        research = ResearchInfo(
            research_id=data["research_id"],
            profile_version_id=data["profile_version_id"] or None,
            version=int(data["version"]) if data["version"] else None,
            title=data["title"],
            description=data["description"] or None,
            goal=data["goal"],
            hypothesis=data["hypothesis"] or None,
            product_name=data["product_name"],
            company_name=data["company_name"] or None,
            company_context=data["company_context"] or None,
            segment=data["segment"],
            problem_context=data["problem_context"] or None,
            fit_criteria=fit_criteria,
            contact_origin=data["contact_origin"] or None,
            questions=questions,
        )
        context = ChatContext(
            source="telegram",
            phone=data["phone"],
            peer=data["peer"],
            chat_id=data["chat_id"] or None,
        )
        return research, context

    def _update_metadata(self, thread: ThreadState) -> None:
        meta = (
            f"version: {thread.research.version} | "
            f"profile_version_id: {thread.research.profile_version_id} | "
            f"last_saved_at: {thread.last_saved_at or '-'}"
        )
        self.query_one("#metadata", Label).update(meta)

    @on(Button.Pressed, "#save-research")
    def save_pressed(self) -> None:
        self.post_message(self.SaveRequested())

    @on(Button.Pressed, "#load-research")
    def load_pressed(self) -> None:
        self.post_message(self.LoadRequested())


class AgentResearchApp(App[None]):
    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    #threads { width: 28; border: round $primary; }
    #chat { width: 1fr; border: round $accent; }
    #sidebar { width: 44; border: round $secondary; overflow-y: auto; }
    #messages { height: 1fr; border: round $surface; overflow-y: auto; }
    #composer { height: 7; }
    .panel-title { text-style: bold; }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_thread", "New thread"),
        Binding("ctrl+s", "save_state", "Save state"),
        Binding("ctrl+j", "send_from_binding", "Send"),
        Binding("f1", "focus('composer')", "Focus composer"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.store = LocalStore()
        self.state: AppState = self.store.load()
        self.prompt_client = PromptServiceClient()
        self.agent_client = AgentClient()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            yield ThreadList(id="threads")
            with Vertical(id="chat"):
                yield Static(id="messages")
                composer = TextArea(id="composer")
                composer.border_title = "Message"
                yield composer
                yield Button("Send", id="send", variant="primary")
            yield ResearchSidebar(id="sidebar")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_threads()
        self.load_thread_to_ui(self.current_thread)

    @property
    def current_thread(self) -> ThreadState:
        selected = self.state.selected_thread_id
        for thread in self.state.threads:
            if thread.thread_id == selected:
                return thread
        thread = self.state.threads[0]
        self.state.selected_thread_id = thread.thread_id
        return thread

    def refresh_threads(self) -> None:
        widget = self.query_one(ThreadList)
        widget.clear_options()
        for thread in self.state.threads:
            widget.add_option(thread.title, id=thread.thread_id)
        current = self.current_thread.thread_id
        for idx, option in enumerate(widget.options):
            if str(option.id) == current:
                widget.highlighted = idx
                break

    def load_thread_to_ui(self, thread: ThreadState) -> None:
        sidebar = self.query_one(ResearchSidebar)
        sidebar.fill(thread)
        self.render_messages(thread.messages)

    def render_messages(self, messages: list[ThreadMessage]) -> None:
        lines: list[str] = []
        for message in messages:
            prefix = "You" if message.role == "user" else "Agent"
            action = message.meta.get("action")
            if action:
                lines.append(f"[{prefix} | {action}] {message.text}")
            else:
                lines.append(f"[{prefix}] {message.text}")
        self.query_one("#messages", Static).update("\n\n".join(lines) or "No messages yet.")

    def persist_from_sidebar(self) -> None:
        sidebar = self.query_one(ResearchSidebar)
        research, context = sidebar.to_models()
        thread = self.current_thread
        thread.research = research
        thread.context = context

    @on(ThreadList.ThreadSelected)
    def thread_selected(self, event: ThreadList.ThreadSelected) -> None:
        self.persist_from_sidebar()
        self.state.selected_thread_id = event.thread_id
        self.load_thread_to_ui(self.current_thread)
        self.store.save(self.state)

    async def action_new_thread(self) -> None:
        self.persist_from_sidebar()
        thread = self.store.new_thread()
        self.state.threads.insert(0, thread)
        self.state.selected_thread_id = thread.thread_id
        self.refresh_threads()
        self.load_thread_to_ui(thread)
        self.store.save(self.state)

    async def action_save_state(self) -> None:
        self.persist_from_sidebar()
        self.store.save(self.state)
        self.notify("Local state saved")

    @on(ResearchSidebar.SaveRequested)
    async def save_research(self) -> None:
        self.persist_from_sidebar()
        thread = self.current_thread
        try:
            await self.prompt_client.save_research(thread.research)
        except Exception as exc:
            self.notify(str(exc), severity="error", title="Save failed")
            return
        thread.last_saved_at = now_iso()
        self.query_one(ResearchSidebar)._update_metadata(thread)
        self.refresh_threads()
        self.store.save(self.state)
        self.notify("Research saved")

    @on(ResearchSidebar.LoadRequested)
    async def load_research(self) -> None:
        self.persist_from_sidebar()
        thread = self.current_thread
        research_id = thread.research.research_id
        if not research_id:
            self.notify("Fill research_id first", severity="warning")
            return

        try:
            payload = await self.prompt_client.load_research(research_id)
        except Exception as exc:
            self.notify(str(exc), severity="error", title="Load failed")
            return

        thread.research = self._research_from_payload(payload)
        self.load_thread_to_ui(thread)
        self.refresh_threads()
        self.store.save(self.state)
        self.notify("Research loaded")

    @on(Button.Pressed, "#send")
    def send_pressed(self) -> None:
        self.send_message()

    def action_send_from_binding(self) -> None:
        self.send_message()

    @work
    async def send_message(self) -> None:
        self.persist_from_sidebar()
        thread = self.current_thread
        composer = self.query_one("#composer", TextArea)
        text = composer.text.strip()
        if not text:
            self.notify("Message is empty", severity="warning")
            return
        if not thread.research.research_id:
            self.notify("research_id is required", severity="warning")
            return

        composer.clear()
        thread.messages.append(ThreadMessage(role="user", text=text))
        self.render_messages(thread.messages)

        try:
            response = await self.agent_client.send_text(
                message_text=text,
                research_id=thread.research.research_id,
                context=thread.context,
                is_first_message=not thread.started,
            )
        except Exception as exc:
            self.notify(str(exc), severity="error", title="Agent failed")
            return

        thread.started = True
        thread.messages.extend(parse_agent_pipeline(response))
        self.render_messages(thread.messages)
        self.store.save(self.state)

    def _research_from_payload(self, payload: dict) -> ResearchInfo:
        if "prompt" in payload and isinstance(payload["prompt"], dict):
            payload = payload["prompt"]

        questions = []
        for idx, item in enumerate(payload.get("questions", []), start=1):
            questions.append(
                ResearchQuestionDTO(
                    position=item.get("position", idx),
                    text=item.get("text", ""),
                    goal=item.get("goal", ""),
                )
            )

        return ResearchInfo(
            research_id=payload.get("research_id", ""),
            profile_version_id=payload.get("profile_version_id"),
            version=payload.get("version"),
            title=payload.get("title", ""),
            description=payload.get("description"),
            goal=payload.get("goal", ""),
            hypothesis=payload.get("hypothesis"),
            product_name=payload.get("product_name", ""),
            company_name=payload.get("company_name"),
            company_context=payload.get("company_context"),
            segment=payload.get("segment", ""),
            problem_context=payload.get("problem_context"),
            fit_criteria=list(payload.get("fit_criteria", [])),
            contact_origin=payload.get("contact_origin"),
            questions=questions,
        )


if __name__ == "__main__":
    AgentResearchApp().run()

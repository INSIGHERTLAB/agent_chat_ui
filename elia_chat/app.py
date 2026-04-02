from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Footer, Header, Input, Label, OptionList, RichLog, TextArea

from elia_chat.research_models import (
    AppState,
    ChatContext,
    ResearchInfo,
    ResearchQuestionDTO,
    ThreadMessage,
    ThreadState,
    now_iso,
)
from elia_chat.normalization import normalize_context, normalize_research_for_save
from elia_chat.services import AgentClient, PromptServiceClient, parse_agent_pipeline
from elia_chat.state_store import LocalStore


class ThreadList(OptionList):
    class ThreadSelected(Message):
        def __init__(self, option_index: int) -> None:
            self.option_index = option_index
            super().__init__()

    @on(OptionList.OptionSelected)
    def selected(self, event: OptionList.OptionSelected) -> None:
        self.post_message(self.ThreadSelected(event.option_index))


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
        yield Label("Research info", classes="section-title")
        for field in self.FIELDS[:13]:
            yield Input(placeholder=field, id=f"field-{field}")

        yield Label("Chat context", classes="section-title")
        for field in self.FIELDS[13:]:
            yield Input(placeholder=field, id=f"field-{field}")

        fit = TextArea(id="field-fit_criteria")
        fit.border_title = "fit_criteria (one per line)"
        fit.styles.height = 6
        yield fit

        questions = TextArea(id="field-questions")
        questions.border_title = "questions (text || goal)"
        questions.styles.height = 8
        yield questions

        yield Label("metadata", id="metadata")
        with Horizontal(id="research-actions"):
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
        version_raw = data["version"]
        version: int | None = None
        if version_raw:
            try:
                version = int(version_raw)
            except ValueError:
                self.notify(
                    "Field 'version' must be an integer. Value ignored.",
                    title="Invalid version",
                    severity="warning",
                )
                version = None

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
            version=version,
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
    #threads-panel { width: 28; }
    #new-thread-btn { width: 1fr; margin: 0 0 1 0; }
    #chat { width: 1fr; border: round $accent; }
    #sidebar { width: 44; border: round $secondary; overflow-y: auto; }
    #sidebar Input { width: 1fr; margin-bottom: 1; }
    #sidebar TextArea { width: 1fr; margin-bottom: 1; }
    #sidebar Button { width: 1fr; margin-bottom: 1; }
    #research-actions { height: auto; width: 1fr; }
    #research-actions Button { width: 1fr; margin-right: 1; }
    #sidebar Label { margin-left: 1; }
    #ops-log { height: 7; border: round $panel; }
    #messages { height: 1fr; border: round $surface; overflow-y: auto; }
    #composer { height: 7; }
    .panel-title { text-style: bold; }
    .section-title { text-style: bold italic; color: $text-muted; margin-top: 1; }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_thread", "New thread"),
        Binding("ctrl+s", "save_state", "Save state"),
        Binding("ctrl+j", "send_from_binding", "Send"),
        Binding("f5", "send_first_from_binding", "Send first ping"),
        Binding("f6", "send_reply_from_binding", "Send reply"),
        Binding("f1", "focus('composer')", "Focus composer"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.store = LocalStore()
        self.state: AppState = self.store.load()
        self.prompt_client = PromptServiceClient()
        self.agent_client = AgentClient()
        self.sending = False
        self.status_text = "Ready"
        self.thread_order: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="threads-panel"):
                yield Button("+ New thread", id="new-thread-btn", variant="primary")
                yield ThreadList(id="threads")
            with Vertical(id="chat"):
                yield Label(self.status_text, id="status-line")
                ops_log = RichLog(id="ops-log", wrap=True, auto_scroll=True)
                ops_log.border_title = "Operations"
                yield ops_log
                messages_log = RichLog(id="messages", markup=True, wrap=True, auto_scroll=True)
                messages_log.border_title = "Chat"
                yield messages_log
                composer = TextArea(id="composer")
                composer.border_title = "Message"
                yield composer
                yield Button("Send", id="send", variant="primary")
                yield Button("Send first ping", id="send-first", variant="warning")
                yield Button("Send reply", id="send-reply")
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
        self.thread_order = []
        for thread in self.state.threads:
            widget.add_option(thread.title)
            self.thread_order.append(thread.thread_id)
        current = self.current_thread.thread_id
        for idx, thread_id in enumerate(self.thread_order):
            if thread_id == current:
                widget.highlighted = idx
                break

    def load_thread_to_ui(self, thread: ThreadState) -> None:
        sidebar = self.query_one(ResearchSidebar)
        sidebar.fill(thread)
        self.render_messages(thread.messages)

    def render_messages(self, messages: list[ThreadMessage]) -> None:
        log = self.query_one("#messages", RichLog)
        log.clear()
        if not messages:
            log.write("No messages yet.")
            return
        for message in messages:
            prefix = "You" if message.role == "user" else "Agent"
            is_event = message.text.startswith("[") and message.text.endswith("]")
            if is_event:
                style = "bold magenta"
                prefix = "Event"
            else:
                style = "bold cyan" if message.role == "user" else "bold green"
            action = message.meta.get("action")
            if action:
                log.write(f"[{style}]{prefix}[/] ({action})")
            else:
                log.write(f"[{style}]{prefix}[/]")
            log.write(message.text)
            log.write("")

    def persist_from_sidebar(self) -> None:
        sidebar = self.query_one(ResearchSidebar)
        research, context = sidebar.to_models()
        thread = self.current_thread
        thread.research = research
        thread.context = context

    @on(ThreadList.ThreadSelected)
    def thread_selected(self, event: ThreadList.ThreadSelected) -> None:
        self.persist_from_sidebar()
        if event.option_index < 0 or event.option_index >= len(self.thread_order):
            return
        self.state.selected_thread_id = self.thread_order[event.option_index]
        self.load_thread_to_ui(self.current_thread)
        self.store.save(self.state)
        self._set_status(f"Switched to {self.current_thread.title}")
        self._log_operation(f"Switched thread: {self.current_thread.thread_id}")

    async def action_new_thread(self) -> None:
        self.persist_from_sidebar()
        thread = self.store.new_thread()
        self.state.threads.insert(0, thread)
        self.state.selected_thread_id = thread.thread_id
        self.refresh_threads()
        self.load_thread_to_ui(thread)
        self.store.save(self.state)
        self._set_status("New thread created")
        self._log_operation(f"New thread created: {thread.thread_id}")

    @on(Button.Pressed, "#new-thread-btn")
    async def new_thread_pressed(self) -> None:
        await self.action_new_thread()

    async def action_save_state(self) -> None:
        self.persist_from_sidebar()
        self.refresh_threads()
        self.store.save(self.state)
        self.notify("Local state saved")
        self._log_operation("Local state saved")

    @on(ResearchSidebar.SaveRequested)
    async def save_research(self) -> None:
        self.persist_from_sidebar()
        thread = self.current_thread
        normalized_research, warnings = normalize_research_for_save(
            thread.research, thread.thread_id
        )
        normalized_context = normalize_context(thread.context)
        thread.research = normalized_research
        thread.context = normalized_context
        self.query_one(ResearchSidebar).fill(thread)
        for warning in warnings:
            self.notify(warning, severity="warning", title="Auto-filled")
            self._log_operation(warning)

        self._set_status("Saving research prompt...")
        try:
            response_payload = await self.prompt_client.save_research(thread.research)
        except Exception as exc:
            self.notify(str(exc), severity="error", title="Save failed")
            self._set_status(f"Save failed: {exc}")
            return
        if isinstance(response_payload, dict):
            source = response_payload.get("prompt") if isinstance(response_payload.get("prompt"), dict) else response_payload
            thread.research.version = source.get("version", thread.research.version)
            thread.research.profile_version_id = source.get(
                "profile_version_id", thread.research.profile_version_id
            )
        thread.last_saved_at = now_iso()
        self.query_one(ResearchSidebar)._update_metadata(thread)
        self.refresh_threads()
        self.store.save(self.state)
        self.notify("Research saved")
        self._set_status("Research saved")
        self._log_operation("Research saved to prompt-service")

    @on(ResearchSidebar.LoadRequested)
    async def load_research(self) -> None:
        self.persist_from_sidebar()
        thread = self.current_thread
        research_id = thread.research.research_id
        if not research_id:
            self.notify("Fill research_id first", severity="warning")
            self._set_status("Load skipped: empty research_id")
            return

        self._set_status(f"Loading research {research_id}...")
        try:
            exists_payload = await self.prompt_client.prompt_exists(research_id)
            if isinstance(exists_payload, dict) and exists_payload.get("exists") is False:
                self.notify(f"Research {research_id!r} not found", severity="warning")
                self._set_status(f"Research {research_id!r} not found")
                self._log_operation(f"Research {research_id!r} not found")
                return
            payload = await self.prompt_client.load_research(research_id)
        except Exception as exc:
            self.notify(str(exc), severity="error", title="Load failed")
            self._set_status(f"Load failed: {exc}")
            return

        thread.research = self._research_from_payload(payload)
        self.load_thread_to_ui(thread)
        self.refresh_threads()
        self.store.save(self.state)
        self.notify("Research loaded")
        self._set_status(f"Research {research_id} loaded")
        self._log_operation(f"Research {research_id} loaded")

    @on(Button.Pressed, "#send")
    def send_pressed(self) -> None:
        self.send_message()

    @on(Button.Pressed, "#send-first")
    def send_first_pressed(self) -> None:
        self.send_message(force_first=True)

    @on(Button.Pressed, "#send-reply")
    def send_reply_pressed(self) -> None:
        self.send_message(force_first=False)

    def action_send_from_binding(self) -> None:
        self.send_message()

    def action_send_first_from_binding(self) -> None:
        self.send_message(force_first=True)

    def action_send_reply_from_binding(self) -> None:
        self.send_message(force_first=False)

    @work
    async def send_message(self, force_first: bool | None = None) -> None:
        if self.sending:
            self.notify("Wait for the current request to finish", severity="warning")
            return
        self.sending = True
        self._set_status("Sending request to interview agent...")
        self._log_operation("Sending request to interview-agent")
        try:
            self.persist_from_sidebar()
            thread = self.current_thread
            composer = self.query_one("#composer", TextArea)
            text = composer.text.strip()
            if not text:
                self.notify("Message is empty", severity="warning")
                self._set_status("Send skipped: empty message")
                return
            if not thread.research.research_id:
                self.notify("research_id is required", severity="warning")
                self._set_status("Send skipped: research_id is required")
                return

            composer.clear()
            thread.messages.append(ThreadMessage(role="user", text=text))
            self.render_messages(thread.messages)

            is_first_message = (
                not thread.started
                or thread.started_research_id != thread.research.research_id
            )
            if force_first is not None:
                is_first_message = force_first

            try:
                response = await self.agent_client.send_text(
                    message_text=text,
                    research_id=thread.research.research_id,
                    context=thread.context,
                    is_first_message=is_first_message,
                )
            except Exception as exc:
                self.notify(str(exc), severity="error", title="Agent failed")
                self._set_status(f"Agent failed: {exc}")
                self._log_operation(f"Agent failed: {exc}")
                return

            thread.started = True
            thread.started_research_id = thread.research.research_id
            thread.messages.extend(parse_agent_pipeline(response))
            self.render_messages(thread.messages)
            self.refresh_threads()
            self.store.save(self.state)
            self.notify("Agent response received", title="Interview agent")
            self._set_status("Agent response received")
            self._log_operation("Agent response received")
        finally:
            self.sending = False

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

    def _set_status(self, text: str) -> None:
        self.status_text = text
        self.query_one("#status-line", Label).update(text)

    def _log_operation(self, text: str) -> None:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.query_one("#ops-log", RichLog).write(f"[{now}] {text}")


if __name__ == "__main__":
    AgentResearchApp().run()

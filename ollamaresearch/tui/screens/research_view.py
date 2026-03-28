"""
Pantalla principal — v1.1.0
Incluye: Markdown rendering, token counter, Ctrl+R regenerar,
         notificaciones, historial, RAG archivos locales, búsqueda Ctrl+F
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Footer, Header, Input,
    Label, ListItem, ListView, Markdown, Static,
)
from textual.widget import Widget

from ollamaresearch.core.ollama_client import OllamaClient
from ollamaresearch.core.research_agent import EventType, ResearchAgent, ResearchEvent
from ollamaresearch.core.search_engine import SearchEngine, SearchResult
from ollamaresearch.core.web_scraper import WebScraper
from ollamaresearch.utils.config import get_config


# ─── Descripciones de modo ───────────────────────────────────────────────────
MODE_INFO = {
    "research": (
        "🔬 Deep Research",
        "Genera sub-búsquedas → descarga páginas web → sintetiza con IA. "
        "Informe exhaustivo con fuentes citadas. Tarda 1-3 min.",
    ),
    "chat": (
        "💬 Chat",
        "Conversación directa sin internet. Usa el conocimiento "
        "interno del modelo. Rápido e inmediato.",
    ),
    "search": (
        "🔍 Búsqueda Rápida",
        "Busca en internet y resume en segundos. "
        "Punto medio entre Deep Research y Chat.",
    ),
    "code": (
        "💻 Modo Código",
        "Agente de terminal: crea proyectos, escribe código, gestiona entornos virtuales. "
        "Ideal para frameworks de pentesting y desarrollo asistido por IA.",
    ),
}


# ─── Widgets de burbuja ──────────────────────────────────────────────────────

class UserBubble(Widget):
    DEFAULT_CSS = """
    UserBubble {
        background: #1a1b2e; border-left: thick #7aa2f7;
        padding: 0 1; margin: 1 0 0 0; height: auto;
    }
    UserBubble .ub-label { color: #7aa2f7; text-style: bold; height: 1; }
    UserBubble .ub-text  { color: #c0caf5; }
    """
    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        yield Static("▶ Tú", classes="ub-label")
        yield Static(self._text, classes="ub-text")


class AIBubble(Widget):
    """
    Burbuja IA con streaming en lugar.
    - Durante generación: Static (rápido, sin re-parseo)
    - Al terminar: reemplaza con Markdown (formateado)
    """
    DEFAULT_CSS = """
    AIBubble {
        background: #13141f; border-left: thick #9ece6a;
        padding: 0 1; margin: 0 0 1 0; height: auto;
    }
    AIBubble .ab-label { color: #9ece6a; text-style: bold; height: 1; }
    AIBubble .ab-body  { color: #c0caf5; }
    AIBubble Markdown  { background: #13141f; padding: 0; margin: 0; }
    """
    def __init__(self, model: str):
        super().__init__()
        self._model = model
        self._text = ""
        self._streaming = True

    def compose(self) -> ComposeResult:
        yield Static(f"🤖 {self._model}", classes="ab-label", id="ab-label")
        yield Static("[dim]▋[/dim]", id="ab-body", classes="ab-body")

    def append_text(self, text: str) -> None:
        """Streaming en lugar — sin nuevas líneas."""
        self._text += text
        try:
            self.query_one("#ab-body", Static).update(self._text + "[dim]▋[/dim]")
        except Exception:
            pass

    def finish(self) -> None:
        """Reemplaza Static con Markdown para renderizado completo."""
        self._streaming = False
        try:
            static = self.query_one("#ab-body", Static)
            static.remove()
            self.mount(Markdown(self._text or "_Sin respuesta_"))
        except Exception:
            try:
                self.query_one("#ab-body", Static).update(self._text or "[dim](sin respuesta)[/dim]")
            except Exception:
                pass

    def get_text(self) -> str:
        return self._text


class StatusLine(Widget):
    DEFAULT_CSS = """
    StatusLine { color: #565f89; height: auto; padding: 0 2; }
    """
    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        yield Static(self._text)

    def set_text(self, text: str) -> None:
        self._text = text
        try:
            self.query_one(Static).update(text)
        except Exception:
            pass


class FileBubble(Widget):
    """Aviso de archivo adjunto."""
    DEFAULT_CSS = """
    FileBubble {
        background: #1a1b2e; border-left: thick #e0af68;
        padding: 0 1; margin: 0 0 0 0; height: auto; color: #e0af68;
    }
    """
    def __init__(self, filename: str, fmt: str):
        super().__init__()
        self._filename = filename
        self._fmt = fmt

    def compose(self) -> ComposeResult:
        yield Static(f"📎 Archivo adjunto: [bold]{self._filename}[/bold] ({self._fmt})")


class SearchBar(Widget):
    """Barra de búsqueda en la conversación (Ctrl+F)."""
    DEFAULT_CSS = """
    SearchBar {
        height: 3; background: #1a1b2e; border: solid #7aa2f7;
        padding: 0 1; display: none;
    }
    SearchBar.visible { display: block; }
    """
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Buscar en la conversación… (Esc = cerrar)", id="search-input")


class SourceItem(ListItem):
    def __init__(self, source: SearchResult, index: int):
        super().__init__()
        self.source = source
        self.index = index

    def compose(self) -> ComposeResult:
        from urllib.parse import urlparse
        domain = urlparse(self.source.url).netloc.replace("www.", "")
        yield Vertical(
            Static(f"[bold]{self.index}.[/bold] {self.source.title[:45]}", classes="src-title"),
            Static(f"[dim cyan]{domain}[/dim cyan]", classes="src-domain"),
        )

    def on_click(self) -> None:
        import webbrowser
        webbrowser.open(self.source.url)


# ─── Pantalla principal ───────────────────────────────────────────────────────

class ResearchView(Screen):
    BINDINGS = [
        Binding("ctrl+m", "change_model", "Cambiar Modelo"),
        Binding("ctrl+n", "action_new_session", "Nueva Sesión"),
        Binding("ctrl+s", "action_save_result", "Guardar"),
        Binding("ctrl+c", "action_copy_result", "Copiar"),
        Binding("ctrl+l", "action_clear_chat", "Limpiar"),
        Binding("ctrl+r", "action_regenerate", "Regenerar"),
        Binding("ctrl+h", "action_show_history", "Historial"),
        Binding("ctrl+f", "action_toggle_search", "Buscar"),
        Binding("escape", "change_model", "Cambiar Modelo"),
        Binding("f1", "action_show_help", "Ayuda"),
        Binding("ctrl+q", "app.quit", "Salir"),
    ]

    def __init__(
        self,
        client: OllamaClient,
        model: str,
        mode: str = "research",
        initial_query: str = "",
    ):
        super().__init__()
        self.client = client
        self.model = model
        self.mode = mode
        self.initial_query = initial_query
        self._is_processing = False
        self._sources: List[SearchResult] = []
        self._current_result = ""
        self._messages: List[Dict] = []
        self._last_query = ""
        self._agent: Optional[ResearchAgent] = None
        self._current_ai_bubble: Optional[AIBubble] = None
        self._current_status: Optional[StatusLine] = None
        self._search_visible = False
        # Token speed
        self._token_start: Optional[float] = None
        self._token_count = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="research-wrapper"):
            with Horizontal(id="top-bar"):
                yield Static(f"🤖 [bold cyan]{self.model}[/bold cyan]", id="model-indicator")
                yield Static("", id="token-speed")
                yield Static("", id="status-bar")

            with Horizontal(id="mode-bar"):
                yield Button("🔬 Deep Research",  id="mode-research", classes="mode-tab")
                yield Button("💬 Chat",            id="mode-chat",    classes="mode-tab")
                yield Button("🔍 Búsqueda Rápida", id="mode-web",     classes="mode-tab")
                yield Button("💻 Código",           id="mode-code",    classes="mode-tab")
                yield Button("📚 Historial",        id="btn-history",  classes="mode-tab hist-btn")

            yield Static("", id="mode-desc")

            with Horizontal(id="main-panel"):
                with Vertical(id="left-panel"):
                    yield Static("💬 CONVERSACIÓN", classes="panel-header")
                    yield SearchBar(id="searchbar")
                    yield VerticalScroll(id="chat-scroll")

                with Vertical(id="right-panel"):
                    yield Static("🔗 FUENTES (0)", id="sources-title", classes="panel-header")
                    yield ListView(id="sources-list")
                    yield Static(
                        "[dim]Las fuentes\naparecerán\naquí[/dim]",
                        id="sources-empty",
                    )

            with Container(id="input-area"):
                yield Input(
                    placeholder="Pregunta, o escribe /ruta/archivo.pdf para adjuntar (Enter = enviar)",
                    id="query-input",
                )
                with Horizontal(id="input-actions"):
                    yield Button("▶ Enviar",   id="btn-send",  variant="primary")
                    yield Button("⏹ Detener",  id="btn-stop",  disabled=True)
                    yield Button("🔄 Nuevas",   id="btn-clear")
                    yield Button("♻ Regenerar", id="btn-regen")
                    yield Button("📋 Copiar",   id="btn-copy")
                    yield Button("💾 Guardar",  id="btn-save")

        yield Footer()

    def on_mount(self) -> None:
        self._setup_mode()
        self._setup_agent()
        self._show_welcome()
        if self.initial_query:
            self.query_one("#query-input", Input).value = self.initial_query
            self._execute_query(self.initial_query)

    # ─── Setup ───────────────────────────────────────────────────────────────

    def _setup_mode(self) -> None:
        name, desc = MODE_INFO.get(self.mode, ("", ""))
        self.query_one("#mode-desc", Static).update(f"[dim]  {desc}[/dim]")
        for mid in ["mode-research", "mode-chat", "mode-web", "mode-code"]:
            self.query_one(f"#{mid}", Button).remove_class("active-tab")
        mode_map = {"research": "mode-research", "chat": "mode-chat", "search": "mode-web", "code": "mode-code"}
        if self.mode in mode_map:
            self.query_one(f"#{mode_map[self.mode]}", Button).add_class("active-tab")
        # Si cambia a modo código, navegar a CodeView
        if self.mode == "code":
            self.app.call_later(self._go_to_code_view)

    def _setup_agent(self) -> None:
        cfg = get_config()
        engine = SearchEngine(
            engine=cfg.search_engine,
            tavily_key=cfg.tavily_api_key,
            serper_key=cfg.serper_api_key,
        )
        scraper = WebScraper(
            timeout=10.0,
            max_chars=cfg.research_config.get("max_tokens_per_source", 2000),
        )
        self._agent = ResearchAgent(
            ollama_client=self.client,
            search_engine=engine,
            scraper=scraper,
            config=cfg.research_config,
        )

    def _show_welcome(self) -> None:
        name, desc = MODE_INFO.get(self.mode, ("", ""))
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(StatusLine(
            f"[cyan]━━━ OllamaResearch v1.1 ━━━[/cyan]\n"
            f"[dim]Modelo:[/dim] [bold]{self.model}[/bold]\n"
            f"[dim]Modo:[/dim]   [bold]{name}[/bold] — {desc}\n"
            f"[dim]Tip:[/dim]    Escribe la ruta de un archivo para adjuntarlo como contexto\n"
            f"[cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━[/cyan]"
        ))

    # ─── Envío ───────────────────────────────────────────────────────────────

    @on(Input.Submitted, "#query-input")
    def on_submitted(self, event: Input.Submitted) -> None:
        q = event.value.strip()
        if q and not self._is_processing:
            event.input.value = ""
            self._execute_query(q)

    @on(Button.Pressed, "#btn-send")
    def on_send(self) -> None:
        inp = self.query_one("#query-input", Input)
        q = inp.value.strip()
        if q and not self._is_processing:
            inp.value = ""
            self._execute_query(q)

    @on(Button.Pressed, "#btn-stop")
    def on_stop(self) -> None:
        for w in self.app._workers:
            if not w.is_done:
                w.cancel()
        self._set_processing(False)
        if self._current_ai_bubble:
            self._current_ai_bubble.finish()
        self._add_status("⚠️ [yellow]Generación detenida[/yellow]")

    def _execute_query(self, query: str) -> None:
        # Detectar si es un archivo adjunto
        from ollamaresearch.core.rag import extract_file_and_query, prepare_context
        file_path, real_query = extract_file_and_query(query)

        if file_path:
            from ollamaresearch.core.rag import read_file
            try:
                _, fmt = read_file(file_path)
                full_ctx = prepare_context(file_path, real_query)
                self._last_query = real_query
                self._do_chat_with_context(file_path.name, fmt, real_query, full_ctx)
            except ValueError as e:
                self._add_status(f"❌ {e}")
        else:
            self._last_query = query
            if self.mode == "research":
                self._do_research(query)
            elif self.mode == "chat":
                self._do_chat(query)
            elif self.mode == "code":
                self._go_to_code_view(query)
            else:
                self._do_search(query)

    # ─── token speed tracking ─────────────────────────────────────────────────
    def _on_chunk(self, text: str) -> None:
        if self._token_start is None:
            self._token_start = time.monotonic()
            self._token_count = 0
        self._token_count += 1
        elapsed = time.monotonic() - self._token_start
        if elapsed > 0 and self._token_count % 5 == 0:
            tps = self._token_count / elapsed
            self.query_one("#token-speed", Static).update(f"[dim]{tps:.1f} tok/s[/dim]")

    def _reset_token_counter(self) -> None:
        self._token_start = None
        self._token_count = 0
        self.query_one("#token-speed", Static).update("")

    # ─── Workers ─────────────────────────────────────────────────────────────

    @work(exclusive=False)
    async def _do_research(self, query: str) -> None:
        self._set_processing(True)
        self._reset_token_counter()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        await scroll.mount(UserBubble(query))
        self._current_ai_bubble = None
        self._current_result = ""
        self._current_status = None
        await self._clear_sources()

        async def handle(event: ResearchEvent) -> None:
            if event.type in (EventType.STATUS, EventType.ITERATION,
                              EventType.SEARCH_START, EventType.SCRAPING,
                              EventType.SYNTHESIZING):
                await self._update_status(event.text)
            elif event.type == EventType.SOURCE_FOUND:
                self._sources = event.sources
                await self._update_sources(event.sources)
            elif event.type == EventType.CHUNK:
                if self._current_ai_bubble is None:
                    self._current_ai_bubble = AIBubble(self.model)
                    await scroll.mount(self._current_ai_bubble)
                self._current_ai_bubble.append_text(event.text)
                self._current_result += event.text
                self._on_chunk(event.text)
                scroll.scroll_end(animate=False)
            elif event.type == EventType.DONE:
                if self._current_ai_bubble:
                    self._current_ai_bubble.finish()
                await self._update_status(event.text)

        try:
            result = await self._agent.research(query, self.model, handle)
            self._messages.append({"role": "user", "content": query})
            self._messages.append({"role": "assistant", "content": result.report})
            self._save_session_auto(query)
            from ollamaresearch.core.notifier import notify
            notify("OllamaResearch", f"✅ Deep Research completado:\n{query[:60]}")
        except Exception as e:
            await self._add_status_async(f"❌ [red]{e}[/red]")
        self._set_processing(False)
        self._reset_token_counter()

    @work(exclusive=False)
    async def _do_chat(self, query: str) -> None:
        self._set_processing(True)
        self._reset_token_counter()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        await scroll.mount(UserBubble(query))
        self._current_ai_bubble = AIBubble(self.model)
        await scroll.mount(self._current_ai_bubble)
        self._current_result = ""
        self._messages.append({"role": "user", "content": query})

        async def handle(event: ResearchEvent) -> None:
            if event.type == EventType.CHUNK:
                self._current_ai_bubble.append_text(event.text)
                self._current_result += event.text
                self._on_chunk(event.text)
                scroll.scroll_end(animate=False)
            elif event.type == EventType.DONE:
                self._current_ai_bubble.finish()

        try:
            result = await self._agent.chat(self._messages, self.model, handle)
            self._messages.append({"role": "assistant", "content": result})
        except Exception as e:
            await self._add_status_async(f"❌ [red]{e}[/red]")
        self._set_processing(False)
        self._reset_token_counter()

    @work(exclusive=False)
    async def _do_search(self, query: str) -> None:
        self._set_processing(True)
        self._reset_token_counter()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        await scroll.mount(UserBubble(query))
        self._current_ai_bubble = AIBubble(self.model)
        self._current_result = ""
        await self._clear_sources()

        async def handle(event: ResearchEvent) -> None:
            if event.type == EventType.STATUS:
                await self._update_status(event.text)
            elif event.type == EventType.SOURCE_FOUND:
                self._sources = event.sources
                await self._update_sources(event.sources)
                if self._current_ai_bubble not in scroll.children:
                    await scroll.mount(self._current_ai_bubble)
            elif event.type == EventType.CHUNK:
                if self._current_ai_bubble not in scroll.children:
                    await scroll.mount(self._current_ai_bubble)
                self._current_ai_bubble.append_text(event.text)
                self._current_result += event.text
                self._on_chunk(event.text)
                scroll.scroll_end(animate=False)
            elif event.type == EventType.DONE:
                self._current_ai_bubble.finish()
                await self._update_status(event.text)

        try:
            await self._agent.web_search_summary(query, self.model, handle)
        except Exception as e:
            await self._add_status_async(f"❌ [red]{e}[/red]")
        self._set_processing(False)
        self._reset_token_counter()

    @work(exclusive=False)
    async def _do_chat_with_context(
        self, filename: str, fmt: str, query: str, full_context: str
    ) -> None:
        self._set_processing(True)
        self._reset_token_counter()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        await scroll.mount(FileBubble(filename, fmt))
        await scroll.mount(UserBubble(query))
        self._current_ai_bubble = AIBubble(self.model)
        await scroll.mount(self._current_ai_bubble)
        self._current_result = ""
        msgs = [{"role": "user", "content": full_context}]

        async def handle(event: ResearchEvent) -> None:
            if event.type == EventType.CHUNK:
                self._current_ai_bubble.append_text(event.text)
                self._current_result += event.text
                self._on_chunk(event.text)
                scroll.scroll_end(animate=False)
            elif event.type == EventType.DONE:
                self._current_ai_bubble.finish()

        try:
            await self._agent.chat(msgs, self.model, handle)
        except Exception as e:
            await self._add_status_async(f"❌ [red]{e}[/red]")
        self._set_processing(False)
        self._reset_token_counter()

    # ─── Helpers UI ──────────────────────────────────────────────────────────

    def _set_processing(self, val: bool) -> None:
        self._is_processing = val
        self.query_one("#btn-send", Button).disabled = val
        self.query_one("#btn-stop", Button).disabled = not val
        self.query_one("#query-input", Input).disabled = val

    def _add_status(self, text: str) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(StatusLine(text))

    async def _add_status_async(self, text: str) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        await scroll.mount(StatusLine(text))

    async def _update_status(self, text: str) -> None:
        if self._current_status is None:
            self._current_status = StatusLine(text)
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            await scroll.mount(self._current_status)
        else:
            self._current_status.set_text(text)

    async def _clear_sources(self) -> None:
        self._sources = []
        await self.query_one("#sources-list", ListView).clear()
        self.query_one("#sources-title", Static).update("🔗 FUENTES (0)")
        self.query_one("#sources-empty").display = True

    async def _update_sources(self, sources: List[SearchResult]) -> None:
        src_list = self.query_one("#sources-list", ListView)
        await src_list.clear()
        self.query_one("#sources-title", Static).update(f"🔗 FUENTES ({len(sources)})")
        self.query_one("#sources-empty").display = False
        for i, s in enumerate(sources[:20], 1):
            await src_list.append(SourceItem(s, i))

    def _show_status(self, msg: str) -> None:
        sb = self.query_one("#status-bar", Static)
        sb.update(msg)
        self.set_timer(3.0, lambda: sb.update(""))

    def _save_session_auto(self, query: str) -> None:
        if not self._current_result:
            return
        try:
            from ollamaresearch.core.history import save_session
            save_session(
                mode=self.mode,
                model=self.model,
                query=query,
                messages=self._messages,
                result=self._current_result,
                sources=self._sources,
            )
        except Exception:
            pass

    # ─── Botones ─────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-regen")
    def action_regenerate(self) -> None:
        if not self._last_query or self._is_processing:
            self._show_status("⚠️  Nada que regenerar")
            return
        # Quitar último AIBubble del scroll
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        children = list(scroll.children)
        for w in reversed(children):
            if isinstance(w, AIBubble):
                w.remove()
                break
        self._current_result = ""
        self._current_ai_bubble = None
        self._execute_query(self._last_query)

    @on(Button.Pressed, "#btn-clear")
    def action_clear_chat(self) -> None:
        self.query_one("#chat-scroll", VerticalScroll).remove_children()
        self._messages.clear()
        self._current_result = ""
        self._current_ai_bubble = None
        self._current_status = None
        self._last_query = ""
        self._sources = []
        self.query_one("#sources-title", Static).update("🔗 FUENTES (0)")
        self.query_one("#sources-empty").display = True
        self._show_welcome()

    @on(Button.Pressed, "#btn-copy")
    def action_copy_result(self) -> None:
        if self._current_result:
            try:
                import pyperclip
                pyperclip.copy(self._current_result)
                self._show_status("📋 Copiado al portapapeles")
            except Exception:
                self._show_status("❌ Instala pyperclip: pip install pyperclip")
        else:
            self._show_status("⚠️  Nada que copiar")

    @on(Button.Pressed, "#btn-save")
    def action_save_result(self) -> None:
        if not self._current_result:
            self._show_status("⚠️  Nada que guardar")
            return
        try:
            from ollamaresearch.utils.config import get_data_dir
            d = get_data_dir() / "results"
            d.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            f = d / f"research_{ts}.md"
            f.write_text(
                f"# {self._last_query}\n\n"
                f"_Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')} "
                f"con {self.model} ({MODE_INFO[self.mode][0]})_\n\n"
                + self._current_result,
                encoding="utf-8",
            )
            self._show_status(f"💾 Guardado: {f.name}")
        except Exception as e:
            self._show_status(f"❌ Error: {e}")

    @on(Button.Pressed, "#btn-history")
    def action_show_history(self) -> None:
        from ollamaresearch.tui.screens.history_screen import HistoryScreen
        self.app.push_screen(HistoryScreen(), callback=self._on_history_selected)

    def _on_history_selected(self, data) -> None:
        if not data:
            return
        self.action_clear_chat()
        self._current_result = data.get("result", "")
        self._messages = data.get("messages", [])
        self.model = data.get("model", self.model)
        self.mode = data.get("mode", self.mode)
        self._setup_mode()
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.mount(StatusLine(
            f"[cyan]📚 Sesión restaurada[/cyan]\n"
            f"[dim]{data.get('timestamp', '')[: 16]} • {data.get('query', '')}[/dim]"
        ))
        bubble = AIBubble(self.model)
        scroll.mount(bubble)
        bubble.append_text(self._current_result)
        bubble.finish()

    # ─── Tabs de modo ─────────────────────────────────────────────────────────

    @on(Button.Pressed, "#mode-research")
    def sw_research(self) -> None:
        self.mode = "research"; self._setup_mode()

    @on(Button.Pressed, "#mode-chat")
    def sw_chat(self) -> None:
        self.mode = "chat"; self._setup_mode()

    @on(Button.Pressed, "#mode-web")
    def sw_web(self) -> None:
        self.mode = "search"; self._setup_mode()

    @on(Button.Pressed, "#mode-code")
    def sw_code(self) -> None:
        self.mode = "code"; self._setup_mode()

    def _go_to_code_view(self, initial_query: str = "") -> None:
        from ollamaresearch.tui.screens.code_view import CodeView
        self.app.push_screen(CodeView(
            client=self.client,
            model=self.model,
            initial_query=initial_query,
        ))

    # ─── Búsqueda Ctrl+F ─────────────────────────────────────────────────────

    def action_toggle_search(self) -> None:
        self._search_visible = not self._search_visible
        sb = self.query_one("#searchbar", SearchBar)
        if self._search_visible:
            sb.add_class("visible")
            self.query_one("#search-input", Input).focus()
        else:
            sb.remove_class("visible")
            self.query_one("#query-input", Input).focus()

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        q = event.value.lower().strip()
        if not q:
            return
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        for w in scroll.children:
            if isinstance(w, (AIBubble, UserBubble, StatusLine)):
                try:
                    text_w = w.query_one(Static)
                    if q in (text_w.renderable or "").lower():
                        scroll.scroll_to_widget(w, animate=True)
                        break
                except Exception:
                    pass

    # ─── Acciones generales ──────────────────────────────────────────────────

    def action_change_model(self) -> None:
        from ollamaresearch.tui.screens.model_selector import ModelSelectorScreen
        self.app.push_screen(
            ModelSelectorScreen(self.client, self.model, self.mode),
            callback=self._on_model_selected,
        )

    def _on_model_selected(self, result) -> None:
        if result:
            model, mode = result
            self.model = model
            self.mode = mode
            self._setup_mode()
            self._setup_agent()
            self.query_one("#model-indicator", Static).update(f"🤖 [bold cyan]{model}[/bold cyan]")
            cfg = get_config()
            cfg.last_model = model
            cfg.last_mode = mode

    def action_new_session(self) -> None:
        self.action_clear_chat()

    def action_show_help(self) -> None:
        self._add_status(
            "[bold yellow]━━━ AYUDA ━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]\n"
            "[bold]Atajos de teclado:[/bold]\n"
            "  [cyan]Enter[/cyan]     Enviar pregunta\n"
            "  [cyan]Ctrl+M[/cyan]    Cambiar modelo\n"
            "  [cyan]Ctrl+N[/cyan]    Nueva sesión\n"
            "  [cyan]Ctrl+R[/cyan]    Regenerar última respuesta\n"
            "  [cyan]Ctrl+H[/cyan]    Ver historial de sesiones\n"
            "  [cyan]Ctrl+F[/cyan]    Buscar en la conversación\n"
            "  [cyan]Ctrl+C[/cyan]    Copiar respuesta\n"
            "  [cyan]Ctrl+S[/cyan]    Guardar como .md\n"
            "  [cyan]Ctrl+Q[/cyan]    Salir\n"
            "[bold]Archivos:[/bold]\n"
            "  Escribe la ruta de un archivo para adjuntarlo:\n"
            "  [cyan]/home/user/doc.pdf resume esto[/cyan]\n"
            "  Soporta: .txt .md .pdf .csv .py .js .json y más\n"
            "[bold yellow]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]"
        )

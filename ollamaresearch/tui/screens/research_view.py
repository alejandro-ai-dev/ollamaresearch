"""
Pantalla principal — Chat con streaming correcto y descripciones de modos
"""
from datetime import datetime
from typing import Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, ListItem, ListView, Static

from ollamaresearch.core.ollama_client import OllamaClient
from ollamaresearch.core.research_agent import EventType, ResearchAgent, ResearchEvent
from ollamaresearch.core.search_engine import SearchEngine, SearchResult
from ollamaresearch.core.web_scraper import WebScraper
from ollamaresearch.utils.config import get_config


# ─── Descripciones de cada modo ──────────────────────────────────────────────
MODE_INFO = {
    "research": (
        "🔬 Deep Research",
        "Investiga en internet: genera sub-búsquedas → descarga páginas → sintetiza con IA "
        "en múltiples iteraciones. Ideal para preguntas complejas o que necesitan información "
        "actualizada. Más lento (1-3 min) pero muy completo.",
    ),
    "chat": (
        "💬 Chat",
        "Conversación directa con el modelo. NO busca en internet — usa solo el conocimiento "
        "interno del modelo. Ideal para preguntas generales, redacción, código o brainstorming. "
        "Rápido e inmediato.",
    ),
    "search": (
        "🔍 Búsqueda Rápida",
        "Busca en internet y el modelo resume los resultados en un párrafo. "
        "Más rápido que Deep Research. Ideal para consultas simples que necesitan "
        "datos recientes sin un informe exhaustivo.",
    ),
}


# ─── Widgets de mensajes ─────────────────────────────────────────────────────

class UserBubble(Widget):
    """Burbuja de mensaje del usuario."""

    DEFAULT_CSS = """
    UserBubble {
        background: #1a1b2e;
        border-left: thick #7aa2f7;
        padding: 0 1;
        margin: 1 0 0 0;
        height: auto;
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


class StatusLine(Widget):
    """Línea de estado durante el procesamiento."""

    DEFAULT_CSS = """
    StatusLine {
        color: #565f89;
        height: auto;
        padding: 0 2;
    }
    """

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        yield Static(self._text)

    def set_text(self, text: str) -> None:
        self._text = text
        self.query_one(Static).update(text)


class AIBubble(Widget):
    """
    Burbuja de respuesta IA con streaming en lugar.
    El texto se actualiza con .append_text() sin crear nuevas líneas.
    """

    DEFAULT_CSS = """
    AIBubble {
        background: #13141f;
        border-left: thick #9ece6a;
        padding: 0 1;
        margin: 0 0 1 0;
        height: auto;
    }
    AIBubble .ab-label { color: #9ece6a; text-style: bold; height: 1; }
    AIBubble .ab-body  { color: #c0caf5; }
    """

    def __init__(self, model: str):
        super().__init__()
        self._model = model
        self._text = ""

    def compose(self) -> ComposeResult:
        yield Static(f"🤖 {self._model}", classes="ab-label")
        yield Static("[dim]▋[/dim]", id="ab-body", classes="ab-body")

    def append_text(self, text: str) -> None:
        """Añade texto al streaming — actualiza en lugar, sin nuevas líneas."""
        self._text += text
        try:
            self.query_one("#ab-body", Static).update(self._text + "[dim]▋[/dim]")
        except Exception:
            pass

    def finish(self) -> None:
        """Elimina el cursor parpadeante al terminar."""
        try:
            self.query_one("#ab-body", Static).update(self._text or "[dim](sin respuesta)[/dim]")
        except Exception:
            pass


class SourceItem(ListItem):
    """Elemento de fuente web."""

    def __init__(self, source: SearchResult, index: int):
        super().__init__()
        self.source = source
        self.index = index

    def compose(self) -> ComposeResult:
        domain = _domain(self.source.url)
        yield Vertical(
            Static(f"[bold]{self.index}.[/bold] {self.source.title[:45]}", classes="src-title"),
            Static(f"[dim cyan]{domain}[/dim cyan]", classes="src-domain"),
        )

    def on_click(self) -> None:
        import webbrowser
        webbrowser.open(self.source.url)


# ─── Importación tardía que evita circular ────────────────────────────────────
from textual.widget import Widget  # noqa: E402


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url[:30]


# ─── Pantalla principal ───────────────────────────────────────────────────────

class ResearchView(Screen):
    """Vista principal: Deep Research, Chat y Búsqueda Rápida."""

    BINDINGS = [
        Binding("ctrl+m", "change_model", "Cambiar Modelo"),
        Binding("ctrl+n", "action_new_session", "Nueva Sesión"),
        Binding("ctrl+s", "action_save_result", "Guardar"),
        Binding("ctrl+c", "action_copy_result", "Copiar"),
        Binding("ctrl+l", "action_clear_chat", "Limpiar"),
        Binding("escape", "change_model", "Cambiar Modelo"),
        Binding("f1", "action_show_help", "Ayuda"),
        Binding("ctrl+q", "app.quit", "Salir"),
    ]

    def __init__(self, client: OllamaClient, model: str, mode: str = "research", initial_query: str = ""):
        super().__init__()
        self.client = client
        self.model = model
        self.mode = mode
        self.initial_query = initial_query
        self._is_processing = False
        self._sources: List[SearchResult] = []
        self._current_result = ""
        self._messages: List[Dict] = []
        self._agent: Optional[ResearchAgent] = None
        self._current_ai_bubble: Optional[AIBubble] = None
        self._current_status: Optional[StatusLine] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="research-wrapper"):

            # Barra superior
            with Horizontal(id="top-bar"):
                yield Static(f"🤖 [bold cyan]{self.model}[/bold cyan]", id="model-indicator")
                yield Static("", id="status-bar")

            # Tabs de modo
            with Horizontal(id="mode-bar"):
                yield Button("🔬 Deep Research", id="mode-research", classes="mode-tab")
                yield Button("💬 Chat",           id="mode-chat",     classes="mode-tab")
                yield Button("🔍 Búsqueda Rápida", id="mode-web",    classes="mode-tab")

            # Descripción del modo activo
            yield Static("", id="mode-desc")

            # Panel principal
            with Horizontal(id="main-panel"):
                # Conversación — VerticalScroll evita el bug de RichLog
                with Vertical(id="left-panel"):
                    yield Static("💬 CONVERSACIÓN", classes="panel-header")
                    yield VerticalScroll(id="chat-scroll")

                # Fuentes
                with Vertical(id="right-panel"):
                    yield Static("🔗 FUENTES (0)", id="sources-title", classes="panel-header")
                    yield ListView(id="sources-list")
                    yield Static(
                        "[dim]Las fuentes aparecerán\naquí al buscar[/dim]",
                        id="sources-empty",
                        classes="src-empty",
                    )

            # Input
            with Container(id="input-area"):
                yield Input(placeholder="Escribe tu pregunta… (Enter para enviar)", id="query-input")
                with Horizontal(id="input-actions"):
                    yield Button("▶ Enviar",  id="btn-send",  variant="primary")
                    yield Button("⏹ Detener", id="btn-stop",  disabled=True)
                    yield Button("🔄 Limpiar", id="btn-clear")
                    yield Button("📋 Copiar",  id="btn-copy")
                    yield Button("💾 Guardar", id="btn-save")

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
        self.query_one("#mode-desc", Static).update(
            f"[dim]  {desc}[/dim]"
        )
        for mid in ["mode-research", "mode-chat", "mode-web"]:
            btn = self.query_one(f"#{mid}", Button)
            btn.remove_class("active-tab")
        mode_map = {"research": "mode-research", "chat": "mode-chat", "search": "mode-web"}
        if self.mode in mode_map:
            self.query_one(f"#{mode_map[self.mode]}", Button).add_class("active-tab")

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
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        name, desc = MODE_INFO.get(self.mode, ("", ""))
        # Se monta de forma síncrona en on_mount
        scroll.mount(
            StatusLine(
                f"[cyan]━━━ OllamaResearch ━━━[/cyan]\n"
                f"[dim]Modelo:[/dim] [bold]{self.model}[/bold]\n"
                f"[dim]Modo:[/dim]   [bold]{name}[/bold]\n"
                f"[dim]{desc}[/dim]\n"
                f"[cyan]━━━━━━━━━━━━━━━━━━━━━━[/cyan]"
            )
        )

    # ─── Envío de query ───────────────────────────────────────────────────────

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
        self._add_status("⚠️ [yellow]Generación detenida[/yellow]")

    def _execute_query(self, query: str) -> None:
        if self.mode == "research":
            self._do_research(query)
        elif self.mode == "chat":
            self._do_chat(query)
        else:
            self._do_search(query)

    # ─── Workers de IA ────────────────────────────────────────────────────────

    @work(exclusive=False)
    async def _do_research(self, query: str) -> None:
        self._set_processing(True)
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        await scroll.mount(UserBubble(query))
        self._current_ai_bubble = None
        self._current_result = ""
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
                scroll.scroll_end(animate=False)

            elif event.type == EventType.DONE:
                if self._current_ai_bubble:
                    self._current_ai_bubble.finish()
                await self._update_status(event.text)

        try:
            result = await self._agent.research(query, self.model, handle)
            self._messages.append({"role": "user", "content": query})
            self._messages.append({"role": "assistant", "content": result.report})
        except Exception as e:
            await self._add_status_async(f"❌ [red]Error: {e}[/red]")
        self._set_processing(False)

    @work(exclusive=False)
    async def _do_chat(self, query: str) -> None:
        self._set_processing(True)
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
                scroll.scroll_end(animate=False)
            elif event.type == EventType.DONE:
                self._current_ai_bubble.finish()

        try:
            result = await self._agent.chat(self._messages, self.model, handle)
            self._messages.append({"role": "assistant", "content": result})
        except Exception as e:
            await self._add_status_async(f"❌ [red]Error: {e}[/red]")
        self._set_processing(False)

    @work(exclusive=False)
    async def _do_search(self, query: str) -> None:
        self._set_processing(True)
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
                scroll.scroll_end(animate=False)
            elif event.type == EventType.DONE:
                self._current_ai_bubble.finish()
                await self._update_status(event.text)

        try:
            await self._agent.web_search_summary(query, self.model, handle)
        except Exception as e:
            await self._add_status_async(f"❌ [red]Error: {e}[/red]")
        self._set_processing(False)

    # ─── Helpers de UI ────────────────────────────────────────────────────────

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
        src_list = self.query_one("#sources-list", ListView)
        await src_list.clear()
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

    # ─── Botones de acción ────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-clear")
    def action_clear_chat(self) -> None:
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.remove_children()
        self._messages = []
        self._current_result = ""
        self._current_ai_bubble = None
        self._current_status = None
        self._show_welcome()
        self._clear_sources_sync()

    def _clear_sources_sync(self) -> None:
        self._sources = []
        self.query_one("#sources-title", Static).update("🔗 FUENTES (0)")
        self.query_one("#sources-empty").display = True

    @on(Button.Pressed, "#btn-copy")
    def action_copy_result(self) -> None:
        if self._current_result:
            try:
                import pyperclip
                pyperclip.copy(self._current_result)
                self._show_status("📋 Copiado al portapapeles")
            except Exception:
                self._show_status("❌ Error al copiar")
        else:
            self._show_status("⚠️ Nada que copiar aún")

    @on(Button.Pressed, "#btn-save")
    def action_save_result(self) -> None:
        if not self._current_result:
            self._show_status("⚠️ Nada que guardar")
            return
        try:
            from ollamaresearch.utils.config import get_data_dir
            data_dir = get_data_dir() / "results"
            data_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            f = data_dir / f"research_{ts}.md"
            f.write_text(
                f"# Investigación — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                + self._current_result,
                encoding="utf-8",
            )
            self._show_status(f"💾 Guardado: {f.name}")
        except Exception as e:
            self._show_status(f"❌ Error al guardar: {e}")

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

    # ─── Acciones ─────────────────────────────────────────────────────────────

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
            self.query_one("#model-indicator", Static).update(
                f"🤖 [bold cyan]{model}[/bold cyan]"
            )
            cfg = get_config()
            cfg.last_model = model
            cfg.last_mode = mode

    def action_new_session(self) -> None:
        self.action_clear_chat()

    def action_show_help(self) -> None:
        self._add_status(
            "[bold yellow]━━━ AYUDA ━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]\n"
            "[bold]Atajos:[/bold]\n"
            "  [cyan]Enter[/cyan]   Enviar pregunta\n"
            "  [cyan]Ctrl+M[/cyan]  Cambiar modelo\n"
            "  [cyan]Ctrl+N[/cyan]  Nueva sesión\n"
            "  [cyan]Ctrl+L[/cyan]  Limpiar pantalla\n"
            "  [cyan]Ctrl+C[/cyan]  Copiar respuesta\n"
            "  [cyan]Ctrl+S[/cyan]  Guardar respuesta\n"
            "  [cyan]Ctrl+Q[/cyan]  Salir\n"
            "[bold]Modos:[/bold]\n"
            "  [cyan]🔬 Deep Research[/cyan]   Búsqueda web + síntesis exhaustiva\n"
            "  [cyan]💬 Chat[/cyan]            Conversación directa, sin internet\n"
            "  [cyan]🔍 Búsqueda Rápida[/cyan] Busca + resume en segundos\n"
            "[bold yellow]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]"
        )

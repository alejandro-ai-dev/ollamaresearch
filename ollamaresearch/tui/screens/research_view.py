"""
Pantalla principal de investigación — Vista de chat y research con streaming en vivo
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    RichLog,
    Static,
)

from ollamaresearch.core.ollama_client import OllamaClient
from ollamaresearch.core.research_agent import EventType, ResearchAgent, ResearchEvent
from ollamaresearch.core.search_engine import SearchEngine, SearchResult
from ollamaresearch.core.web_scraper import WebScraper
from ollamaresearch.utils.config import get_config


class SourceItem(ListItem):
    """Elemento de lista para una fuente web."""

    def __init__(self, source: SearchResult, index: int) -> None:
        super().__init__()
        self.source = source
        self.index = index

    def compose(self) -> ComposeResult:
        domain = source_domain(self.source.url)
        yield Vertical(
            Static(f"[bold]{self.index}.[/bold] {self.source.title[:50]}", classes="source-title"),
            Static(f"[dim]{domain}[/dim]", classes="source-domain"),
        )

    def on_click(self) -> None:
        import webbrowser
        webbrowser.open(self.source.url)


def source_domain(url: str) -> str:
    """Extrae el dominio de una URL."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url[:30]


class ResearchView(Screen):
    """
    Pantalla principal de investigación.
    Soporta tres modos: Deep Research, Chat, Búsqueda Rápida.
    """

    BINDINGS = [
        Binding("ctrl+m", "change_model", "Cambiar Modelo"),
        Binding("ctrl+n", "new_session", "Nueva Sesión"),
        Binding("ctrl+s", "save_result", "Guardar"),
        Binding("ctrl+c", "copy_result", "Copiar"),
        Binding("ctrl+l", "clear_chat", "Limpiar"),
        Binding("escape", "change_model", "Cambiar Modelo"),
        Binding("f1", "show_help", "Ayuda"),
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
        self._messages: List[Dict] = []  # Historial de chat
        self._agent: Optional[ResearchAgent] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="research-wrapper"):
            # Barra superior con info del modelo y modo
            with Horizontal(id="top-bar"):
                yield Static(f"🤖 [bold cyan]{self.model}[/bold cyan]", id="model-indicator")
                yield Static("", id="mode-indicator")
                yield Static("", id="status-bar")

            # Selector de modo
            with Horizontal(id="mode-bar"):
                yield Button("🔬 Deep Research", id="mode-research", classes="mode-tab")
                yield Button("💬 Chat", id="mode-chat", classes="mode-tab")
                yield Button("🔍 Búsqueda Rápida", id="mode-web", classes="mode-tab")

            # Panel principal — split en dos columnas
            with Horizontal(id="main-panel"):
                # Panel izquierdo: conversación/resultados
                with Vertical(id="left-panel"):
                    yield Static("💬 CONVERSACIÓN", classes="panel-header")
                    yield RichLog(
                        id="chat-log",
                        highlight=True,
                        markup=True,
                        wrap=True,
                    )

                # Panel derecho: fuentes
                with Vertical(id="right-panel"):
                    yield Static("🔗 FUENTES (0)", id="sources-title", classes="panel-header")
                    yield ListView(id="sources-list")
                    yield Static(
                        "[dim]Las fuentes aparecerán\naquí durante la búsqueda[/dim]",
                        id="sources-empty",
                        classes="sources-empty-msg",
                    )

            # Panel de input
            with Container(id="input-area"):
                yield Input(
                    placeholder="Escribe tu pregunta aquí... (Enter para enviar)",
                    id="query-input",
                )
                with Horizontal(id="input-actions"):
                    yield Button("▶ Enviar", id="btn-send", variant="primary")
                    yield Button("⏹ Detener", id="btn-stop", disabled=True)
                    yield Button("🔄 Limpiar", id="btn-clear")
                    yield Button("📋 Copiar", id="btn-copy")
                    yield Button("💾 Guardar", id="btn-save")

        yield Footer()

    def on_mount(self) -> None:
        self._setup_mode()
        self._setup_agent()

        # Mensaje de bienvenida
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(
            f"\n[bold cyan]━━━ OllamaResearch ━━━[/bold cyan]\n"
            f"[dim]Modelo:[/dim] [bold]{self.model}[/bold]\n"
            f"[dim]Modo:[/dim] [bold]{self._mode_label()}[/bold]\n"
            f"[dim]Atajos:[/dim] Ctrl+M cambiar modelo • Ctrl+N nueva sesión • Ctrl+L limpiar\n"
            f"[cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/cyan]\n"
        )

        # Si se pasó una query inicial, ejecutarla
        if self.initial_query:
            query_input = self.query_one("#query-input", Input)
            query_input.value = self.initial_query
            self._execute_query(self.initial_query)

    def _mode_label(self) -> str:
        return {
            "research": "🔬 Deep Research",
            "chat": "💬 Chat",
            "search": "🔍 Búsqueda Rápida",
        }.get(self.mode, self.mode)

    def _setup_mode(self) -> None:
        """Configura la UI según el modo activo."""
        mode_indicator = self.query_one("#mode-indicator", Static)
        mode_indicator.update(self._mode_label())

        # Actualizar botones de modo
        mode_map = {"research": "mode-research", "chat": "mode-chat", "search": "mode-web"}
        for m, btn_id in mode_map.items():
            btn = self.query_one(f"#{btn_id}", Button)
            if m == self.mode:
                btn.add_class("active-tab")
            else:
                btn.remove_class("active-tab")

    def _setup_agent(self) -> None:
        """Inicializa el agente de investigación."""
        config = get_config()
        search_engine = SearchEngine(
            engine=config.search_engine,
            tavily_key=config.tavily_api_key,
            serper_key=config.serper_api_key,
        )
        scraper = WebScraper(timeout=10.0, max_chars=config.research_config.get("max_tokens_per_source", 2000))
        self._agent = ResearchAgent(
            ollama_client=self.client,
            search_engine=search_engine,
            scraper=scraper,
            config=config.research_config,
        )

    @on(Input.Submitted, "#query-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if query and not self._is_processing:
            event.input.value = ""
            self._execute_query(query)

    @on(Button.Pressed, "#btn-send")
    def on_send_pressed(self) -> None:
        query_input = self.query_one("#query-input", Input)
        query = query_input.value.strip()
        if query and not self._is_processing:
            query_input.value = ""
            self._execute_query(query)

    @on(Button.Pressed, "#btn-stop")
    def on_stop_pressed(self) -> None:
        # Textual workers se cancelan con worker.cancel()
        for worker in self.app._workers:
            if not worker.is_done:
                worker.cancel()
        self._set_processing(False)
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write("\n[yellow]⚠️ Generación detenida por el usuario[/yellow]\n")

    @on(Button.Pressed, "#btn-clear")
    def action_clear_chat(self) -> None:
        self.query_one("#chat-log", RichLog).clear()
        self._messages = []
        self._sources = []
        self._current_result = ""
        sources_list = self.query_one("#sources-list", ListView)
        sources_list.clear()
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
            self._show_status("⚠️ Nada que copiar")

    @on(Button.Pressed, "#btn-save")
    def action_save_result(self) -> None:
        if self._current_result:
            self._save_to_file()

    def _save_to_file(self) -> None:
        from ollamaresearch.utils.config import get_data_dir
        import os
        data_dir = get_data_dir() / "results"
        data_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = data_dir / f"research_{timestamp}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# Investigación: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(self._current_result)
        self._show_status(f"💾 Guardado en: {filename}")

    def _show_status(self, message: str) -> None:
        status = self.query_one("#status-bar", Static)
        status.update(message)
        self.set_timer(3.0, lambda: status.update(""))

    def _set_processing(self, processing: bool) -> None:
        self._is_processing = processing
        send_btn = self.query_one("#btn-send", Button)
        stop_btn = self.query_one("#btn-stop", Button)
        query_input = self.query_one("#query-input", Input)

        send_btn.disabled = processing
        stop_btn.disabled = not processing
        query_input.disabled = processing

    def _execute_query(self, query: str) -> None:
        """Despacha la query según el modo activo."""
        if self.mode == "research":
            self._do_research(query)
        elif self.mode == "chat":
            self._do_chat(query)
        elif self.mode == "search":
            self._do_search(query)

    @work(exclusive=False)
    async def _do_research(self, query: str) -> None:
        """Ejecuta deep research en background."""
        self._set_processing(True)
        chat_log = self.query_one("#chat-log", RichLog)
        self._current_result = ""

        # Mostrar query del usuario
        chat_log.write(
            f"\n[bold cyan]┌─ Tú ───────────────────────────────[/bold cyan]\n"
            f"[white]{query}[/white]\n"
            f"[bold cyan]└────────────────────────────────────[/bold cyan]\n"
        )

        # Header de respuesta
        chat_log.write(
            f"\n[bold green]┌─ 🔬 OllamaResearch ({self.model}) ──────[/bold green]\n"
        )

        # Limpiar fuentes anteriores
        sources_list = self.query_one("#sources-list", ListView)
        sources_list.clear()
        self._sources = []

        async def handle_event(event: ResearchEvent):
            if event.type == EventType.STATUS:
                chat_log.write(f"[dim]{event.text}[/dim]\n")

            elif event.type == EventType.ITERATION:
                chat_log.write(
                    f"\n[bold yellow]{'─' * 40}[/bold yellow]\n"
                    f"[yellow]{event.text}[/yellow]\n"
                )

            elif event.type == EventType.SEARCH_START:
                chat_log.write(f"[dim cyan]{event.text}[/dim cyan]\n")

            elif event.type == EventType.SOURCE_FOUND:
                self._sources = event.sources
                self.query_one("#sources-title", Static).update(
                    f"🔗 FUENTES ({len(event.sources)})"
                )
                sources_list.clear()
                empty_msg = self.query_one("#sources-empty")
                empty_msg.display = len(event.sources) == 0

                for i, src in enumerate(event.sources[:20], 1):
                    await sources_list.append(SourceItem(src, i))

            elif event.type == EventType.SCRAPING:
                chat_log.write(f"[dim]{event.text}[/dim]\n")

            elif event.type == EventType.SYNTHESIZING:
                chat_log.write(f"[dim magenta]{event.text}[/dim magenta]\n")
                chat_log.write(
                    "\n[bold green]┌─ 📝 Informe Final ─────────────────[/bold green]\n"
                )

            elif event.type == EventType.CHUNK:
                chat_log.write(event.text)
                self._current_result += event.text

            elif event.type == EventType.DONE:
                chat_log.write(
                    f"\n[bold green]└─────────────────────────────────────[/bold green]\n"
                    f"[dim]{event.text}[/dim]\n"
                )

        try:
            result = await self._agent.research(query, self.model, handle_event)
            # Guardar en historial de mensajes
            self._messages.append({"role": "user", "content": query})
            self._messages.append({"role": "assistant", "content": result.report})

        except Exception as e:
            chat_log.write(f"\n[bold red]❌ Error: {str(e)}[/bold red]\n")

        self._set_processing(False)

    @work(exclusive=False)
    async def _do_chat(self, query: str) -> None:
        """Modo chat con streaming."""
        self._set_processing(True)
        chat_log = self.query_one("#chat-log", RichLog)
        self._current_result = ""

        chat_log.write(
            f"\n[bold cyan]┌─ Tú ───────────────────────────────[/bold cyan]\n"
            f"[white]{query}[/white]\n"
            f"[bold cyan]└────────────────────────────────────[/bold cyan]\n"
        )
        chat_log.write(
            f"\n[bold green]┌─ 🤖 {self.model} ─────────────────────[/bold green]\n"
        )

        self._messages.append({"role": "user", "content": query})

        async def handle_event(event: ResearchEvent):
            if event.type == EventType.CHUNK:
                chat_log.write(event.text)
                self._current_result += event.text
            elif event.type == EventType.DONE:
                chat_log.write(
                    f"\n[bold green]└────────────────────────────────────[/bold green]\n"
                )

        try:
            result = await self._agent.chat(self._messages, self.model, handle_event)
            self._messages.append({"role": "assistant", "content": result})
        except Exception as e:
            chat_log.write(f"\n[bold red]❌ Error: {str(e)}[/bold red]\n")

        self._set_processing(False)

    @work(exclusive=False)
    async def _do_search(self, query: str) -> None:
        """Búsqueda web rápida con resumen."""
        self._set_processing(True)
        chat_log = self.query_one("#chat-log", RichLog)
        self._current_result = ""

        chat_log.write(
            f"\n[bold cyan]┌─ Búsqueda ─────────────────────────[/bold cyan]\n"
            f"[white]{query}[/white]\n"
            f"[bold cyan]└────────────────────────────────────[/bold cyan]\n"
        )
        chat_log.write(
            f"\n[bold green]┌─ 🔍 Resultados ────────────────────[/bold green]\n"
        )

        sources_list = self.query_one("#sources-list", ListView)
        sources_list.clear()

        async def handle_event(event: ResearchEvent):
            if event.type == EventType.STATUS:
                chat_log.write(f"[dim]{event.text}[/dim]\n")
            elif event.type == EventType.SOURCE_FOUND:
                self._sources = event.sources
                self.query_one("#sources-title", Static).update(
                    f"🔗 FUENTES ({len(event.sources)})"
                )
                for i, src in enumerate(event.sources[:20], 1):
                    await sources_list.append(SourceItem(src, i))
                self.query_one("#sources-empty").display = len(event.sources) == 0
            elif event.type == EventType.CHUNK:
                chat_log.write(event.text)
                self._current_result += event.text
            elif event.type == EventType.DONE:
                chat_log.write(
                    f"\n[bold green]└────────────────────────────────────[/bold green]\n"
                    f"[dim]{event.text}[/dim]\n"
                )

        try:
            await self._agent.web_search_summary(query, self.model, handle_event)
        except Exception as e:
            chat_log.write(f"\n[bold red]❌ Error: {str(e)}[/bold red]\n")

        self._set_processing(False)

    # ─── Cambio de modo ──────────────────────────────────────────────────────

    @on(Button.Pressed, "#mode-research")
    def switch_research(self) -> None:
        self.mode = "research"
        self._setup_mode()

    @on(Button.Pressed, "#mode-chat")
    def switch_chat(self) -> None:
        self.mode = "chat"
        self._setup_mode()

    @on(Button.Pressed, "#mode-web")
    def switch_web(self) -> None:
        self.mode = "search"
        self._setup_mode()

    # ─── Acciones ────────────────────────────────────────────────────────────

    def action_change_model(self) -> None:
        """Vuelve al selector de modelos."""
        from ollamaresearch.tui.screens.model_selector import ModelSelectorScreen
        self.app.push_screen(
            ModelSelectorScreen(self.client, self.model, self.mode),
            callback=self._on_model_selected,
        )

    def _on_model_selected(self, result) -> None:
        if result:
            model_name, mode = result
            self.model = model_name
            self.mode = mode
            self._setup_mode()
            self.query_one("#model-indicator", Static).update(
                f"🤖 [bold cyan]{self.model}[/bold cyan]"
            )
            config = get_config()
            config.last_model = model_name
            config.last_mode = mode

    def action_new_session(self) -> None:
        self.action_clear_chat()

    def action_show_help(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(
            "\n[bold yellow]━━━ AYUDA ━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]\n"
            "[bold]Atajos de teclado:[/bold]\n"
            "  [cyan]Enter[/cyan]       Enviar pregunta\n"
            "  [cyan]Ctrl+M[/cyan]      Cambiar modelo\n"
            "  [cyan]Ctrl+N[/cyan]      Nueva sesión\n"
            "  [cyan]Ctrl+L[/cyan]      Limpiar pantalla\n"
            "  [cyan]Ctrl+C[/cyan]      Copiar respuesta\n"
            "  [cyan]Ctrl+S[/cyan]      Guardar respuesta\n"
            "  [cyan]Ctrl+Q[/cyan]      Salir\n"
            "  [cyan]F1[/cyan]          Esta ayuda\n"
            "\n[bold]Modos:[/bold]\n"
            "  [cyan]🔬 Deep Research[/cyan]  Investigación profunda con búsqueda web\n"
            "  [cyan]💬 Chat[/cyan]           Conversación directa con el modelo\n"
            "  [cyan]🔍 Búsqueda Rápida[/cyan] Búsqueda web con resumen del LLM\n"
            "[bold yellow]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]\n"
        )

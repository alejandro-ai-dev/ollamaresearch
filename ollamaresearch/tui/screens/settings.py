"""
Pantalla de configuración — API keys, motor de búsqueda, profundidad de investigación
"""
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static, Switch

from ollamaresearch.utils.config import get_config


DEPTH_OPTIONS = [("Ligero (1 iteración, rápido)", "light"),
                 ("Medio (3 iteraciones, balanceado)", "medium"),
                 ("Profundo (5 iteraciones, exhaustivo)", "deep")]

ENGINE_OPTIONS = [("DuckDuckGo (gratuito, sin API key)", "duckduckgo"),
                  ("Tavily (optimizado para AI)", "tavily"),
                  ("Serper (resultados de Google)", "serper")]


class SettingsScreen(Screen):
    """Pantalla de configuración del framework."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver"),
        Binding("ctrl+s", "action_save", "Guardar"),
    ]

    def compose(self) -> ComposeResult:
        cfg = get_config()
        yield Header(show_clock=True)

        with Container(id="settings-wrapper"):
            yield Static("⚙️  [bold cyan]Configuración[/bold cyan]", id="settings-title")
            yield Static(
                "Los cambios se guardan automáticamente",
                id="settings-subtitle",
            )

            with Vertical(id="settings-form"):
                # ── Sección: Ollama ──────────────────────────
                yield Static("🤖 CONEXIÓN OLLAMA", classes="section-header")

                with Horizontal(classes="form-row"):
                    yield Label("Host de Ollama:", classes="form-label")
                    yield Input(
                        value=cfg.ollama_host,
                        placeholder="http://localhost:11434",
                        id="input-ollama-host",
                    )

                # ── Sección: Motor de búsqueda ───────────────
                yield Static("🔍 MOTOR DE BÚSQUEDA", classes="section-header")

                with Horizontal(classes="form-row"):
                    yield Label("Motor:", classes="form-label")
                    yield Select(
                        [(label, val) for label, val in ENGINE_OPTIONS],
                        value=cfg.search_engine,
                        id="select-engine",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Tavily API Key:", classes="form-label")
                    yield Input(
                        value=cfg.tavily_api_key,
                        placeholder="tvly-xxxxx (opcional, gratis en tavily.com)",
                        password=True,
                        id="input-tavily-key",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Serper API Key:", classes="form-label")
                    yield Input(
                        value=cfg.serper_api_key,
                        placeholder="xxxx (opcional, en serper.dev)",
                        password=True,
                        id="input-serper-key",
                    )

                # ── Sección: Investigación ───────────────────
                yield Static("🔬 INVESTIGACIÓN", classes="section-header")

                with Horizontal(classes="form-row"):
                    yield Label("Profundidad:", classes="form-label")
                    yield Select(
                        [(label, val) for label, val in DEPTH_OPTIONS],
                        value=cfg.research_config.get("depth", "medium"),
                        id="select-depth",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Máx. fuentes:", classes="form-label")
                    yield Input(
                        value=str(cfg.research_config.get("max_sources", 8)),
                        placeholder="8",
                        id="input-max-sources",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Idioma respuesta:", classes="form-label")
                    yield Input(
                        value=cfg.research_config.get("language", "español"),
                        placeholder="español, english, français...",
                        id="input-language",
                    )

                # ── Sección: Interfaz ────────────────────────
                yield Static("🎨 INTERFAZ", classes="section-header")

                with Horizontal(classes="form-row"):
                    yield Label("Mostrar fuentes:", classes="form-label")
                    yield Switch(
                        value=cfg.get("ui.show_sources", True),
                        id="switch-sources",
                    )

                with Horizontal(classes="form-row"):
                    yield Label("Auto-copiar respuesta:", classes="form-label")
                    yield Switch(
                        value=cfg.get("ui.auto_copy", False),
                        id="switch-autocopy",
                    )

                # ── Info ─────────────────────────────────────
                yield Static("", id="settings-status")
                yield Static(
                    "[dim]💡 DuckDuckGo es gratuito y no requiere API key.\n"
                    "   Para Tavily: regístrate en tavily.com (1000 búsquedas/mes gratis)\n"
                    "   Para Serper: regístrate en serper.dev[/dim]",
                    id="settings-tip",
                )

            with Horizontal(id="settings-buttons"):
                yield Button("💾 Guardar", id="btn-save-settings", variant="primary")
                yield Button("✖ Cancelar", id="btn-cancel-settings")
                yield Button("🔄 Restaurar Defaults", id="btn-reset-settings")

        yield Footer()

    @on(Button.Pressed, "#btn-save-settings")
    def action_save(self) -> None:
        cfg = get_config()

        cfg.set("ollama_host", self.query_one("#input-ollama-host", Input).value)
        cfg.set("search_engine", self.query_one("#select-engine", Select).value)
        cfg.set("tavily_api_key", self.query_one("#input-tavily-key", Input).value)
        cfg.set("serper_api_key", self.query_one("#input-serper-key", Input).value)
        cfg.set("research.depth", self.query_one("#select-depth", Select).value)
        cfg.set("ui.show_sources", self.query_one("#switch-sources", Switch).value)
        cfg.set("ui.auto_copy", self.query_one("#switch-autocopy", Switch).value)

        try:
            max_sources = int(self.query_one("#input-max-sources", Input).value)
            cfg.set("research.max_sources", max_sources)
        except ValueError:
            pass

        cfg.set(
            "research.language",
            self.query_one("#input-language", Input).value,
        )

        self.query_one("#settings-status", Static).update(
            "[bold green]✅ Configuración guardada correctamente[/bold green]"
        )
        self.set_timer(2.0, self.app.pop_screen)

    @on(Button.Pressed, "#btn-cancel-settings")
    def on_cancel(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-reset-settings")
    def on_reset(self) -> None:
        from ollamaresearch.utils.config import DEFAULT_CONFIG
        cfg = get_config()
        cfg._data = dict(DEFAULT_CONFIG)
        cfg.save()
        self.query_one("#settings-status", Static).update(
            "[yellow]⚠️ Configuración restaurada a valores por defecto[/yellow]"
        )
        self.set_timer(1.5, lambda: self.app.pop_screen())

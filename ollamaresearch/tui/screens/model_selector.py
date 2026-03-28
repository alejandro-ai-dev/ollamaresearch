"""
Pantalla de selección de modelo — Primera pantalla al iniciar OllamaResearch
Muestra modelos locales y catálogo de modelos disponibles para descargar
"""
import asyncio
from typing import List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    ProgressBar,
    Static,
)

from ollamaresearch.core.ollama_client import ModelInfo, OllamaClient


class ModelItem(ListItem):
    """Elemento de lista para un modelo."""

    def __init__(self, model: ModelInfo) -> None:
        super().__init__()
        self.model = model

    def compose(self) -> ComposeResult:
        badge = "🟢 LOCAL" if self.model.local else "☁️  CATÁLOGO"
        badge_class = "badge-local" if self.model.local else "badge-cloud"
        size = self.model.size_display

        yield Horizontal(
            Static(f" {self.model.name}", classes="model-name"),
            Static(size, classes="model-size"),
            Static(badge, classes=f"model-badge {badge_class}"),
            classes="model-row",
        )


class ModelSelectorScreen(Screen):
    """
    Pantalla de selección de modelo.
    Muestra modelos locales y disponibles en el catálogo de Ollama.
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Volver", show=False),
        Binding("ctrl+r", "refresh_models", "Actualizar", show=True),
        Binding("p", "action_pull", "Descargar modelo", show=True),
        Binding("q", "app.quit", "Salir", show=True),
    ]

    def __init__(
        self,
        client: OllamaClient,
        current_model: str = "",
        initial_mode: str = "research",
    ):
        super().__init__()
        self.client = client
        self.current_model = current_model
        self.initial_mode = initial_mode
        self._local_models: List[ModelInfo] = []
        self._catalog_models: List[ModelInfo] = []
        self._selected_model: Optional[ModelInfo] = None
        self._selected_mode = initial_mode

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="selector-wrapper"):
            # Logo y título
            yield Static(
                "🔬 [bold cyan]OllamaResearch[/bold cyan]",
                id="logo",
            )
            yield Static(
                "Framework de [bold]Deep Research[/bold] con IA • Multi-plataforma",
                id="subtitle",
            )

            # Estado de Ollama
            yield Static("⟳ Conectando con Ollama...", id="ollama-status")

            # Selector de modo
            with Horizontal(id="mode-selector"):
                yield Button("🔬 Deep Research", id="btn-research", classes="mode-btn active-mode")
                yield Button("💬 Chat", id="btn-chat", classes="mode-btn")
                yield Button("🔍 Búsqueda Rápida", id="btn-search", classes="mode-btn")
                yield Button("💻 Código", id="btn-code", classes="mode-btn")

            # Listas de modelos
            with Horizontal(id="model-columns"):
                # Columna izquierda — Modelos locales
                with Vertical(id="local-column", classes="model-column"):
                    yield Static("🟢 MODELOS INSTALADOS", classes="column-title")
                    yield ListView(id="local-list")
                    yield LoadingIndicator(id="local-loading")

                # Separador
                yield Static("│", id="column-divider")

                # Columna derecha — Catálogo
                with Vertical(id="catalog-column", classes="model-column"):
                    yield Static("☁️  CATÁLOGO OLLAMA", classes="column-title")
                    yield ListView(id="catalog-list")
                    yield LoadingIndicator(id="catalog-loading")

            # Panel de descarga
            with Container(id="download-panel", classes="hidden"):
                yield Static("", id="download-status")
                yield ProgressBar(id="download-progress", total=100, show_eta=False)

            # Info del modelo seleccionado
            yield Static("", id="model-info")

            # Botones de acción
            with Horizontal(id="action-buttons"):
                yield Button(
                    "✅ Seleccionar Modelo",
                    id="btn-select",
                    variant="primary",
                    disabled=True,
                )
                yield Button("📥 Descargar", id="btn-pull", disabled=True)
                yield Button("⚙️  Configuración", id="btn-settings")

        yield Footer()

    def on_mount(self) -> None:
        self._load_models()

    @work(exclusive=True)
    async def _load_models(self) -> None:
        """Carga modelos en background."""
        # Verificar Ollama
        is_running = await self.client.check_running()
        status_widget = self.query_one("#ollama-status", Static)

        if is_running:
            status_widget.update("● [bold green]Ollama está corriendo[/bold green]")
        else:
            # Intentar iniciar
            status_widget.update("⟳ [yellow]Iniciando Ollama...[/yellow]")
            started = await self.client.start_server()
            if started:
                status_widget.update("● [bold green]Ollama iniciado correctamente[/bold green]")
            else:
                status_widget.update(
                    "✗ [bold red]Ollama no disponible[/bold red] — "
                    "[dim]Instálalo en ollama.com[/dim]"
                )

        # Cargar modelos locales
        self._local_models = await self.client.list_local_models()
        local_list = self.query_one("#local-list", ListView)
        loading_local = self.query_one("#local-loading", LoadingIndicator)

        loading_local.display = False

        if self._local_models:
            for m in self._local_models:
                await local_list.append(ModelItem(m))
        else:
            await local_list.append(
                ListItem(Static("[dim]No hay modelos instalados[/dim]\n[dim]Descarga uno del catálogo →[/dim]"))
            )

        # Cargar catálogo
        self._catalog_models = await self.client.list_catalog_models()
        catalog_list = self.query_one("#catalog-list", ListView)
        loading_catalog = self.query_one("#catalog-loading", LoadingIndicator)
        loading_catalog.display = False

        for m in self._catalog_models:
            await catalog_list.append(ModelItem(m))

        # Seleccionar modelo anterior si existe
        if self.current_model and self._local_models:
            for i, m in enumerate(self._local_models):
                if m.name == self.current_model:
                    local_list.index = i
                    self._selected_model = m
                    self._update_select_button()
                    break

    @on(ListView.Selected, "#local-list")
    def on_local_selected(self, event: ListView.Selected) -> None:
        """Modelo local seleccionado."""
        if isinstance(event.item, ModelItem):
            self._selected_model = event.item.model
            self._update_model_info()
            self._update_select_button()
            # Limpiar selección en catálogo
            self.query_one("#catalog-list", ListView).index = None

    @on(ListView.Selected, "#catalog-list")
    def on_catalog_selected(self, event: ListView.Selected) -> None:
        """Modelo de catálogo seleccionado."""
        if isinstance(event.item, ModelItem):
            self._selected_model = event.item.model
            self._update_model_info()
            self._update_select_button()
            # Limpiar selección local
            self.query_one("#local-list", ListView).index = None

    def _update_model_info(self) -> None:
        if not self._selected_model:
            return
        m = self._selected_model
        status = "Instalado" if m.local else "No instalado — requiere descarga"
        tags = " ".join([f"[{t}]" for t in m.tags]) if m.tags else ""
        info = f" {m.name}  •  {m.size_display}  •  {status}  {tags}"
        self.query_one("#model-info", Static).update(info)

    def _update_select_button(self) -> None:
        btn = self.query_one("#btn-select", Button)
        pull_btn = self.query_one("#btn-pull", Button)

        if self._selected_model:
            if self._selected_model.local:
                btn.disabled = False
                btn.label = "✅ Usar este modelo"
                pull_btn.disabled = True
            else:
                btn.disabled = True
                btn.label = "⬇️  Descarga requerida"
                pull_btn.disabled = False

    @on(Button.Pressed, "#btn-select")
    def on_select_pressed(self) -> None:
        if self._selected_model and self._selected_model.local:
            self.dismiss((self._selected_model.name, self._selected_mode))

    @on(Button.Pressed, "#btn-pull")
    async def on_pull_pressed(self) -> None:
        if self._selected_model and not self._selected_model.local:
            self._download_model(self._selected_model.name)

    @work(exclusive=True)
    async def _download_model(self, model_name: str) -> None:
        """Descarga un modelo con barra de progreso."""
        panel = self.query_one("#download-panel")
        panel.remove_class("hidden")
        status = self.query_one("#download-status", Static)
        progress = self.query_one("#download-progress", ProgressBar)

        async def on_progress(st: str, pct: int):
            status.update(f"📥 {st}")
            if pct > 0:
                progress.advance(pct - progress.progress)

        status.update(f"📥 Descargando {model_name}...")
        success = await self.client.pull_model(model_name, on_progress)

        if success:
            status.update(f"✅ Modelo {model_name} descargado correctamente")
            # Recargar lista local
            await asyncio.sleep(1)
            panel.add_class("hidden")
            self._load_models()
        else:
            status.update(f"❌ Error al descargar {model_name}")

    @on(Button.Pressed, "#btn-research")
    def on_research_mode(self) -> None:
        self._selected_mode = "research"
        self._update_mode_buttons("btn-research")

    @on(Button.Pressed, "#btn-chat")
    def on_chat_mode(self) -> None:
        self._selected_mode = "chat"
        self._update_mode_buttons("btn-chat")

    @on(Button.Pressed, "#btn-search")
    def on_search_mode(self) -> None:
        self._selected_mode = "search"
        self._update_mode_buttons("btn-search")

    @on(Button.Pressed, "#btn-code")
    def on_code_mode(self) -> None:
        self._selected_mode = "code"
        self._update_mode_buttons("btn-code")
        self.query_one("#model-info", Static).update(
            " 💡 Para modo Código se recomiendan: codellama, deepseek-r1:7b, qwen2.5:7b"
        )

    def _update_mode_buttons(self, active_id: str) -> None:
        for btn_id in ["btn-research", "btn-chat", "btn-search", "btn-code"]:
            btn = self.query_one(f"#{btn_id}", Button)
            if btn_id == active_id:
                btn.add_class("active-mode")
            else:
                btn.remove_class("active-mode")

    @on(Button.Pressed, "#btn-settings")
    def on_settings_pressed(self) -> None:
        from ollamaresearch.tui.screens.settings import SettingsScreen
        self.app.push_screen(SettingsScreen())

    def action_refresh_models(self) -> None:
        """Recarga la lista de modelos."""
        local_list = self.query_one("#local-list", ListView)
        catalog_list = self.query_one("#catalog-list", ListView)
        local_list.clear()
        catalog_list.clear()
        self.query_one("#local-loading", LoadingIndicator).display = True
        self.query_one("#catalog-loading", LoadingIndicator).display = True
        self._load_models()

    def action_pull(self) -> None:
        if self._selected_model and not self._selected_model.local:
            self._download_model(self._selected_model.name)

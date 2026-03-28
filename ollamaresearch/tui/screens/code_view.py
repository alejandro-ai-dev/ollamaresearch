"""
CodeView — Pantalla del modo Código para OllamaResearch
Layout: terminal output (izq) + árbol de proyecto (der)
"""
import asyncio
from pathlib import Path
from typing import Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static
from textual.widget import Widget

from ollamaresearch.core.code_agent import CodeAgent, CodeEvent, CodeEventType, WORKSPACE_ROOT
from ollamaresearch.core.ollama_client import OllamaClient


# ─── Widgets de terminal ──────────────────────────────────────────────────────

class TermLine(Widget):
    """Línea individual en el panel de terminal, con color por tipo."""
    DEFAULT_CSS = """
    TermLine { height: auto; padding: 0 1; }
    TermLine.status     { color: #7aa2f7; }
    TermLine.plan       { color: #e0af68; background: #1a1b2e; border-left: thick #e0af68; padding: 0 1; margin: 1 0; }
    TermLine.action     { color: #c0caf5; }
    TermLine.output     { color: #565f89; background: #0a0b14; padding: 0 2; font-family: monospace; }
    TermLine.success    { color: #9ece6a; }
    TermLine.error      { color: #f7768e; }
    TermLine.warning    { color: #e0af68; }
    TermLine.file       { color: #9ece6a; text-style: bold; }
    TermLine.dir        { color: #7aa2f7; }
    TermLine.ask        { color: #bb9af7; background: #1a1a2e; border: solid #bb9af7; padding: 0 1; margin: 1 0; }
    TermLine.done       { color: #9ece6a; background: #1a2d1a; border-left: thick #9ece6a; padding: 0 1; margin: 1 0; }
    TermLine.chunk      { color: #c0caf5; }
    """
    def __init__(self, text: str, style: str = "status"):
        super().__init__(classes=style)
        self._text = text
        self._static: Optional[Static] = None

    def compose(self) -> ComposeResult:
        self._static = Static(self._text)
        yield self._static

    def append(self, text: str) -> None:
        self._text += text
        if self._static:
            try:
                self._static.update(self._text)
            except Exception:
                pass


class AskConfirmWidget(Widget):
    """Bloque de confirmación estilo prompt de terminal."""
    DEFAULT_CSS = """
    AskConfirmWidget {
        height: auto; background: #1a1a2e;
        border: solid #bb9af7; padding: 1 2; margin: 1 0;
    }
    AskConfirmWidget .ask-text  { color: #bb9af7; text-style: bold; }
    AskConfirmWidget .ask-btns  { height: 3; margin-top: 1; align: left middle; }
    AskConfirmWidget Button     { margin-right: 1; }
    """
    def __init__(self, step: Dict, step_index: int, future: asyncio.Future):
        super().__init__()
        self._step    = step
        self._index   = step_index
        self._future  = future

    def compose(self) -> ComposeResult:
        desc = self._step.get("description", self._step.get("action", ""))
        pkgs = self._step.get("packages", [])
        cmd  = self._step.get("cmd", "")
        detail = f"  Paquetes: {', '.join(pkgs)}" if pkgs else (f"  Comando: {cmd}" if cmd else "")
        yield Static(f"⏸️  Paso {self._index}: {desc}\n{detail}", classes="ask-text")
        with Horizontal(classes="ask-btns"):
            yield Button("✅ Ejecutar", id=f"ask-yes-{self._index}", variant="success")
            yield Button("⏭️ Omitir",   id=f"ask-no-{self._index}")

    @on(Button.Pressed)
    def on_btn(self, event: Button.Pressed) -> None:
        if not self._future.done():
            self._future.set_result("yes" in event.button.id)
        self.remove()


class ProjectItem(ListItem):
    """Ítem de proyecto en el picker."""
    def __init__(self, path: Path):
        super().__init__()
        self.project_path = path

    def compose(self) -> ComposeResult:
        size = sum(
            f.stat().st_size for f in self.project_path.rglob("*")
            if f.is_file() and ".venv" not in f.parts
        ) if self.project_path.exists() else 0
        size_str = f"{size/1024:.0f} KB" if size < 1_000_000 else f"{size/1_000_000:.1f} MB"
        yield Vertical(
            Static(f"📁 [bold]{self.project_path.name}[/bold]", classes="proj-name"),
            Static(f"[dim]{size_str}[/dim]", classes="proj-size"),
        )


# ─── Pantalla principal ───────────────────────────────────────────────────────

class CodeView(Screen):
    """
    Vista del modo Código.
    Layout:
      - top-bar: modelo + modo + botones de autonomía
      - main:    terminal output (izq 2/3) | árbol + proyectos (der 1/3)
      - bottom:  input + botones de acción
    """

    DEFAULT_CSS = """
    CodeView {
        background: #0a0b14;
    }

    #code-topbar {
        height: 2; background: #1a1b2e;
        padding: 0 2; border-bottom: solid #2a2d3e;
        align: left middle;
    }
    #code-model-lbl { width: auto; margin-right: 3; color: #7aa2f7; text-style: bold; }
    #code-mode-lbl  { width: auto; margin-right: 3; color: #bb9af7; }
    #code-ws-lbl    { width: 1fr; color: #3b3f5a; }

    #auto-toggle    { width: auto; height: 2; margin-left: 1; }
    #auto-toggle Button { height: 2; padding: 0 1; border: solid #2a2d3e; background: #13141f; color: #565f89; }
    #auto-toggle Button.-primary { background: #283447; color: #7dcfff; border: solid #7dcfff; text-style: bold; }

    #code-main { height: 1fr; }

    /* Panel izquierdo: terminal */
    #terminal-panel { width: 2fr; border-right: solid #2a2d3e; }
    #terminal-header {
        background: #13141f; color: #565f89; text-style: bold;
        padding: 0 1; height: 2; border-bottom: solid #2a2d3e;
    }
    #terminal-scroll {
        background: #0a0b14; padding: 0; height: 1fr;
        scrollbar-color: #2a2d3e #0a0b14;
    }

    /* Panel derecho: árbol + proyectos */
    #right-code-panel { width: 1fr; background: #0d0f1a; }

    #tree-header {
        background: #13141f; color: #9ece6a; text-style: bold;
        padding: 0 1; height: 2; border-bottom: solid #2a2d3e;
    }
    #tree-scroll   { height: 1fr; padding: 0 1; }
    #tree-content  { color: #565f89; height: auto; }

    #projects-header {
        background: #13141f; color: #e0af68; text-style: bold;
        padding: 0 1; height: 2;
        border-top: solid #2a2d3e; border-bottom: solid #2a2d3e;
        margin-top: 1;
    }
    #projects-list { height: 8; background: #0d0f1a; border-bottom: solid #2a2d3e; }

    .proj-name { color: #c0caf5; height: 1; }
    .proj-size { color: #565f89; height: 1; }

    ListItem:hover       { background: #1f2235; }
    ListItem.-highlighted { background: #283457; }

    /* Input area */
    #code-input-area {
        height: auto; background: #13141f;
        border-top: solid #2a2d3e; padding: 1 2;
    }
    #code-input {
        background: #0a0b14; border: solid #2a2d3e;
        color: #c0caf5; height: 3; margin-bottom: 1;
    }
    #code-input:focus { border: solid #bb9af7; }
    #code-input-actions { height: 3; align: left middle; }
    #code-input-actions Button { margin-right: 1; height: 3; }

    #btn-code-send    { background: #2a1f3d; color: #bb9af7; border: solid #bb9af7; text-style: bold; }
    #btn-code-send:hover { background: #3d2d5c; }
    #btn-code-stop    { color: #f7768e; border: solid #f7768e; }
    #btn-code-stop:hover { background: #2d1a1e; }
    #btn-open-project { color: #e0af68; border: solid #e0af68; }
    #btn-new-session  { color: #7aa2f7; border: solid #2a2d3e; }
    #btn-open-folder  { color: #9ece6a; border: solid #2a2d3e; }
    """

    BINDINGS = [
        Binding("ctrl+q",      "app.quit",          "Salir"),
        Binding("ctrl+m",      "change_model",       "Modelo"),
        Binding("ctrl+n",      "new_session",        "Nueva sesión"),
        Binding("ctrl+l",      "clear_terminal",     "Limpiar"),
        Binding("ctrl+o",      "open_project",       "Abrir proyecto"),
        Binding("escape",      "change_model",       "Cambiar modo"),
    ]

    def __init__(self, client: OllamaClient, model: str, initial_query: str = ""):
        super().__init__()
        self.client        = client
        self.model         = model
        self.initial_query = initial_query

        self._autonomy   = "semi"
        self._agent      = CodeAgent(client, autonomy="semi")
        self._processing = False
        self._confirm_futures: Dict[int, asyncio.Future] = {}
        self._step_index = 0
        self._current_chunk_line: Optional[TermLine] = None
        self._active_project: Optional[Path] = None

    # ─── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="code-topbar"):
            yield Static(f"🤖 {self.model}", id="code-model-lbl")
            yield Static("💻 Modo Código", id="code-mode-lbl")
            yield Static(f"📁 {WORKSPACE_ROOT}", id="code-ws-lbl")
            with Horizontal(id="auto-toggle"):
                yield Button("🔶 Semi-auto", id="btn-semi", classes="")
                yield Button("⚡ Autónomo",  id="btn-auto", classes="")

        with Horizontal(id="code-main"):
            # ── Terminal panel ────────────────────────────────────────────────
            with Vertical(id="terminal-panel"):
                yield Static("⬛ TERMINAL", id="terminal-header")
                with VerticalScroll(id="terminal-scroll"):
                    yield TermLine(
                        "💻 [bold cyan]OllamaResearch — Modo Código[/bold cyan]\n"
                        f"[dim]Workspace: {WORKSPACE_ROOT}[/dim]\n"
                        "[dim]Describe qué proyecto quieres crear o mejorar.[/dim]\n"
                        "[dim]Ejemplos: 'crea un port scanner en Python' | 'mejora el proyecto mi_scanner'[/dim]",
                        "status",
                    )

            # ── Right panel ───────────────────────────────────────────────────
            with Vertical(id="right-code-panel"):
                yield Static("🌲 PROYECTO ACTIVO", id="tree-header")
                with VerticalScroll(id="tree-scroll"):
                    yield Static("[dim]Sin proyecto activo[/dim]", id="tree-content")

                yield Static("📂 PROYECTOS EXISTENTES", id="projects-header")
                yield ListView(id="projects-list")

        with Container(id="code-input-area"):
            yield Input(
                placeholder="Describe el proyecto o mejora... (Enter = ejecutar)",
                id="code-input",
            )
            with Horizontal(id="code-input-actions"):
                yield Button("💻 Ejecutar",        id="btn-code-send",    variant="primary")
                yield Button("⏹ Detener",          id="btn-code-stop",    disabled=True)
                yield Button("📂 Abrir proyecto",   id="btn-open-project")
                yield Button("📋 Nueva sesión",     id="btn-new-session")
                yield Button("📁 Abrir carpeta",    id="btn-open-folder")

        yield Footer()

    # ─── Mount ────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._set_autonomy("semi")
        self._load_existing_projects()
        if self.initial_query:
            self.query_one("#code-input", Input).value = self.initial_query

    def _load_existing_projects(self) -> None:
        projects_list = self.query_one("#projects-list", ListView)
        projects = self._agent.list_projects()
        if projects:
            for p in projects[:15]:
                projects_list.append(ProjectItem(p))
        else:
            projects_list.append(ListItem(Static("[dim]No hay proyectos aún[/dim]")))

    # ─── Autonomía ────────────────────────────────────────────────────────────

    def _set_autonomy(self, mode: str) -> None:
        self._autonomy = mode
        self._agent.autonomy = mode
        semi = self.query_one("#btn-semi", Button)
        auto = self.query_one("#btn-auto", Button)
        if mode == "semi":
            semi.add_class("-primary")
            auto.remove_class("-primary")
        else:
            auto.add_class("-primary")
            semi.remove_class("-primary")

    @on(Button.Pressed, "#btn-semi")
    def sw_semi(self) -> None:
        self._set_autonomy("semi")
        self._log("🔶 Modo Semi-autónomo: pausará antes de instalar paquetes o ejecutar comandos.", "status")

    @on(Button.Pressed, "#btn-auto")
    def sw_auto(self) -> None:
        self._set_autonomy("auto")
        self._log("⚡ Modo Autónomo: ejecuta todo dentro del sandbox sin pausas.", "warning")

    # ─── Envío ────────────────────────────────────────────────────────────────

    @on(Input.Submitted, "#code-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        q = event.value.strip()
        if q and not self._processing:
            event.input.value = ""
            self._run_agent(q)

    @on(Button.Pressed, "#btn-code-send")
    def on_send(self) -> None:
        inp = self.query_one("#code-input", Input)
        q = inp.value.strip()
        if q and not self._processing:
            inp.value = ""
            self._run_agent(q)

    @on(Button.Pressed, "#btn-code-stop")
    def on_stop(self) -> None:
        for w in self.app._workers:
            if not w.is_done:
                w.cancel()
        # Resolver cualquier future pendiente como "no"
        for fut in self._confirm_futures.values():
            if not fut.done():
                fut.set_result(False)
        self._confirm_futures.clear()
        self._set_processing(False)
        self._log("⚠️  Ejecución detenida.", "warning")

    # ─── Worker principal ─────────────────────────────────────────────────────

    @work(exclusive=False)
    async def _run_agent(self, objective: str) -> None:
        self._set_processing(True)
        self._current_chunk_line = None
        self._step_index = 0

        # Determinar si se quiere editar un proyecto existente
        existing = self._active_project

        scroll = self.query_one("#terminal-scroll", VerticalScroll)
        await scroll.mount(TermLine(f"\n▶ {objective}", "plan"))

        async def event_cb(ev: CodeEvent) -> None:
            await self._handle_event(ev)

        async def confirm_cb(step: Dict) -> bool:
            return await self._ask_user_confirm(step)

        try:
            await self._agent.generate_project(
                objective=objective,
                model=self.model,
                event_cb=event_cb,
                confirm_cb=confirm_cb if self._autonomy == "semi" else None,
                existing_project=existing,
            )
        except Exception as exc:
            await self._log_async(f"❌ Error inesperado: {exc}", "error")

        self._set_processing(False)
        # Actualizar árbol y lista de proyectos tras completar
        if self._agent._project_path:
            self._active_project = self._agent._project_path
            self._refresh_tree(self._active_project)
        self._refresh_project_list()

    # ─── Manejador de eventos del agente ──────────────────────────────────────

    async def _handle_event(self, ev: CodeEvent) -> None:
        scroll = self.query_one("#terminal-scroll", VerticalScroll)

        style_map = {
            CodeEventType.STATUS:         "status",
            CodeEventType.PLAN:           "plan",
            CodeEventType.ACTION:         "action",
            CodeEventType.ACTION_OUTPUT:  "output",
            CodeEventType.ACTION_SUCCESS: "success",
            CodeEventType.ACTION_ERROR:   "error",
            CodeEventType.FILE_CREATED:   "file",
            CodeEventType.DIR_CREATED:    "dir",
            CodeEventType.WARNING:        "warning",
            CodeEventType.DONE:           "done",
        }

        if ev.type == CodeEventType.CHUNK:
            # Streaming: agregar a la línea de chunk actual
            if self._current_chunk_line is None:
                self._current_chunk_line = TermLine("", "chunk")
                await scroll.mount(self._current_chunk_line)
            self._current_chunk_line.append(ev.text)
            scroll.scroll_end(animate=False)

        elif ev.type == CodeEventType.STATUS and not ev.text:
            # "status vacío" = fin del chunk — resetear línea de chunk
            self._current_chunk_line = None

        elif ev.type == CodeEventType.ASK_USER:
            # No viene del agente directamente, viene del confirm_cb
            pass

        elif ev.type in (CodeEventType.FILE_CREATED, CodeEventType.DIR_CREATED):
            self._current_chunk_line = None
            await scroll.mount(TermLine(ev.text, style_map[ev.type]))
            # Actualizar árbol en vivo
            if self._agent._project_path and self._agent._project_path.exists():
                self._refresh_tree(self._agent._project_path)
            scroll.scroll_end(animate=False)

        elif ev.type == CodeEventType.DONE:
            self._current_chunk_line = None
            await scroll.mount(TermLine(ev.text, "done"))
            scroll.scroll_end(animate=False)

        else:
            self._current_chunk_line = None
            style = style_map.get(ev.type, "status")
            if ev.text:
                await scroll.mount(TermLine(ev.text, style))
                scroll.scroll_end(animate=False)

    # ─── Confirmación usuario (modo semi) ─────────────────────────────────────

    async def _ask_user_confirm(self, step: Dict) -> bool:
        """Monta un widget de confirmación y espera la respuesta del usuario."""
        self._step_index += 1
        loop   = asyncio.get_event_loop()
        future = loop.create_future()
        self._confirm_futures[self._step_index] = future

        scroll = self.query_one("#terminal-scroll", VerticalScroll)
        widget = AskConfirmWidget(step, self._step_index, future)
        await scroll.mount(widget)
        scroll.scroll_end(animate=False)

        result = await future
        self._confirm_futures.pop(self._step_index, None)
        return result

    # ─── Proyectos existentes ─────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-open-project")
    def on_open_project(self) -> None:
        """Carga el proyecto seleccionado en la lista."""
        lst = self.query_one("#projects-list", ListView)
        highlighted = lst.highlighted_child
        if highlighted and isinstance(highlighted, ProjectItem):
            self._load_project(highlighted.project_path)
        else:
            self._log("⚠️  Selecciona un proyecto de la lista primero.", "warning")

    @on(ListView.Selected, "#projects-list")
    def on_project_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ProjectItem):
            self._load_project(event.item.project_path)

    def _load_project(self, path: Path) -> None:
        self._active_project = path
        self._agent._project_path = path
        venv = path / ".venv"
        self._agent._venv_path = venv if venv.exists() else None
        self._refresh_tree(path)
        self._log(
            f"📂 Proyecto cargado: [bold]{path.name}[/bold]\n"
            f"[dim]Describe qué quieres mejorar o agregar y pulsa Ejecutar.[/dim]",
            "plan",
        )
        # Leer contexto del proyecto para mostrarlo
        ctx_preview = self._agent.get_project_tree(path)
        self._log("\n".join(ctx_preview[:30]), "output")

    @on(Button.Pressed, "#btn-open-folder")
    def on_open_folder(self) -> None:
        """Abre la carpeta del workspace en el explorador de archivos del OS."""
        import subprocess
        import platform
        ws = str(WORKSPACE_ROOT)
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", ws])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", ws])
            else:
                subprocess.Popen(["xdg-open", ws])
        except Exception as exc:
            self._log(f"❌ No se pudo abrir: {exc}", "error")

    # ─── UI helpers ───────────────────────────────────────────────────────────

    def _refresh_tree(self, project_path: Path) -> None:
        lines = self._agent.get_project_tree(project_path)
        tree_text = "\n".join(lines) if lines else "[dim](vacío)[/dim]"
        try:
            self.query_one("#tree-content", Static).update(tree_text)
            self.query_one("#tree-header", Static).update(f"🌲 {project_path.name.upper()}")
        except Exception:
            pass

    def _refresh_project_list(self) -> None:
        try:
            lst = self.query_one("#projects-list", ListView)
            lst.clear()
            projects = self._agent.list_projects()
            if projects:
                for p in projects[:15]:
                    lst.append(ProjectItem(p))
            else:
                lst.append(ListItem(Static("[dim]No hay proyectos aún[/dim]")))
        except Exception:
            pass

    def _log(self, text: str, style: str = "status") -> None:
        scroll = self.query_one("#terminal-scroll", VerticalScroll)
        scroll.mount(TermLine(text, style))

    async def _log_async(self, text: str, style: str = "status") -> None:
        scroll = self.query_one("#terminal-scroll", VerticalScroll)
        await scroll.mount(TermLine(text, style))

    def _set_processing(self, val: bool) -> None:
        self._processing = val
        self.query_one("#btn-code-send", Button).disabled = val
        self.query_one("#btn-code-stop", Button).disabled = not val
        self.query_one("#code-input",    Input).disabled  = val

    # ─── Acciones generales ───────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-new-session")
    def action_new_session(self) -> None:
        self._active_project = None
        self._agent._project_path = None
        self._agent._venv_path    = None
        try:
            scroll = self.query_one("#terminal-scroll", VerticalScroll)
            scroll.remove_children()
            scroll.mount(TermLine(
                "💻 [bold cyan]OllamaResearch — Modo Código[/bold cyan]\n"
                "[dim]Nueva sesión iniciada. Describe tu proyecto.[/dim]",
                "status",
            ))
            self.query_one("#tree-content", Static).update("[dim]Sin proyecto activo[/dim]")
            self.query_one("#tree-header",  Static).update("🌲 PROYECTO ACTIVO")
        except Exception:
            pass

    def action_clear_terminal(self) -> None:
        try:
            scroll = self.query_one("#terminal-scroll", VerticalScroll)
            scroll.remove_children()
        except Exception:
            pass

    def action_change_model(self) -> None:
        from ollamaresearch.tui.screens.model_selector import ModelSelectorScreen
        self.app.push_screen(
            ModelSelectorScreen(self.client, self.model, "code"),
            callback=self._on_model_selected,
        )

    def _on_model_selected(self, result) -> None:
        if result:
            model, mode = result
            self.model = model
            try:
                self.query_one("#code-model-lbl", Static).update(f"🤖 {model}")
            except Exception:
                pass

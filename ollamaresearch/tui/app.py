"""
Aplicación principal TUI — OllamaResearch
Framework de Deep Research con interfaz de terminal completa
"""
from textual.app import App, ComposeResult
from textual.binding import Binding

from ollamaresearch.core.ollama_client import OllamaClient
from ollamaresearch.utils.config import get_config


class OllamaResearchApp(App):
    """
    Aplicación TUI principal de OllamaResearch.
    Gestiona el flujo de pantallas y la configuración global.
    """

    TITLE = "OllamaResearch"
    SUB_TITLE = "Deep Research con IA • Multi-plataforma"

    CSS = """
    /* ═══════════════════════════════════════════════════════════════ */
    /* Tema global — Paleta oscura estilo IDE moderno                 */
    /* ═══════════════════════════════════════════════════════════════ */

    Screen {
        background: #0d0f1a;
        color: #c0caf5;
    }

    Header {
        background: #1a1b2e;
        color: #7aa2f7;
        text-style: bold;
    }

    Footer {
        background: #1a1b2e;
        color: #565f89;
    }

    /* ─── Selector de Modelos ────────────────────────────────────── */

    #selector-wrapper {
        padding: 1 2;
        height: 100%;
    }

    #logo {
        color: #7aa2f7;
        text-align: center;
        text-style: bold;
        padding: 1 0 0 0;
        height: 3;
    }

    #subtitle {
        color: #565f89;
        text-align: center;
        height: 2;
    }

    #ollama-status {
        background: #13141f;
        border: solid #2a2d3e;
        padding: 0 2;
        height: 3;
        content-align: center middle;
        margin: 0 0 1 0;
    }

    #mode-selector {
        height: 3;
        margin: 0 0 1 0;
        align: center middle;
    }

    .mode-btn {
        background: #1a1b2e;
        color: #565f89;
        border: solid #2a2d3e;
        margin: 0 1;
    }

    .mode-btn:hover {
        background: #1f2235;
        color: #c0caf5;
    }

    .active-mode {
        background: #283457;
        color: #7aa2f7;
        border: solid #7aa2f7;
        text-style: bold;
    }

    #model-columns {
        height: 1fr;
        margin: 0 0 1 0;
    }

    .model-column {
        width: 1fr;
        border: solid #2a2d3e;
        background: #13141f;
        padding: 0;
    }

    #column-divider {
        width: 1;
        color: #2a2d3e;
        content-align: center middle;
    }

    .column-title {
        background: #1a1b2e;
        color: #7aa2f7;
        text-style: bold;
        padding: 0 1;
        height: 2;
    }

    ListView {
        background: #13141f;
        border: none;
    }

    ListItem {
        background: #13141f;
        padding: 0 1;
    }

    ListItem:hover {
        background: #1f2235;
    }

    ListItem.-highlighted {
        background: #283457;
    }

    .model-row {
        height: 2;
        align: left middle;
    }

    .model-name {
        width: 1fr;
        color: #c0caf5;
    }

    .model-size {
        width: 8;
        color: #e0af68;
        text-align: right;
    }

    .model-badge {
        width: 12;
        text-align: right;
    }

    .badge-local {
        color: #9ece6a;
    }

    .badge-cloud {
        color: #7aa2f7;
    }

    #download-panel {
        background: #1a1b2e;
        border: solid #7aa2f7;
        padding: 0 2;
        height: 4;
        margin: 0 0 1 0;
    }

    #download-panel.hidden {
        display: none;
    }

    #download-status {
        height: 2;
    }

    #model-info {
        background: #13141f;
        color: #565f89;
        padding: 0 1;
        height: 2;
        border: solid #2a2d3e;
        margin: 0 0 1 0;
    }

    #action-buttons {
        height: 3;
        align: left middle;
    }

    #action-buttons Button {
        margin: 0 1 0 0;
    }

    Button {
        background: #1a1b2e;
        color: #c0caf5;
        border: solid #2a2d3e;
    }

    Button:hover {
        background: #1f2235;
        border: solid #565f89;
    }

    Button:focus {
        border: solid #7aa2f7;
    }

    Button.-primary {
        background: #283457;
        color: #7aa2f7;
        border: solid #7aa2f7;
        text-style: bold;
    }

    Button.-primary:hover {
        background: #3d4f7c;
    }

    LoadingIndicator {
        height: 2;
        color: #7aa2f7;
    }

    /* ─── Vista de Investigación ─────────────────────────────────── */

    #research-wrapper {
        height: 100%;
        padding: 0;
    }

    #top-bar {
        height: 2;
        background: #1a1b2e;
        padding: 0 2;
        border-bottom: solid #2a2d3e;
        align: left middle;
    }

    #model-indicator { width: auto; margin-right: 3; }

    #status-bar {
        width: 1fr;
        text-align: right;
        color: #e0af68;
    }

    #mode-bar {
        height: 3;
        background: #13141f;
        border-bottom: solid #2a2d3e;
        padding: 0 1;
        align: left middle;
    }

    .mode-tab {
        background: #13141f;
        color: #565f89;
        border: solid #2a2d3e;
        margin: 0 1 0 0;
        height: 3;
    }
    .mode-tab:hover { color: #c0caf5; background: #1f2235; }
    .active-tab {
        background: #1a1b2e;
        color: #7aa2f7;
        border: solid #7aa2f7;
        text-style: bold;
    }

    /* Barra de descripción del modo */
    #mode-desc {
        background: #0d0f1a;
        color: #3b3f5a;
        padding: 0 2;
        height: auto;
        min-height: 2;
        border-bottom: solid #2a2d3e;
    }

    #main-panel { height: 1fr; }

    #left-panel {
        width: 3fr;
        border-right: solid #2a2d3e;
    }

    #right-panel {
        width: 1fr;
        background: #0d0f1a;
    }

    .panel-header {
        background: #1a1b2e;
        color: #565f89;
        text-style: bold;
        padding: 0 1;
        height: 2;
        border-bottom: solid #2a2d3e;
    }

    /* Chat scroll area */
    #chat-scroll {
        background: #0d0f1a;
        padding: 0 1;
        height: 1fr;
        scrollbar-color: #2a2d3e #0d0f1a;
    }

    /* Burbujas de mensajes */
    UserBubble {
        background: #1a1b2e;
        border-left: thick #7aa2f7;
        padding: 0 1;
        margin: 1 0 0 0;
        height: auto;
    }
    UserBubble .ub-label { color: #7aa2f7; text-style: bold; height: 1; }
    UserBubble .ub-text  { color: #c0caf5; }

    AIBubble {
        background: #13141f;
        border-left: thick #9ece6a;
        padding: 0 1;
        margin: 0 0 1 0;
        height: auto;
    }
    AIBubble .ab-label { color: #9ece6a; text-style: bold; height: 1; }
    AIBubble .ab-body  { color: #c0caf5; }

    StatusLine {
        color: #565f89;
        height: auto;
        padding: 0 2;
    }

    /* Fuentes */
    #sources-list  { height: 1fr; background: #0d0f1a; }
    #sources-empty { color: #3b3f5a; text-align: center; padding: 2; }
    .src-title  { color: #c0caf5; }
    .src-domain { color: #7aa2f7; }
    #sources-title {
        background: #1a1b2e;
        color: #565f89;
        text-style: bold;
        padding: 0 1;
        height: 2;
        border-bottom: solid #2a2d3e;
    }

    #input-area {
        height: auto;
        background: #13141f;
        border-top: solid #2a2d3e;
        padding: 1 2;
    }

    Input {
        background: #0d0f1a;
        border: solid #2a2d3e;
        color: #c0caf5;
        height: 3;
        margin-bottom: 1;
    }

    Input:focus {
        border: solid #7aa2f7;
    }

    #input-actions {
        height: 3;
        align: left middle;
    }

    #input-actions Button {
        margin-right: 1;
        height: 3;
    }

    #btn-stop {
        color: #f7768e;
        border: solid #f7768e;
    }

    #btn-stop:hover {
        background: #2d1a1e;
    }

    /* ─── Pantalla de Configuración ──────────────────────────────── */

    #settings-wrapper {
        padding: 1 3;
        height: 100%;
    }

    #settings-title {
        text-align: center;
        height: 2;
        padding: 0;
    }

    #settings-subtitle {
        color: #565f89;
        text-align: center;
        height: 2;
        margin-bottom: 1;
    }

    #settings-form {
        height: 1fr;
        overflow-y: auto;
    }

    .section-header {
        background: #1a1b2e;
        color: #7aa2f7;
        text-style: bold;
        padding: 0 1;
        height: 2;
        margin: 1 0 0 0;
        border: solid #2a2d3e;
    }

    .form-row {
        height: 4;
        align: left middle;
        margin: 1 0;
    }

    .form-label {
        width: 22;
        color: #c0caf5;
        padding: 1 1;
    }

    .form-row Input, .form-row Select {
        width: 1fr;
    }

    Select {
        background: #0d0f1a;
        border: solid #2a2d3e;
        color: #c0caf5;
    }

    Select:focus {
        border: solid #7aa2f7;
    }

    Switch {
        background: #2a2d3e;
        border: none;
    }

    Switch.-on {
        background: #283457;
    }

    #settings-status {
        height: 2;
        text-align: center;
        margin: 1 0;
    }

    #settings-tip {
        color: #3b3f5a;
        padding: 1;
        margin: 1 0;
    }

    #settings-buttons {
        height: 4;
        align: center middle;
        margin-top: 1;
    }

    #settings-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Salir"),
        Binding("ctrl+m", "change_model", "Modelo"),
        Binding("f1", "help", "Ayuda"),
    ]

    def __init__(self, initial_query: str = "", initial_model: str = "", initial_mode: str = ""):
        super().__init__()
        self.initial_query = initial_query
        self.initial_model = initial_model
        self.initial_mode = initial_mode or "research"

    def on_mount(self) -> None:
        cfg = get_config()
        self._client = OllamaClient(host=cfg.ollama_host)

        saved_model = self.initial_model or cfg.last_model
        saved_mode = self.initial_mode or cfg.last_mode or "research"

        from ollamaresearch.tui.screens.model_selector import ModelSelectorScreen

        self.push_screen(
            ModelSelectorScreen(
                client=self._client,
                current_model=saved_model,
                initial_mode=saved_mode,
            ),
            callback=self._on_model_selected,
        )

    def _on_model_selected(self, result) -> None:
        if result is None:
            self.exit()
            return

        model_name, mode = result
        cfg = get_config()
        cfg.last_model = model_name
        cfg.last_mode  = mode

        if mode == "code":
            from ollamaresearch.tui.screens.code_view import CodeView
            self.push_screen(CodeView(
                client=self._client,
                model=model_name,
                initial_query=self.initial_query,
            ))
        else:
            from ollamaresearch.tui.screens.research_view import ResearchView
            self.push_screen(
                ResearchView(
                    client=self._client,
                    model=model_name,
                    mode=mode,
                    initial_query=self.initial_query,
                )
            )

    def action_change_model(self) -> None:
        """Shortcut global para volver al selector de modelos."""
        # El ResearchView ya maneja esto internamente
        pass

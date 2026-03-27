"""Pantalla de historial de sesiones."""
from pathlib import Path
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from ollamaresearch.core.history import delete_session, list_sessions, load_session


class HistoryScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Cerrar"),
        Binding("enter", "open_selected", "Abrir"),
        Binding("d", "delete_selected", "Eliminar"),
    ]

    def __init__(self):
        super().__init__()
        self._sessions = list_sessions(100)
        self._selected_path: Path | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="history-wrapper"):
            yield Static("📚 [bold cyan]Historial de Investigaciones[/bold cyan]", id="hist-title")
            yield Static(
                f"[dim]{len(self._sessions)} sesiones guardadas • Enter=Abrir • D=Eliminar • Esc=Cerrar[/dim]",
                id="hist-sub",
            )
            yield DataTable(id="hist-table", zebra_stripes=True, cursor_type="row")
            with Horizontal(id="hist-buttons"):
                yield Button("📖 Abrir sesión", id="btn-open", variant="primary", disabled=True)
                yield Button("🗑  Eliminar",     id="btn-delete", disabled=True)
                yield Button("❌ Cerrar",        id="btn-close")
            yield Static("", id="hist-preview")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#hist-table", DataTable)
        table.add_columns("Fecha", "Modo", "Modelo", "Pregunta", "Vista previa")
        for s in self._sessions:
            ts = s["timestamp"][:16].replace("T", " ")
            icon = {"research": "🔬", "chat": "💬", "search": "🔍"}.get(s["mode"], "•")
            table.add_row(
                ts,
                f"{icon} {s['mode']}",
                s["model"][:20],
                s["query"][:40],
                s["preview"][:60],
                key=str(s["file"]),
            )

    @on(DataTable.RowSelected, "#hist-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            self._selected_path = Path(event.row_key.value)
            data = load_session(self._selected_path)
            if data:
                preview = data.get("result", "")[:300]
                self.query_one("#hist-preview", Static).update(
                    f"[bold]Pregunta:[/bold] {data.get('query', '')}\n\n"
                    f"[dim]{preview}...[/dim]"
                )
            self.query_one("#btn-open", Button).disabled = False
            self.query_one("#btn-delete", Button).disabled = False

    @on(Button.Pressed, "#btn-open")
    def action_open_selected(self) -> None:
        if self._selected_path:
            data = load_session(self._selected_path)
            if data:
                self.dismiss(data)

    @on(Button.Pressed, "#btn-delete")
    def action_delete_selected(self) -> None:
        if self._selected_path:
            delete_session(self._selected_path)
            self._sessions = list_sessions(100)
            self.app.pop_screen()
            self.app.push_screen(HistoryScreen())

    @on(Button.Pressed, "#btn-close")
    def on_close(self) -> None:
        self.dismiss(None)

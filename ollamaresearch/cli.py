"""
CLI principal de OllamaResearch
Punto de entrada del comando `ia`, `research` y `ollamaresearch`
"""
import sys
from pathlib import Path

import click


def _check_python_version():
    if sys.version_info < (3, 9):
        click.echo("❌ OllamaResearch requiere Python 3.9 o superior.", err=True)
        click.echo(f"   Versión actual: Python {sys.version}", err=True)
        sys.exit(1)


@click.command(
    name="ia",
    context_settings=dict(help_option_names=["-h", "--help"]),
)
@click.argument("query", nargs=-1)
@click.option(
    "--model", "-m",
    default="",
    help="Modelo de Ollama a usar (ej: llama3.2, gemma2:9b)",
    metavar="MODELO",
)
@click.option(
    "--mode",
    type=click.Choice(["research", "chat", "search"], case_sensitive=False),
    default=None,
    help="Modo: research (deep research), chat, search (búsqueda rápida)",
)
@click.option(
    "--host",
    default="",
    help="Host de Ollama (default: http://localhost:11434)",
    metavar="URL",
)
@click.option(
    "--version", "-v",
    is_flag=True,
    help="Mostrar versión",
)
@click.option(
    "--config",
    is_flag=True,
    help="Abrir configuración directamente",
)
@click.option(
    "--list-models",
    is_flag=True,
    help="Listar modelos instalados y salir",
)
@click.option(
    "--install-shortcuts",
    is_flag=True,
    help="Instalar shortcuts de terminal (ia, research)",
)
@click.option(
    "--share",
    is_flag=True,
    help="Compartir tu terminal en vivo (instala tmate si es necesario)",
)
@click.option(
    "--record",
    is_flag=True,
    help="Grabar la sesión de terminal con asciinema",
)
@click.option(
    "--history",
    is_flag=True,
    help="Ver historial de sesiones guardadas (sin TUI)",
)
def main(
    query,
    model,
    mode,
    host,
    version,
    config,
    list_models,
    install_shortcuts,
    share,
    record,
    history,
):
    """
    \b
    🔬 OllamaResearch — Framework de Deep Research con IA

    Herramienta de investigación profunda con modelos Ollama
    y búsqueda web en vivo. Compatible con Linux, macOS y Windows.

    \b
    EJEMPLOS:
      ia                          → Abre el TUI (interfaz completa)
      ia "¿qué es la IA?"        → Investiga directamente
      ia --model llama3.2        → Usa un modelo específico
      ia --mode chat             → Modo chat simple
      ia --list-models           → Ver modelos instalados
      ia --share                 → Compartir terminal en vivo (tmate)
      ia --record                → Grabar sesión (asciinema)
      ia --history               → Ver historial de sesiones
    """
    _check_python_version()

    if version:
        from ollamaresearch import __version__
        click.echo(f"OllamaResearch v{__version__}")
        return

    if install_shortcuts:
        _install_shortcuts()
        return

    if list_models:
        _list_models_cli(host)
        return

    if history:
        _show_history_cli()
        return

    if share:
        _share_terminal()
        return

    if record:
        _record_session()
        return

    # Actualizar host en config si se especificó
    if host:
        from ollamaresearch.utils.config import get_config
        get_config().set("ollama_host", host)

    # Abrir TUI
    query_str = " ".join(query) if query else ""

    if config:
        mode_override = "settings"
    else:
        mode_override = mode

    _launch_tui(query_str, model, mode_override)


def _launch_tui(query: str = "", model: str = "", mode: str = ""):
    """Lanza la interfaz TUI de Textual."""
    try:
        from ollamaresearch.tui.app import OllamaResearchApp
        app = OllamaResearchApp(
            initial_query=query,
            initial_model=model,
            initial_mode=mode,
        )
        app.run()
    except ImportError as e:
        click.echo(f"❌ Error al importar dependencias: {e}", err=True)
        click.echo("   Ejecuta: pip install ollamaresearch", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        pass


def _list_models_cli(host: str = ""):
    """Lista los modelos de Ollama en la terminal sin TUI."""
    import asyncio
    from ollamaresearch.core.ollama_client import OllamaClient
    from ollamaresearch.utils.config import get_config

    cfg = get_config()
    client = OllamaClient(host=host or cfg.ollama_host)

    async def _run():
        click.echo("\n🔬 OllamaResearch — Modelos disponibles\n")

        is_running = await client.check_running()
        if not is_running:
            click.echo("⟳ Intentando iniciar Ollama...")
            started = await client.start_server()
            if not started:
                click.echo("❌ Ollama no está disponible. Instálalo en ollama.com")
                return

        models = await client.list_local_models()

        if models:
            click.echo("🟢 MODELOS INSTALADOS LOCALMENTE:")
            click.echo(f"  {'Nombre':<35} {'Tamaño':<10} {'Familia'}")
            click.echo(f"  {'─'*35} {'─'*10} {'─'*20}")
            for m in models:
                click.echo(f"  {m.name:<35} {m.size:<10} {m.family}")
        else:
            click.echo("  (No hay modelos instalados)")
            click.echo(
                "\n  Descarga un modelo con:\n"
                "  ollama pull llama3.2\n"
                "  ollama pull gemma2\n"
            )

        click.echo(f"\n  Total: {len(models)} modelos locales")
        click.echo(f"\n  Host Ollama: {client.host}\n")

    asyncio.run(_run())


def _install_shortcuts():
    """Instala shortcuts de terminal en el sistema."""
    import platform
    system = platform.system().lower()

    click.echo("\n🔧 Instalando shortcuts de terminal...\n")

    if system in ("linux", "darwin"):
        _install_unix_shortcuts()
    elif system == "windows":
        _install_windows_shortcuts()
    else:
        click.echo(f"⚠️ Sistema operativo no reconocido: {system}")
        click.echo("   Agrega manualmente: alias ia='ollamaresearch'")


def _install_unix_shortcuts():
    """Instala aliases en shell de Unix/macOS."""
    home = Path.home()
    shells = []

    # Detectar shells disponibles
    for rc_file in [".bashrc", ".bash_profile", ".zshrc", ".profile", ".config/fish/config.fish"]:
        rc_path = home / rc_file
        if rc_path.exists():
            shells.append(rc_path)

    if not shells:
        rc_path = home / ".bashrc"
        shells = [rc_path]

    alias_line = "\n# OllamaResearch shortcuts\nalias ia='python -m ollamaresearch'\nalias research='python -m ollamaresearch'\n"
    fish_line = "\n# OllamaResearch shortcuts\nalias ia 'python -m ollamaresearch'\nalias research 'python -m ollamaresearch'\n"

    for shell_file in shells:
        try:
            content = shell_file.read_text(errors="ignore")
            if "OllamaResearch shortcuts" not in content:
                line = fish_line if "fish" in str(shell_file) else alias_line
                with open(shell_file, "a") as f:
                    f.write(line)
                click.echo(f"  ✅ Alias añadido a {shell_file}")
            else:
                click.echo(f"  ℹ️  Alias ya existe en {shell_file}")
        except Exception as e:
            click.echo(f"  ❌ Error en {shell_file}: {e}")

    click.echo("\n✅ Shortcuts instalados.")
    click.echo("   Reinicia tu terminal o ejecuta: source ~/.bashrc")
    click.echo("   Luego puedes usar: ia  ó  research\n")


def _install_windows_shortcuts():
    """Instala shortcuts en Windows PowerShell."""
    import subprocess
    ps_profile_cmd = "$PROFILE"

    click.echo("  Configurando PowerShell...")
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_profile_cmd],
            capture_output=True, text=True
        )
        profile_path = Path(result.stdout.strip())
        profile_path.parent.mkdir(parents=True, exist_ok=True)

        content = ""
        if profile_path.exists():
            content = profile_path.read_text(errors="ignore")

        if "OllamaResearch" not in content:
            alias_block = "\n# OllamaResearch shortcuts\nfunction ia { python -m ollamaresearch $args }\nfunction research { python -m ollamaresearch $args }\n"
            with open(profile_path, "a") as f:
                f.write(alias_block)
            click.echo(f"  ✅ Función 'ia' añadida al perfil de PowerShell")
        else:
            click.echo("  ℹ️  Shortcuts ya configurados en PowerShell")

        click.echo("\n✅ Shortcuts instalados.")
        click.echo("   Reinicia PowerShell y usa: ia")
    except Exception as e:
        click.echo(f"  ❌ Error: {e}")
        click.echo("  Añade manualmente a tu perfil de PowerShell:")
        click.echo("  function ia { python -m ollamaresearch $args }")




def _share_terminal():
    """Comparte la terminal en vivo usando tmate."""
    import platform
    import shutil
    import subprocess

    click.echo("\n🔗 OllamaResearch — Compartir Terminal en Vivo\n")
    click.echo("  tmate crea una sesión SSH que otra persona puede unirse")
    click.echo("  para ver (o controlar) tu terminal en tiempo real.\n")

    system = platform.system().lower()

    if not shutil.which("tmate"):
        click.echo("  ⟳ tmate no está instalado. Instalando...\n")
        if system == "darwin":
            subprocess.run(["brew", "install", "tmate"], check=False)
        elif system == "linux":
            # Intentar snap, apt, descarga directa
            if shutil.which("snap"):
                subprocess.run(["sudo", "snap", "install", "tmate"], check=False)
            elif shutil.which("apt"):
                subprocess.run(["sudo", "apt", "install", "-y", "tmate"], check=False)
            else:
                # Descarga binario directo
                arch = "amd64" if platform.machine() == "x86_64" else "arm64v8"
                url = f"https://github.com/tmate-io/tmate/releases/latest/download/tmate-linux-{arch}.tar.gz"
                click.echo(f"  Descargando desde: {url}")
                subprocess.run(f"curl -sL {url} | tar xz -C /usr/local/bin --strip-components=1 tmate*/tmate", shell=True)
        elif system == "windows":
            click.echo("  En Windows, instala WSL2 y ejecuta desde ahí, o usa SSH desde PowerShell.")
            click.echo("  Descarga tmate: https://tmate.io")
            return

    if not shutil.which("tmate"):
        click.echo("  ❌ No se pudo instalar tmate automáticamente.")
        click.echo("  Instala manualmente desde: https://tmate.io")
        return

    click.echo("  ✅ tmate disponible\n")
    click.echo("  Iniciando sesión compartida (Ctrl+C para terminar)...\n")
    click.echo("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    click.echo("  Las URLs de conexión aparecerán abajo:")
    click.echo("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    try:
        # -F: modo que muestra el output directamente (no abre nueva ventana)
        subprocess.run(["tmate", "-F"], check=False)
    except KeyboardInterrupt:
        pass
    click.echo("\n  Sesión compartida terminada.")


def _record_session():
    """Graba la sesión de terminal con asciinema."""
    import shutil
    import subprocess
    from datetime import datetime

    click.echo("\n🎬 OllamaResearch — Grabar Sesión de Terminal\n")

    if not shutil.which("asciinema"):
        click.echo("  ⟳ asciinema no está instalado. Instalando...\n")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "asciinema", "--quiet"])
        except Exception:
            pass

    if not shutil.which("asciinema") and not subprocess.run(
        [sys.executable, "-m", "asciinema", "--version"],
        capture_output=True
    ).returncode == 0:
        click.echo("  ❌ No se pudo instalar asciinema.")
        click.echo("  Instala con: pip install asciinema")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    from ollamaresearch.utils.config import get_data_dir
    out_dir = get_data_dir() / "recordings"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"session_{ts}.cast"

    click.echo(f"  📹 Grabando en: {out_file}")
    click.echo("  Escribe 'exit' o Ctrl+D para terminar la grabación.\n")
    click.echo("  Iniciando OllamaResearch grabado...\n")

    asciinema_cmd = shutil.which("asciinema") or f"{sys.executable} -m asciinema"
    cmd = f'{asciinema_cmd} rec --command "ia" --title "OllamaResearch {ts}" "{out_file}"'

    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        pass

    if out_file.exists():
        click.echo(f"\n  ✅ Grabación guardada: {out_file}")
        click.echo(f"  Reproducir con: asciinema play \"{out_file}\"")
        click.echo(f"  Subir y compartir: asciinema upload \"{out_file}\"")
    else:
        click.echo("\n  ⚠️ No se guardó la grabación.")


def _show_history_cli():
    """Muestra el historial de sesiones en la terminal (sin TUI)."""
    from ollamaresearch.core.history import list_sessions

    sessions = list_sessions(20)
    click.echo("\n📚 OllamaResearch — Historial de Sesiones\n")

    if not sessions:
        click.echo("  (No hay sesiones guardadas todavía)")
        click.echo("  Las sesiones se guardan automáticamente al usar Deep Research.\n")
        return

    for i, s in enumerate(sessions, 1):
        ts = s["timestamp"][:16].replace("T", " ")
        icon = {"research": "🔬", "chat": "💬", "search": "🔍"}.get(s["mode"], "•")
        click.echo(f"  [{i:02d}] {ts}  {icon} {s['mode']:<10}  {s['query'][:50]}")

    click.echo(f"\n  Total: {len(sessions)} sesiones")
    click.echo(f"  Guardadas en: {sessions[0]['file'].parent}\n")
    click.echo("  Usa 'ia --history' para ver el historial.")
    click.echo("  Usa 'ia' → botón 📚 Historial para abrirlas en la interfaz.\n")


if __name__ == "__main__":
    main()


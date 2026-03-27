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
def main(
    query,
    model,
    mode,
    host,
    version,
    config,
    list_models,
    install_shortcuts,
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


if __name__ == "__main__":
    main()

"""
CodeAgent — Agente primitivo de terminal para OllamaResearch
Genera, escribe y ejecuta código en un workspace sandbox seguro.

Modos:
  semi   → ejecuta create_dir/write_file directo, pausa antes de install/run
  auto   → ejecuta todo dentro del workspace (nunca toca rutas externas)
"""
import asyncio
import json
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from ollamaresearch.core.ollama_client import OllamaClient

# ─── Workspace por defecto ────────────────────────────────────────────────────
WORKSPACE_ROOT = Path.home() / "ollamaresearch-projects"

# ─── Lenguajes soportados → extensión ────────────────────────────────────────
LANG_EXTENSIONS = {
    "python": ".py", "javascript": ".js", "typescript": ".ts",
    "c": ".c", "cpp": ".cpp", "c++": ".cpp", "go": ".go",
    "rust": ".rs", "bash": ".sh", "powershell": ".ps1",
    "html": ".html", "css": ".css", "json": ".json",
    "yaml": ".yaml", "yml": ".yaml", "markdown": ".md", "toml": ".toml",
}


class ActionType(str, Enum):
    CREATE_DIR      = "create_dir"
    CREATE_VENV     = "create_venv"
    WRITE_FILE      = "write_file"
    RUN_COMMAND     = "run_command"
    INSTALL_PACKAGE = "install_package"
    READ_FILE       = "read_file"
    DONE            = "done"


class CodeEventType(str, Enum):
    STATUS         = "status"
    PLAN           = "plan"
    ACTION         = "action"
    ACTION_OUTPUT  = "action_output"
    ACTION_SUCCESS = "action_success"
    ACTION_ERROR   = "action_error"
    FILE_CREATED   = "file_created"
    DIR_CREATED    = "dir_created"
    ASK_USER       = "ask_user"
    CHUNK          = "chunk"
    DONE           = "done"
    ERROR          = "error"
    WARNING        = "warning"


@dataclass
class CodeEvent:
    type: CodeEventType
    text: str = ""
    data: Dict = field(default_factory=dict)


@dataclass
class CodeAction:
    action: ActionType
    path: str = ""
    content: str = ""
    cmd: str = ""
    cwd: str = ""
    packages: List[str] = field(default_factory=list)
    description: str = ""


# ─── RISKY_ACTIONS: acciones que pausan en modo semi ────────────────────────
RISKY_ACTIONS = {ActionType.RUN_COMMAND, ActionType.INSTALL_PACKAGE}


class CodeAgent:
    """
    Agente de terminal primitivo.
    - NUNCA opera fuera de WORKSPACE_ROOT (sandbox estricto)
    - Modo 'semi': pausa antes de install_package / run_command
    - Modo 'auto': ejecuta todo sin pausas dentro del sandbox
    - Puede editar proyectos existentes (lee estructura y archivos)
    """

    def __init__(
        self,
        ollama_client: OllamaClient,
        autonomy: str = "semi",
        workspace: Optional[Path] = None,
    ):
        self.ollama     = ollama_client
        self.autonomy   = autonomy  # "semi" | "auto"
        self.workspace  = workspace or WORKSPACE_ROOT
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Detección de OS y comandos adaptados
        self._os         = platform.system()          # "Windows" | "Darwin" | "Linux"
        self._python_cmd = "python" if self._os == "Windows" else "python3"
        self._venv_bin   = "Scripts" if self._os == "Windows" else "bin"

        # Estado de la sesión actual
        self._project_path: Optional[Path] = None
        self._venv_path:    Optional[Path] = None
        self._files_created: List[str] = []
        self._dirs_created:  List[str] = []

    # ─── Seguridad ────────────────────────────────────────────────────────────

    def _is_safe_path(self, path) -> bool:
        """Verifica que la ruta esté dentro del workspace (sandbox)."""
        try:
            target    = Path(path).resolve()
            workspace = self.workspace.resolve()
            return str(target).startswith(str(workspace))
        except Exception:
            return False

    def _resolve_path(self, relative: str) -> Path:
        """Resuelve una ruta relativa al proyecto actual o al workspace."""
        p = Path(relative)
        if p.is_absolute():
            return p
        if self._project_path:
            return (self._project_path / relative).resolve()
        return (self.workspace / relative).resolve()

    # ─── Helpers venv ─────────────────────────────────────────────────────────

    def _venv_python(self, venv: Path) -> str:
        if self._os == "Windows":
            return str(venv / "Scripts" / "python.exe")
        return str(venv / "bin" / "python3")

    def _venv_pip(self, venv: Path) -> str:
        if self._os == "Windows":
            return str(venv / "Scripts" / "pip.exe")
        return str(venv / "bin" / "pip")

    # ─── Subprocess async ─────────────────────────────────────────────────────

    async def _run(self, cmd: List[str], cwd: Optional[Path] = None, timeout: int = 180) -> Tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return (
                    proc.returncode or 0,
                    stdout.decode("utf-8", errors="replace"),
                    stderr.decode("utf-8", errors="replace"),
                )
            except asyncio.TimeoutError:
                proc.kill()
                return -1, "", f"Timeout después de {timeout}s"
        except Exception as exc:
            return -1, "", str(exc)

    # ─── Ejecutor de acciones ─────────────────────────────────────────────────

    async def execute_action(
        self,
        action: CodeAction,
        event_cb: Callable[[CodeEvent], None],
    ) -> bool:
        """Ejecuta una acción individual. Retorna True si tuvo éxito."""

        at = action.action

        # ── create_dir ────────────────────────────────────────────────────────
        if at == ActionType.CREATE_DIR:
            path = self._resolve_path(action.path)
            if not self._is_safe_path(path):
                await event_cb(CodeEvent(CodeEventType.ACTION_ERROR, f"⛔ Ruta fuera del sandbox: {path}"))
                return False
            path.mkdir(parents=True, exist_ok=True)
            self._dirs_created.append(str(path))
            if self._project_path is None:
                self._project_path = path
            await event_cb(CodeEvent(CodeEventType.DIR_CREATED, f"📁 {action.path}", {"path": str(path)}))
            return True

        # ── create_venv ───────────────────────────────────────────────────────
        elif at == ActionType.CREATE_VENV:
            path = self._resolve_path(action.path)
            if not self._is_safe_path(path):
                await event_cb(CodeEvent(CodeEventType.ACTION_ERROR, f"⛔ Ruta fuera del sandbox"))
                return False
            venv_path = path / ".venv"
            await event_cb(CodeEvent(CodeEventType.ACTION, f"🐍 Creando entorno virtual (.venv)..."))
            rc, out, err = await self._run([self._python_cmd, "-m", "venv", str(venv_path)], cwd=path)
            if rc == 0:
                self._venv_path = venv_path
                await event_cb(CodeEvent(CodeEventType.ACTION_SUCCESS, "✅ Entorno virtual listo"))
                return True
            else:
                await event_cb(CodeEvent(CodeEventType.ACTION_ERROR, f"❌ venv falló: {err[:300]}"))
                return False

        # ── write_file ────────────────────────────────────────────────────────
        elif at == ActionType.WRITE_FILE:
            path = self._resolve_path(action.path)
            if not self._is_safe_path(path):
                await event_cb(CodeEvent(CodeEventType.ACTION_ERROR, f"⛔ Ruta fuera del sandbox: {path}"))
                return False
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(action.content, encoding="utf-8")
            self._files_created.append(str(path))
            lines = len(action.content.splitlines())
            await event_cb(CodeEvent(CodeEventType.FILE_CREATED, f"📄 {action.path} ({lines} líneas)", {"path": str(path)}))
            return True

        # ── install_package ───────────────────────────────────────────────────
        elif at == ActionType.INSTALL_PACKAGE:
            if not action.packages:
                return True
            pip = self._venv_pip(self._venv_path) if self._venv_path else "pip"
            await event_cb(CodeEvent(CodeEventType.ACTION, f"📦 Instalando: {', '.join(action.packages)}..."))
            rc, out, err = await self._run([pip, "install"] + action.packages, cwd=self._project_path, timeout=240)
            combined = (out + err).strip()
            if combined:
                await event_cb(CodeEvent(CodeEventType.ACTION_OUTPUT, combined[-600:]))
            if rc == 0:
                await event_cb(CodeEvent(CodeEventType.ACTION_SUCCESS, f"✅ Paquetes instalados"))
                return True
            else:
                await event_cb(CodeEvent(CodeEventType.ACTION_ERROR, f"❌ Error al instalar paquetes"))
                return False

        # ── run_command ───────────────────────────────────────────────────────
        elif at == ActionType.RUN_COMMAND:
            cwd = self._resolve_path(action.cwd) if action.cwd else self._project_path or self.workspace
            if not self._is_safe_path(cwd):
                await event_cb(CodeEvent(CodeEventType.ACTION_ERROR, "⛔ Directorio fuera del sandbox"))
                return False

            # Sustituir python/pip por los del venv si existe
            cmd_str = action.cmd
            if self._venv_path:
                cmd_str = cmd_str.replace("python3 ", self._venv_python(self._venv_path) + " ")
                cmd_str = cmd_str.replace("python ",  self._venv_python(self._venv_path) + " ")
                cmd_str = cmd_str.replace("pip3 ",    self._venv_pip(self._venv_path) + " ")
                cmd_str = cmd_str.replace("pip ",     self._venv_pip(self._venv_path) + " ")

            if self._os == "Windows":
                cmd = ["powershell", "-Command", cmd_str]
            else:
                cmd = ["bash", "-c", cmd_str]

            await event_cb(CodeEvent(CodeEventType.ACTION, f"⚡ {action.cmd}"))
            rc, out, err = await self._run(cmd, cwd=cwd, timeout=60)
            combined = (out + err).strip()
            if combined:
                await event_cb(CodeEvent(CodeEventType.ACTION_OUTPUT, combined[:1200]))
            if rc == 0:
                await event_cb(CodeEvent(CodeEventType.ACTION_SUCCESS, "✅ Comando completado"))
                return True
            else:
                await event_cb(CodeEvent(CodeEventType.ACTION_ERROR, f"❌ Falló (código {rc})"))
                return False

        # ── read_file ─────────────────────────────────────────────────────────
        elif at == ActionType.READ_FILE:
            path = self._resolve_path(action.path)
            if not self._is_safe_path(path):
                await event_cb(CodeEvent(CodeEventType.ACTION_ERROR, f"⛔ Ruta fuera del sandbox"))
                return False
            if not path.exists():
                await event_cb(CodeEvent(CodeEventType.ACTION_ERROR, f"❌ No existe: {path.name}"))
                return False
            content = path.read_text(encoding="utf-8", errors="replace")
            await event_cb(CodeEvent(CodeEventType.ACTION_OUTPUT, f"📖 {path.name}:\n{content[:2000]}"))
            return True

        return True

    # ─── Flujo principal ──────────────────────────────────────────────────────

    async def generate_project(
        self,
        objective: str,
        model: str,
        event_cb: Callable[[CodeEvent], None],
        confirm_cb: Optional[Callable] = None,
        existing_project: Optional[Path] = None,
    ) -> None:
        """
        Flujo completo: planifica → genera código → ejecuta acciones.
        Si existing_project viene dado, carga ese proyecto y lo mejora.
        confirm_cb(step_dict) -> bool: llamado en modo semi para pasos de riesgo.
        """
        self._files_created = []
        self._dirs_created  = []

        # Cargar proyecto existente
        existing_files_ctx = ""
        if existing_project:
            self._project_path = existing_project
            venv = existing_project / ".venv"
            if venv.exists():
                self._venv_path = venv
            file_list = [
                str(f.relative_to(existing_project))
                for f in existing_project.rglob("*")
                if f.is_file() and ".venv" not in f.parts and "__pycache__" not in f.parts
            ]
            existing_files_ctx = "\nArchivos existentes:\n" + "\n".join(f"  - {f}" for f in file_list[:40])
            await event_cb(CodeEvent(CodeEventType.STATUS, f"📂 Proyecto cargado: {existing_project.name}"))

        await event_cb(CodeEvent(CodeEventType.STATUS,
            f"🖥️  OS: {self._os}  |  Python: {self._python_cmd}  |  Modo: {'Semi-autónomo' if self.autonomy == 'semi' else 'Autónomo'}"))
        await event_cb(CodeEvent(CodeEventType.STATUS, "🧠 Generando plan..."))

        # ── Paso 1: planificación ─────────────────────────────────────────────
        plan_raw = await self.ollama.generate_simple(
            model,
            PLANNING_PROMPT.format(
                objective=objective,
                os=self._os,
                python_cmd=self._python_cmd,
                workspace=str(self.workspace),
                existing_files=existing_files_ctx,
                edit_note="MEJORANDO proyecto existente. NO crear_dir ni create_venv si ya existen."
                          if existing_project else "CREANDO proyecto nuevo.",
            ),
        )

        plan_json = self._extract_json(plan_raw)
        if not plan_json:
            await event_cb(CodeEvent(CodeEventType.ERROR,
                f"❌ El modelo no devolvió JSON válido.\nRespuesta:\n{plan_raw[:600]}"))
            return

        try:
            plan = json.loads(plan_json)
        except json.JSONDecodeError as exc:
            await event_cb(CodeEvent(CodeEventType.ERROR, f"❌ JSON inválido: {exc}"))
            return

        project_name = plan.get("project_name", "proyecto_nuevo")
        description  = plan.get("description", "")
        steps        = plan.get("steps", [])

        await event_cb(CodeEvent(
            CodeEventType.PLAN,
            f"📋 {project_name}\n{description}\n🔢 {len(steps)} pasos",
            {"project_name": project_name, "steps_count": len(steps)},
        ))

        if not existing_project:
            self._project_path = self.workspace / project_name

        # ── Paso 2: ejecutar cada acción ──────────────────────────────────────
        for i, step in enumerate(steps):
            raw_action = step.get("action", "")
            desc       = step.get("description", raw_action)

            await event_cb(CodeEvent(CodeEventType.STATUS, f"[{i+1}/{len(steps)}] {desc}"))

            # Pausa en modo semi para acciones de riesgo
            try:
                action_type = ActionType(raw_action)
            except ValueError:
                await event_cb(CodeEvent(CodeEventType.WARNING, f"⚠️ Acción desconocida: {raw_action} — omitiendo"))
                continue

            if self.autonomy == "semi" and action_type in RISKY_ACTIONS and confirm_cb:
                approved = await confirm_cb(step)
                if not approved:
                    await event_cb(CodeEvent(CodeEventType.STATUS, f"⏭️  Paso {i+1} omitido"))
                    continue

            action = CodeAction(
                action=action_type,
                path=step.get("path", ""),
                content=step.get("content", ""),
                cmd=step.get("cmd", ""),
                cwd=step.get("cwd", ""),
                packages=step.get("packages", []),
                description=desc,
            )

            # Si write_file no tiene contenido → generarlo con el LLM
            if action_type == ActionType.WRITE_FILE and not action.content:
                await event_cb(CodeEvent(CodeEventType.STATUS, f"✍️  Generando código: {action.path}..."))
                code_chunks: List[str] = []
                async for chunk in self.ollama.chat_stream(
                    model,
                    [{"role": "user", "content": CODE_GENERATION_PROMPT.format(
                        objective=objective,
                        file_path=action.path,
                        description=desc,
                        os=self._os,
                        project_name=project_name,
                    )}],
                ):
                    code_chunks.append(chunk)
                    await event_cb(CodeEvent(CodeEventType.CHUNK, chunk))

                action.content = self._clean_code("".join(code_chunks), action.path)

            await self.execute_action(action, event_cb)

        # ── Resumen final ─────────────────────────────────────────────────────
        await event_cb(CodeEvent(
            CodeEventType.DONE,
            f"✅ {len(self._files_created)} archivo(s) • {len(self._dirs_created)} carpeta(s)\n"
            f"📁 Workspace: {self._project_path}",
            {
                "files":        self._files_created,
                "dirs":         self._dirs_created,
                "project_path": str(self._project_path) if self._project_path else "",
            },
        ))

    # ─── Utilities ────────────────────────────────────────────────────────────

    def _extract_json(self, text: str) -> Optional[str]:
        """Extrae el primer bloque JSON válido de la respuesta del LLM."""
        for pattern in [
            r"```json\s*([\s\S]+?)\s*```",
            r"```\s*(\{[\s\S]+?\})\s*```",
            r"(\{[\s\S]+\})",
        ]:
            m = re.search(pattern, text)
            if m:
                candidate = m.group(1).strip()
                try:
                    json.loads(candidate)
                    return candidate
                except Exception:
                    continue
        return None

    def _clean_code(self, content: str, file_path: str) -> str:
        """Elimina markdown fences del código generado."""
        content = re.sub(r"^```[\w]*\s*\n?", "", content.strip())
        content = re.sub(r"\n?```\s*$",       "", content.strip())
        return content.strip()

    def list_projects(self) -> List[Path]:
        """Lista todos los proyectos en el workspace."""
        if not self.workspace.exists():
            return []
        return sorted(
            [d for d in self.workspace.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )

    def get_project_tree(self, project_path: Path, max_depth: int = 4) -> List[str]:
        """Genera árbol visual del proyecto (estilo `tree`)."""
        SKIP = {".venv", "__pycache__", ".git", "node_modules", "dist", "build"}
        lines: List[str] = [f"📁 {project_path.name}/"]

        def _walk(path: Path, prefix: str, depth: int) -> None:
            if depth > max_depth:
                return
            try:
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return
            items = [i for i in items if i.name not in SKIP]
            for idx, item in enumerate(items):
                is_last   = idx == len(items) - 1
                connector = "└── " if is_last else "├── "
                icon      = "📄" if item.is_file() else "📁"
                lines.append(f"{prefix}{connector}{icon} {item.name}")
                if item.is_dir():
                    ext = "    " if is_last else "│   "
                    _walk(item, prefix + ext, depth + 1)

        _walk(project_path, "", 0)
        return lines

    def read_project_context(self, project_path: Path, max_chars: int = 8000) -> str:
        """Lee los archivos principales del proyecto para contexto del LLM."""
        SKIP = {".venv", "__pycache__", ".git", "node_modules"}
        IMPORTANT_EXTS = {".py", ".js", ".ts", ".go", ".rs", ".c", ".cpp", ".md", ".toml", ".json", ".yaml"}
        context_parts = []
        total = 0

        for f in sorted(project_path.rglob("*")):
            if any(s in f.parts for s in SKIP):
                continue
            if f.is_file() and f.suffix in IMPORTANT_EXTS:
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    snippet = content[:2000]
                    entry   = f"\n--- {f.relative_to(project_path)} ---\n{snippet}"
                    if total + len(entry) > max_chars:
                        break
                    context_parts.append(entry)
                    total += len(entry)
                except Exception:
                    pass

        return "\n".join(context_parts) if context_parts else "(proyecto vacío)"


# ─── Prompts del CodeAgent ────────────────────────────────────────────────────

PLANNING_PROMPT = """\
ROL: Arquitecto de software. Tu ÚNICA tarea es generar un plan de proyecto en JSON.

OBJETIVO: {objective}
OS: {os} | PYTHON: {python_cmd} | WORKSPACE: {workspace}
NOTA: {edit_note}
{existing_files}

DEVUELVE EXACTAMENTE este JSON (sin texto extra, sin markdown):
{{
  "project_name": "nombre_en_snake_case",
  "description": "Una línea: qué hace este proyecto",
  "steps": [
    {{"action": "create_dir",      "path": "nombre_proyecto",            "description": "Crear carpeta raíz"}},
    {{"action": "create_venv",     "path": "nombre_proyecto",            "description": "Entorno virtual Python"}},
    {{"action": "write_file",      "path": "nombre_proyecto/main.py",    "description": "Script principal — [rol exacto del archivo]",    "content": ""}},
    {{"action": "write_file",      "path": "nombre_proyecto/README.md",  "description": "Documentación",                                  "content": ""}},
    {{"action": "install_package", "packages": ["requests","scapy"],     "description": "Instalar dependencias"}},
    {{"action": "write_file",      "path": "nombre_proyecto/requirements.txt", "description": "Lista de dependencias",                    "content": ""}}
  ]
}}

REGLAS:
- Usa SOLO acciones: create_dir, create_venv, write_file, install_package, run_command, read_file
- Para proyectos Python: SIEMPRE include create_venv como segundo paso
- Para archivos de código: "content" SIEMPRE vacío "" — se genera por separado
- Incluye SIEMPRE README.md al final
- Para pentesting/hacking ético: incluye scapy, paramiko, impacket o las libs apropiadas
- NO incluir create_dir ni create_venv si ya existen (modo edición)
- RESPONDE SOLO el JSON"""

CODE_GENERATION_PROMPT = """\
ROL: Desarrollador experto. Escribe el código completo para este archivo.

PROYECTO: {project_name}
OBJETIVO: {objective}
ARCHIVO: {file_path}
ROL DEL ARCHIVO: {description}
OS: {os}

REGLAS ABSOLUTAS:
- Escribe SOLO el código. Sin explicaciones. Sin markdown fences (``` ```)
- Comenta el código en español
- Código completo y funcional (no esqueletos)
- Para pentesting ético: código profesional con disclaimer y manejo de errores robusto
- Para README.md: markdown bien estructurado con instalación, uso y ejemplos
- Para requirements.txt: solo nombres de paquetes, uno por línea, sin versiones fijas
- Include if __name__ == '__main__' en scripts Python principales

CÓDIGO:"""

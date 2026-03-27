"""
Cliente Ollama unificado — soporta modelos locales y remotos
Maneja automáticamente el servidor Ollama si no está corriendo
"""
import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import AsyncGenerator, Callable, Dict, List, Optional

import httpx

# Catálogo de modelos populares disponibles en ollama.com/library
# Estos pueden descargarse bajo demanda
CATALOG_MODELS = [
    # Llama Family
    {"name": "llama3.2:latest", "size": "3B", "family": "Llama 3.2", "tags": ["fast", "local"]},
    {"name": "llama3.2:3b", "size": "3B", "family": "Llama 3.2", "tags": ["fast", "local"]},
    {"name": "llama3.2:1b", "size": "1B", "family": "Llama 3.2", "tags": ["ultrafast", "local"]},
    {"name": "llama3.1:8b", "size": "8B", "family": "Llama 3.1", "tags": ["balanced"]},
    {"name": "llama3.1:70b", "size": "70B", "family": "Llama 3.1", "tags": ["powerful", "large"]},
    {"name": "llama3.3:70b", "size": "70B", "family": "Llama 3.3", "tags": ["latest", "powerful"]},
    # DeepSeek
    {"name": "deepseek-r1:7b", "size": "7B", "family": "DeepSeek R1", "tags": ["reasoning"]},
    {"name": "deepseek-r1:14b", "size": "14B", "family": "DeepSeek R1", "tags": ["reasoning"]},
    {"name": "deepseek-r1:32b", "size": "32B", "family": "DeepSeek R1", "tags": ["reasoning", "large"]},
    {"name": "deepseek-r1:70b", "size": "70B", "family": "DeepSeek R1", "tags": ["reasoning", "large"]},
    # Gemma
    {"name": "gemma2:2b", "size": "2B", "family": "Gemma 2", "tags": ["fast", "google"]},
    {"name": "gemma2:9b", "size": "9B", "family": "Gemma 2", "tags": ["balanced", "google"]},
    {"name": "gemma2:27b", "size": "27B", "family": "Gemma 2", "tags": ["powerful", "google"]},
    # Mistral
    {"name": "mistral:latest", "size": "7B", "family": "Mistral", "tags": ["fast", "french"]},
    {"name": "mistral-nemo:latest", "size": "12B", "family": "Mistral", "tags": ["balanced"]},
    # Qwen
    {"name": "qwen2.5:7b", "size": "7B", "family": "Qwen 2.5", "tags": ["multilingual"]},
    {"name": "qwen2.5:14b", "size": "14B", "family": "Qwen 2.5", "tags": ["multilingual"]},
    {"name": "qwen2.5:32b", "size": "32B", "family": "Qwen 2.5", "tags": ["multilingual", "large"]},
    # Phi
    {"name": "phi4:latest", "size": "14B", "family": "Phi-4", "tags": ["microsoft", "efficient"]},
    {"name": "phi3.5:latest", "size": "4B", "family": "Phi-3.5", "tags": ["microsoft", "fast"]},
    # Otros populares
    {"name": "codellama:latest", "size": "7B", "family": "Code Llama", "tags": ["code"]},
    {"name": "nomic-embed-text:latest", "size": "137M", "family": "Nomic", "tags": ["embeddings"]},
    {"name": "command-r:latest", "size": "35B", "family": "Command R", "tags": ["rag", "cohere"]},
]


@dataclass
class ModelInfo:
    """Información de un modelo de Ollama."""
    name: str
    size: str = ""
    family: str = ""
    description: str = ""
    local: bool = True
    tags: List[str] = field(default_factory=list)
    modified: str = ""

    @property
    def display_name(self) -> str:
        """Nombre limpio para mostrar en UI."""
        return self.name.split(":")[0].replace("-", " ").title()

    @property
    def size_display(self) -> str:
        return self.size or "?"


class OllamaClient:
    """
    Cliente Ollama que gestiona modelos locales y del catálogo.
    Inicia el servidor automáticamente si no está corriendo.
    """

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip("/")
        self._is_running = False

    async def check_running(self) -> bool:
        """Verifica si el servidor Ollama está activo."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.host}/api/tags")
                self._is_running = resp.status_code == 200
                return self._is_running
        except Exception:
            self._is_running = False
            return False

    async def start_server(self) -> bool:
        """
        Intenta iniciar el servidor Ollama.
        Funciona en Linux, macOS y Windows.
        """
        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    ["ollama", "serve"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            # Esperar hasta 8 segundos a que inicie
            for _ in range(16):
                await asyncio.sleep(0.5)
                if await self.check_running():
                    return True
            return False

        except FileNotFoundError:
            # Ollama no está instalado
            return False
        except Exception:
            return False

    async def ensure_running(self) -> bool:
        """Garantiza que Ollama esté corriendo, iniciándolo si es necesario."""
        if await self.check_running():
            return True
        return await self.start_server()

    async def list_local_models(self) -> List[ModelInfo]:
        """Lista los modelos instalados localmente."""
        if not await self.ensure_running():
            return []

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{self.host}/api/tags")
                if resp.status_code != 200:
                    return []

                data = resp.json()
                models = []
                for m in data.get("models", []):
                    size_bytes = m.get("size", 0)
                    if size_bytes > 1_000_000_000:
                        size_str = f"{size_bytes / 1e9:.1f}GB"
                    elif size_bytes > 1_000_000:
                        size_str = f"{size_bytes / 1e6:.0f}MB"
                    else:
                        size_str = "?"

                    name = m.get("name", "")
                    family = m.get("details", {}).get("family", "")

                    models.append(ModelInfo(
                        name=name,
                        size=size_str,
                        family=family,
                        local=True,
                        modified=str(m.get("modified_at", ""))[:10],
                    ))
                return models

        except Exception:
            return []

    async def list_catalog_models(self) -> List[ModelInfo]:
        """
        Devuelve modelos del catálogo de Ollama (descargables bajo demanda).
        Excluye los que ya están instalados localmente.
        """
        local = await self.list_local_models()
        local_names = {m.name for m in local}

        catalog = []
        for m in CATALOG_MODELS:
            if m["name"] not in local_names:
                catalog.append(ModelInfo(
                    name=m["name"],
                    size=m["size"],
                    family=m["family"],
                    local=False,
                    tags=m.get("tags", []),
                ))
        return catalog

    async def pull_model(
        self,
        model_name: str,
        progress_cb: Optional[Callable] = None,
    ) -> bool:
        """
        Descarga un modelo del repositorio de Ollama.
        Llama a progress_cb(status: str, percent: int) durante la descarga.
        """
        if not await self.ensure_running():
            return False

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{self.host}/api/pull",
                    json={"name": model_name, "stream": True},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")
                            total = data.get("total", 0)
                            completed = data.get("completed", 0)
                            pct = int(completed / total * 100) if total > 0 else 0
                            if progress_cb:
                                await progress_cb(status, pct)
                        except Exception:
                            continue
            return True
        except Exception:
            return False

    async def delete_model(self, model_name: str) -> bool:
        """Elimina un modelo local."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(
                    f"{self.host}/api/delete",
                    json={"name": model_name},
                )
                return resp.status_code in (200, 204)
        except Exception:
            return False

    async def chat_stream(
        self,
        model: str,
        messages: List[Dict],
        options: Optional[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Genera una respuesta en streaming desde el modelo seleccionado.
        Yield de cada fragmento de texto a medida que llega.
        """
        if not await self.ensure_running():
            yield "❌ Error: No se pudo conectar con Ollama. Por favor inicia Ollama primero."
            return

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if options:
            payload["options"] = options

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{self.host}/api/chat",
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        yield f"❌ Error del servidor: {resp.status_code}"
                        return

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done", False):
                                break
                        except Exception:
                            continue

        except httpx.ConnectError:
            yield "\n❌ Error de conexión. Verifica que Ollama esté corriendo."
        except Exception as e:
            yield f"\n❌ Error: {str(e)}"

    async def generate_simple(self, model: str, prompt: str) -> str:
        """Genera una respuesta completa (sin streaming) para uso interno."""
        result = ""
        async for chunk in self.chat_stream(
            model, [{"role": "user", "content": prompt}]
        ):
            result += chunk
        return result

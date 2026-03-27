"""
Gestión de configuración para OllamaResearch
Almacena configuración en directorio específico de cada plataforma
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def get_config_dir() -> Path:
    """Obtiene el directorio de configuración específico de cada plataforma."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    config_dir = base / "ollamaresearch"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    """Directorio para guardar historial y resultados."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    data_dir = base / "ollamaresearch"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DEFAULT_CONFIG: Dict[str, Any] = {
    "ollama_host": "http://localhost:11434",
    "search_engine": "duckduckgo",  # duckduckgo, tavily, serper
    "tavily_api_key": "",
    "serper_api_key": "",
    "research": {
        "max_iterations": 3,
        "max_sources": 8,
        "max_tokens_per_source": 2000,
        "depth": "medium",  # light, medium, deep
        "language": "español",
    },
    "ui": {
        "theme": "dark",
        "show_sources": True,
        "auto_copy": False,
    },
    "last_model": "",
    "last_mode": "research",  # research, chat, search
    "shortcuts": {
        "linux": "ia",
        "darwin": "ia",
        "win32": "ia",
    },
}


class Config:
    """Gestión de configuración del framework."""

    def __init__(self):
        self._path = get_config_dir() / "config.json"
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    data = json.load(f)
                return self._deep_merge(DEFAULT_CONFIG, data)
            except Exception:
                pass
        return dict(DEFAULT_CONFIG)

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        keys = key.split(".")
        data = self._data
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k)
                if data is None:
                    return default
            else:
                return default
        return data

    def set(self, key: str, value):
        keys = key.split(".")
        data = self._data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value
        self.save()

    # Propiedades de acceso rápido
    @property
    def ollama_host(self) -> str:
        return self.get("ollama_host", "http://localhost:11434")

    @property
    def search_engine(self) -> str:
        return self.get("search_engine", "duckduckgo")

    @property
    def tavily_api_key(self) -> str:
        return self.get("tavily_api_key", "")

    @property
    def serper_api_key(self) -> str:
        return self.get("serper_api_key", "")

    @property
    def research_config(self) -> dict:
        return self.get("research", DEFAULT_CONFIG["research"])

    @property
    def last_model(self) -> str:
        return self.get("last_model", "")

    @last_model.setter
    def last_model(self, value: str):
        self.set("last_model", value)

    @property
    def last_mode(self) -> str:
        return self.get("last_mode", "research")

    @last_mode.setter
    def last_mode(self, value: str):
        self.set("last_mode", value)


# Instancia global
_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config

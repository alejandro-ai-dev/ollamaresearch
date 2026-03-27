"""
Historial persistente de sesiones.
Guarda/carga conversaciones en JSON bajo el directorio de datos del usuario.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _history_dir() -> Path:
    from ollamaresearch.utils.config import get_data_dir
    d = get_data_dir() / "history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_session(
    mode: str,
    model: str,
    query: str,
    messages: List[Dict],
    result: str,
    sources: Optional[List[Any]] = None,
) -> Path:
    """Guarda una sesión completa en JSON. Devuelve la ruta del archivo."""
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    slug = re.sub(r"[^\w\s-]", "", query[:40]).strip().replace(" ", "_")
    filename = f"{ts}_{mode}_{slug}.json"
    path = _history_dir() / filename

    data = {
        "version": 1,
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "model": model,
        "query": query,
        "result": result,
        "messages": messages,
        "sources": [
            {"title": s.title, "url": s.url, "snippet": s.snippet}
            for s in (sources or [])
            if hasattr(s, "url")
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_sessions(limit: int = 50) -> List[Dict]:
    """Lista las sesiones más recientes."""
    d = _history_dir()
    files = sorted(d.glob("*.json"), reverse=True)[:limit]
    sessions = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions.append(
                {
                    "file": f,
                    "timestamp": data.get("timestamp", ""),
                    "mode": data.get("mode", ""),
                    "model": data.get("model", ""),
                    "query": data.get("query", ""),
                    "preview": data.get("result", "")[:120],
                }
            )
        except Exception:
            pass
    return sessions


def load_session(path: Path) -> Optional[Dict]:
    """Carga una sesión desde archivo."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def delete_session(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except Exception:
        return False

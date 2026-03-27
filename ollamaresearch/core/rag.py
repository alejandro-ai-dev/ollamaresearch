"""
RAG básico — Lector de archivos locales para contexto adicional.
Soporta: .txt, .md, .csv, .pdf, .py, .js, .json (y más código)
"""
import re
from pathlib import Path
from typing import Optional, Tuple


MAX_CHARS = 12_000  # Máximo caracteres a enviar al modelo


def is_file_ref(text: str) -> Optional[Path]:
    """Detecta si el texto/query es una ruta a un archivo existente."""
    # Soporta rutas entre comillas o sin ellas
    stripped = text.strip().strip('"').strip("'")
    p = Path(stripped)
    if p.exists() and p.is_file():
        return p
    # Detectar si empieza con / ~ o letra:\ (Windows)
    if re.match(r'^[/~]|^[A-Za-z]:\\', stripped):
        p2 = Path(stripped).expanduser()
        if p2.exists() and p2.is_file():
            return p2
    return None


def extract_file_and_query(text: str) -> Tuple[Optional[Path], str]:
    """
    Extrae una ruta de archivo al inicio del texto y el resto como query.
    Ejemplos:
      '/home/user/doc.pdf resume esto' → (Path, 'resume esto')
      'archivo.txt qué dice?' → (Path, 'qué dice?')
      'sin archivo' → (None, 'sin archivo')
    """
    parts = text.strip().split(None, 1)
    if not parts:
        return None, text

    candidate = parts[0].strip('"').strip("'")
    p = Path(candidate).expanduser()
    if p.exists() and p.is_file():
        query = parts[1].strip() if len(parts) > 1 else "Resume el contenido de este archivo"
        return p, query

    return None, text


def read_file(path: Path) -> Tuple[str, str]:
    """
    Lee un archivo y devuelve (content, format_hint).
    Lanza ValueError si el tipo no está soportado.
    """
    suffix = path.suffix.lower()

    # PDF
    if suffix == ".pdf":
        return _read_pdf(path), "PDF"

    # Texto plano / código / config
    text_types = {
        ".txt": "texto",
        ".md": "Markdown",
        ".csv": "CSV",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".sh": "Shell",
        ".bat": "Batch",
        ".ps1": "PowerShell",
        ".html": "HTML",
        ".xml": "XML",
        ".toml": "TOML",
        ".ini": "INI",
        ".env": "ENV",
        ".rs": "Rust",
        ".go": "Go",
        ".java": "Java",
        ".cpp": "C++",
        ".c": "C",
        ".cs": "C#",
        ".r": "R",
        ".sql": "SQL",
    }

    if suffix in text_types:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise ValueError(f"No se pudo leer {path.name}: {e}")
        return content, text_types[suffix]

    raise ValueError(
        f"Tipo de archivo '{suffix}' no soportado.\n"
        "Soportados: .txt .md .pdf .csv .json .yaml .py .js .ts .sh y más código."
    )


def _read_pdf(path: Path) -> str:
    """Extrae texto de un PDF usando pdfplumber (si está instalado)."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages.append(f"[Página {i+1}]\n{text}")
        return "\n\n".join(pages)
    except ImportError:
        raise ValueError(
            "Para leer PDFs instala pdfplumber:\n"
            "  pip install pdfplumber\n"
            "o en el venv del proyecto:\n"
            "  .venv/bin/pip install pdfplumber"
        )
    except Exception as e:
        raise ValueError(f"Error al leer PDF: {e}")


def prepare_context(path: Path, query: str) -> str:
    """
    Genera el prompt completo con el contenido del archivo como contexto.
    Trunca si es muy largo para no superar el límite del modelo.
    """
    try:
        content, fmt = read_file(path)
    except ValueError as e:
        return f"❌ {e}"

    if len(content) > MAX_CHARS:
        content = content[:MAX_CHARS] + f"\n\n... [contenido truncado a {MAX_CHARS} caracteres]"

    size_kb = path.stat().st_size / 1024
    return (
        f"El usuario ha adjuntado el archivo '{path.name}' "
        f"({fmt}, {size_kb:.1f} KB).\n\n"
        f"--- CONTENIDO DEL ARCHIVO ---\n\n"
        f"{content}\n\n"
        f"--- FIN DEL ARCHIVO ---\n\n"
        f"Instrucción del usuario: {query}"
    )

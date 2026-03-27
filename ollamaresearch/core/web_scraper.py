"""
Extractor de contenido web para OllamaResearch
Extrae texto limpio de URLs para el agente de investigación
"""
import asyncio
import re
from typing import Optional
from urllib.parse import urlparse

import httpx


# Headers para simular navegador y evitar bloqueos
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
}

# Dominios que generalmente bloquean scraping
BLOCKED_DOMAINS = {
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "linkedin.com", "reddit.com", "tiktok.com",
}

# Dominios de PDFs y archivos binarios a omitir
SKIP_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                   ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mp3", ".zip"}


def should_skip_url(url: str) -> bool:
    """Verifica si la URL debe omitirse."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        if domain in BLOCKED_DOMAINS:
            return True
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
            return True
    except Exception:
        pass
    return False


def clean_text(text: str, max_chars: int = 6000) -> str:
    """Limpia y trunca el texto extraído."""
    # Eliminar múltiples espacios y líneas en blanco
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Eliminar caracteres de control
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.strip()
    # Truncar al máximo de caracteres
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text


def extract_with_bs4(html: str, url: str) -> str:
    """Extrae texto limpio de HTML usando BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # Eliminar elementos no relevantes
        for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                                   "iframe", "noscript", "aside", "advertisement",
                                   ".ads", ".sidebar", ".menu", ".cookie"]):
            tag.decompose()

        # Intentar extraer el contenido principal
        main_content = (
            soup.find("main") or
            soup.find("article") or
            soup.find(id=re.compile(r"content|main|article|post", re.I)) or
            soup.find(class_=re.compile(r"content|main|article|post|body", re.I)) or
            soup.find("body")
        )

        if main_content:
            # Extraer texto con separadores de párrafo
            texts = []
            for element in main_content.find_all(["p", "h1", "h2", "h3", "h4", "li", "td"]):
                text = element.get_text(strip=True)
                if len(text) > 30:  # Solo fragmentos con contenido real
                    texts.append(text)
            return "\n\n".join(texts)
        else:
            return soup.get_text(separator="\n", strip=True)

    except Exception:
        # Fallback: regex básico
        clean = re.sub(r"<[^>]+>", " ", html)
        return clean_text(clean, 3000)


class WebScraper:
    """Extractor de contenido web asíncrono."""

    def __init__(self, timeout: float = 10.0, max_chars: int = 6000):
        self.timeout = timeout
        self.max_chars = max_chars

    async def fetch(self, url: str) -> Optional[str]:
        """
        Descarga y extrae el texto de una URL.
        Devuelve None si no se puede acceder.
        """
        if should_skip_url(url):
            return None

        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
                verify=False,  # Algunos sitios tienen certificados problemáticos
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None

                content_type = resp.headers.get("content-type", "")
                if "html" not in content_type and "text" not in content_type:
                    return None

                html = resp.text
                text = extract_with_bs4(html, url)
                return clean_text(text, self.max_chars) if text else None

        except Exception:
            return None

    async def fetch_many(
        self, urls: list, max_concurrent: int = 5
    ) -> list:
        """
        Descarga múltiples URLs en paralelo con límite de concurrencia.
        Devuelve lista de (url, content) donde content puede ser None.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(url: str):
            async with semaphore:
                content = await self.fetch(url)
                return url, content

        tasks = [fetch_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = []
        for r in results:
            if isinstance(r, Exception):
                continue
            output.append(r)

        return output

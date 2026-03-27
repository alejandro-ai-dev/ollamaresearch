"""
Motor de búsqueda web para OllamaResearch
Soporta DuckDuckGo (gratis), Tavily y Serper
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional
import httpx


@dataclass
class SearchResult:
    """Un resultado de búsqueda web."""
    title: str
    url: str
    snippet: str
    source: str = ""
    relevance: float = 0.0


class DuckDuckGoSearch:
    """
    Búsqueda usando DuckDuckGo - sin API key, gratuito.
    Usa la librería duckduckgo-search para resultados confiables.
    """

    def __init__(self, max_results: int = 8):
        self.max_results = max_results

    async def search(self, query: str) -> List[SearchResult]:
        """Realiza búsqueda en DuckDuckGo de forma asíncrona."""
        try:
            from duckduckgo_search import DDGS

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self._sync_search, query
            )
            return results
        except Exception as e:
            return []

    def _sync_search(self, query: str) -> List[SearchResult]:
        from duckduckgo_search import DDGS
        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(
                    query,
                    max_results=self.max_results,
                    region="es-es",
                    safesearch="moderate",
                ):
                    results.append(SearchResult(
                        title=r.get("title", "Sin título"),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                        source="duckduckgo",
                    ))
        except Exception:
            # Fallback sin región
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=self.max_results):
                        results.append(SearchResult(
                            title=r.get("title", "Sin título"),
                            url=r.get("href", ""),
                            snippet=r.get("body", ""),
                            source="duckduckgo",
                        ))
            except Exception:
                pass
        return results


class TavilySearch:
    """
    Búsqueda usando Tavily - optimizado para AI, requiere API key.
    Tier gratuito: 1000 búsquedas/mes.
    """

    def __init__(self, api_key: str, max_results: int = 8):
        self.api_key = api_key
        self.max_results = max_results
        self.base_url = "https://api.tavily.com"

    async def search(self, query: str) -> List[SearchResult]:
        if not self.api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": self.max_results,
                        "include_answer": False,
                        "include_raw_content": False,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [
                        SearchResult(
                            title=r.get("title", ""),
                            url=r.get("url", ""),
                            snippet=r.get("content", ""),
                            source="tavily",
                            relevance=r.get("score", 0.0),
                        )
                        for r in data.get("results", [])
                    ]
        except Exception:
            pass
        return []


class SerperSearch:
    """
    Búsqueda usando Serper.dev API (resultados de Google).
    Requiere API key de serper.dev.
    """

    def __init__(self, api_key: str, max_results: int = 8):
        self.api_key = api_key
        self.max_results = max_results
        self.base_url = "https://google.serper.dev/search"

    async def search(self, query: str) -> List[SearchResult]:
        if not self.api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    self.base_url,
                    headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                    json={"q": query, "num": self.max_results, "hl": "es"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for r in data.get("organic", []):
                        results.append(SearchResult(
                            title=r.get("title", ""),
                            url=r.get("link", ""),
                            snippet=r.get("snippet", ""),
                            source="serper",
                        ))
                    return results
        except Exception:
            pass
        return []


class SearchEngine:
    """
    Motor de búsqueda unificado que selecciona el proveedor según configuración.
    DuckDuckGo como fallback garantizado (sin API key).
    """

    def __init__(
        self,
        engine: str = "duckduckgo",
        tavily_key: str = "",
        serper_key: str = "",
        max_results: int = 8,
    ):
        self.engine = engine
        self.max_results = max_results
        self._ddg = DuckDuckGoSearch(max_results)
        self._tavily = TavilySearch(tavily_key, max_results) if tavily_key else None
        self._serper = SerperSearch(serper_key, max_results) if serper_key else None

    async def search(self, query: str) -> List[SearchResult]:
        """Busca usando el motor configurado, con fallback a DuckDuckGo."""
        results = []

        if self.engine == "tavily" and self._tavily:
            results = await self._tavily.search(query)
        elif self.engine == "serper" and self._serper:
            results = await self._serper.search(query)

        # Fallback a DuckDuckGo si el motor principal falla
        if not results:
            results = await self._ddg.search(query)

        return results

    async def multi_search(self, queries: List[str]) -> List[SearchResult]:
        """Realiza múltiples búsquedas en paralelo, deduplicando resultados."""
        tasks = [self.search(q) for q in queries]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        seen_urls = set()
        all_results = []
        for results in results_lists:
            if isinstance(results, Exception):
                continue
            for r in results:
                if r.url and r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

        return all_results

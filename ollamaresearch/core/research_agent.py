"""
Agente de Deep Research — Motor central de investigación iterativa
Combina búsqueda web, extracción de contenido y síntesis con LLM
"""
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Callable, Dict, List, Optional

from ollamaresearch.core.ollama_client import OllamaClient
from ollamaresearch.core.search_engine import SearchEngine, SearchResult
from ollamaresearch.core.web_scraper import WebScraper


class EventType(str, Enum):
    STATUS = "status"
    SEARCH_START = "search_start"
    SOURCE_FOUND = "source_found"
    SCRAPING = "scraping"
    SYNTHESIZING = "synthesizing"
    CHUNK = "chunk"
    ITERATION = "iteration"
    DONE = "done"
    ERROR = "error"


@dataclass
class ResearchEvent:
    """Evento emitido por el agente durante la investigación."""
    type: EventType
    text: str = ""
    sources: List[SearchResult] = field(default_factory=list)
    iteration: int = 0
    total_iterations: int = 0


@dataclass
class ResearchResult:
    """Resultado final de una investigación."""
    query: str
    report: str
    sources: List[SearchResult]
    iterations: int
    model: str


# ─── Prompts del sistema ──────────────────────────────────────────────────────

QUERY_GENERATION_PROMPT = """Eres un experto en investigación. El usuario quiere investigar:

"{query}"

{context}

Genera exactamente {num_queries} consultas de búsqueda específicas y complementarias para encontrar información exhaustiva sobre este tema. Las consultas deben ser en español e inglés alternativamente para maximizar resultados.

RESPONDE SOLO con las consultas, una por línea, sin numeración ni explicaciones."""

GAP_ANALYSIS_PROMPT = """Estás analizando si la investigación sobre "{query}" está completa.

Información recopilada hasta ahora:
{knowledge}

¿La información anterior responde completamente a la pregunta original? 
Si NO está completa, lista en máximo 3 bullets los aspectos que faltan.
Si SÍ está completa, responde exactamente: COMPLETO

Sé muy conciso."""

SYNTHESIS_PROMPT = """Eres un investigador experto. Tu tarea es sintetizar la siguiente información recopilada de múltiples fuentes web sobre:

**Pregunta:** {query}

**Fuentes y contenido:**
{sources_content}

{previous_knowledge}

Sintetiza la información en un análisis coherente. Sé preciso, cita hechos concretos cuando estén disponibles. No inventes información. Si hay contradicciones entre fuentes, menciónalo."""

FINAL_REPORT_PROMPT = """Eres un investigador experto. Basándote en toda la investigación realizada, escribe un informe completo y bien estructurado sobre:

**Pregunta original:** {query}

**Conocimiento acumulado:**
{knowledge}

**Fuentes consultadas ({num_sources}):**
{source_list}

Escribe el informe EN MARKDOWN con:
1. Un resumen ejecutivo
2. Análisis detallado con subsecciones
3. Hallazgos clave
4. Conclusiones
5. Referencias (lista las URLs más relevantes)

Sé exhaustivo pero claro. Usa emojis ocasionalmente para mejor legibilidad."""

CHAT_SYSTEM_PROMPT = """Eres un asistente inteligente y útil. Responde de manera clara, precisa y en el idioma del usuario. Cuando no sepas algo, dilo con honestidad."""

SEARCH_SUMMARY_PROMPT = """Resume los siguientes resultados de búsqueda web sobre "{query}" de manera concisa y útil:

{content}

Incluye los hallazgos más importantes y las URLs relevantes."""


class ResearchAgent:
    """
    Agente de investigación profunda que combina:
    - Búsqueda iterativa en web
    - Extracción de contenido
    - Síntesis con LLM
    - Análisis de gaps para más iteraciones
    """

    def __init__(
        self,
        ollama_client: OllamaClient,
        search_engine: SearchEngine,
        scraper: WebScraper,
        config: Optional[Dict] = None,
    ):
        self.ollama = ollama_client
        self.search = search_engine
        self.scraper = scraper
        self.config = config or {}
        self.max_iterations = self.config.get("max_iterations", 3)
        self.max_sources = self.config.get("max_sources", 8)
        self.max_chars = self.config.get("max_tokens_per_source", 2000)
        self.depth = self.config.get("depth", "medium")

    def _num_queries(self) -> int:
        """Número de sub-queries según la profundidad configurada."""
        return {"light": 2, "medium": 3, "deep": 5}.get(self.depth, 3)

    async def research(
        self,
        query: str,
        model: str,
        event_cb: Callable[[ResearchEvent], None],
    ) -> ResearchResult:
        """
        Ejecuta una investigación profunda iterativa.
        Emite eventos en tiempo real via event_cb.
        """
        all_sources: List[SearchResult] = []
        knowledge = ""
        iterations_done = 0
        max_iter = self.max_iterations

        await event_cb(ResearchEvent(
            type=EventType.STATUS,
            text=f"🔬 Iniciando investigación profunda...",
        ))

        for iteration in range(max_iter):
            iterations_done = iteration + 1
            await event_cb(ResearchEvent(
                type=EventType.ITERATION,
                text=f"📋 Iteración {iteration + 1} de {max_iter}",
                iteration=iteration + 1,
                total_iterations=max_iter,
            ))

            # Paso 1: Generar consultas de búsqueda
            context = f"\nConocimiento previo:\n{knowledge[:1000]}" if knowledge else ""
            gen_prompt = QUERY_GENERATION_PROMPT.format(
                query=query,
                context=context,
                num_queries=self._num_queries(),
            )

            await event_cb(ResearchEvent(
                type=EventType.STATUS,
                text="🧠 Generando consultas de búsqueda...",
            ))

            queries_text = await self.ollama.generate_simple(model, gen_prompt)
            queries = [
                q.strip("- •*").strip()
                for q in queries_text.strip().split("\n")
                if q.strip() and len(q.strip()) > 5
            ][: self._num_queries()]

            if not queries:
                queries = [query]

            # Paso 2: Buscar en web
            await event_cb(ResearchEvent(
                type=EventType.SEARCH_START,
                text=f"🔍 Buscando: {len(queries)} consultas...",
            ))

            new_results = await self.search.multi_search(queries)

            # Añadir fuentes nuevas
            existing_urls = {s.url for s in all_sources}
            for r in new_results:
                if r.url and r.url not in existing_urls:
                    all_sources.append(r)
                    existing_urls.add(r.url)

            await event_cb(ResearchEvent(
                type=EventType.SOURCE_FOUND,
                text=f"📄 {len(all_sources)} fuentes encontradas",
                sources=all_sources,
            ))

            # Paso 3: Extraer contenido de URLs
            urls_to_scrape = [
                s.url for s in all_sources[: self.max_sources]
                if s.url
            ]

            await event_cb(ResearchEvent(
                type=EventType.SCRAPING,
                text=f"📑 Extrayendo contenido de {len(urls_to_scrape)} fuentes...",
            ))

            scraped = await self.scraper.fetch_many(urls_to_scrape, max_concurrent=4)
            scraped_dict = {url: content for url, content in scraped if content}

            # Preparar contenido para síntesis
            sources_content = []
            for source in all_sources[: self.max_sources]:
                content = scraped_dict.get(source.url, "")
                if content:
                    sources_content.append(
                        f"**Fuente:** {source.title}\n**URL:** {source.url}\n\n{content[:self.max_chars]}"
                    )
                elif source.snippet:
                    sources_content.append(
                        f"**Fuente:** {source.title}\n**URL:** {source.url}\n\n{source.snippet}"
                    )

            if not sources_content:
                await event_cb(ResearchEvent(
                    type=EventType.STATUS,
                    text="⚠️ No se pudo extraer contenido. Usando fragmentos...",
                ))
                sources_content = [
                    f"**{s.title}** ({s.url})\n{s.snippet}"
                    for s in all_sources[:5]
                ]

            # Paso 4: Síntesis con LLM
            await event_cb(ResearchEvent(
                type=EventType.SYNTHESIZING,
                text="🤖 Sintetizando información...",
            ))

            prev_knowledge = (
                f"\nInformación de iteración anterior:\n{knowledge[:2000]}"
                if knowledge else ""
            )
            synthesis_prompt = SYNTHESIS_PROMPT.format(
                query=query,
                sources_content="\n\n---\n\n".join(sources_content[:6]),
                previous_knowledge=prev_knowledge,
            )

            knowledge = await self.ollama.generate_simple(model, synthesis_prompt)

            # Paso 5: ¿Necesitamos más iteraciones?
            if iteration < max_iter - 1:
                gap_prompt = GAP_ANALYSIS_PROMPT.format(
                    query=query,
                    knowledge=knowledge[:3000],
                )
                gap_response = await self.ollama.generate_simple(model, gap_prompt)

                if "COMPLETO" in gap_response.upper():
                    await event_cb(ResearchEvent(
                        type=EventType.STATUS,
                        text="✅ Investigación completa. Generando informe final...",
                    ))
                    break
                else:
                    await event_cb(ResearchEvent(
                        type=EventType.STATUS,
                        text=f"🔄 Profundizando en gaps detectados...",
                    ))

        # Paso 6: Informe final
        await event_cb(ResearchEvent(
            type=EventType.STATUS,
            text="📝 Generando informe final...",
        ))

        source_list = "\n".join([
            f"- [{s.title}]({s.url})"
            for s in all_sources[:15]
            if s.url
        ])

        report_prompt = FINAL_REPORT_PROMPT.format(
            query=query,
            knowledge=knowledge,
            num_sources=len(all_sources),
            source_list=source_list,
        )

        # Stream del informe final
        report_chunks = []
        messages = [{"role": "user", "content": report_prompt}]
        async for chunk in self.ollama.chat_stream(model, messages):
            report_chunks.append(chunk)
            await event_cb(ResearchEvent(type=EventType.CHUNK, text=chunk))

        report = "".join(report_chunks)

        result = ResearchResult(
            query=query,
            report=report,
            sources=all_sources,
            iterations=iterations_done,
            model=model,
        )

        await event_cb(ResearchEvent(
            type=EventType.DONE,
            text=f"✅ Investigación completada — {len(all_sources)} fuentes, {iterations_done} iteraciones",
            sources=all_sources,
        ))

        return result

    async def chat(
        self,
        messages: List[Dict],
        model: str,
        event_cb: Callable[[ResearchEvent], None],
    ) -> str:
        """Modo chat simple con streaming."""
        full_messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT}
        ] + messages

        result_chunks = []
        async for chunk in self.ollama.chat_stream(model, full_messages):
            result_chunks.append(chunk)
            await event_cb(ResearchEvent(type=EventType.CHUNK, text=chunk))

        await event_cb(ResearchEvent(type=EventType.DONE, text=""))
        return "".join(result_chunks)

    async def web_search_summary(
        self,
        query: str,
        model: str,
        event_cb: Callable[[ResearchEvent], None],
    ) -> str:
        """Búsqueda web rápida con resumen del LLM (sin deep research)."""
        await event_cb(ResearchEvent(
            type=EventType.STATUS,
            text=f"🔍 Buscando: {query}",
        ))

        results = await self.search.search(query)

        await event_cb(ResearchEvent(
            type=EventType.SOURCE_FOUND,
            text=f"📄 {len(results)} resultados encontrados",
            sources=results,
        ))

        if not results:
            await event_cb(ResearchEvent(
                type=EventType.DONE,
                text="No se encontraron resultados",
            ))
            return "No se encontraron resultados para esa búsqueda."

        content = "\n\n".join([
            f"**{r.title}**\n{r.snippet}\n{r.url}"
            for r in results[:8]
        ])

        summary_prompt = SEARCH_SUMMARY_PROMPT.format(query=query, content=content)

        await event_cb(ResearchEvent(
            type=EventType.SYNTHESIZING,
            text="🤖 Resumiendo resultados...",
        ))

        chunks = []
        async for chunk in self.ollama.chat_stream(
            model,
            [{"role": "user", "content": summary_prompt}]
        ):
            chunks.append(chunk)
            await event_cb(ResearchEvent(type=EventType.CHUNK, text=chunk))

        await event_cb(ResearchEvent(
            type=EventType.DONE,
            text=f"✅ Búsqueda completada — {len(results)} fuentes",
            sources=results,
        ))

        return "".join(chunks)

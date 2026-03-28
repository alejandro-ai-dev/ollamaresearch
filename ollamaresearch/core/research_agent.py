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

QUERY_GENERATION_PROMPT = """\
ROL: Especialista en búsqueda de información. Tu ÚNICA tarea es generar consultas de búsqueda web.

OBJETIVO DE INVESTIGACIÓN: {query}

{context}

REGLAS ESTRICTAS:
- Genera EXACTAMENTE {num_queries} consultas de búsqueda
- Cada consulta debe atacar un ángulo DIFERENTE del tema (definición, aplicaciones, comparativas, últimos avances, casos reales)
- Alterna entre español e inglés para maximizar cobertura de fuentes
- Las consultas deben ser directas, como si las escribieras en un buscador (sin signos de pregunta, sin verbos como "investigar" o "buscar")
- NO corrijas ni interpretes errores en el objetivo — úsalo tal como está
- NO expliques nada, NO numeres, NO pongas viñetas

FORMATO DE SALIDA — solo las consultas, una por línea:"""

GAP_ANALYSIS_PROMPT = """\
ROL: Evaluador de completitud en investigación.

OBJETIVO ORIGINAL: {query}

INFORMACIÓN RECOPILADA:
{knowledge}

EVALÚA si la información recopilada responde de forma SUFICIENTE el objetivo original.

CRITERIOS para considerar COMPLETO:
- Se responde la pregunta central con datos concretos
- Hay al menos un ejemplo, caso o evidencia
- Hay una conclusión o síntesis aplicable

Si está COMPLETO → responde únicamente la palabra: COMPLETO
Si NO está completo → lista máximo 3 aspectos clave que faltan, en formato bullet, sin explicaciones adicionales.
NO hagas preguntas. NO corrijas el objetivo. Sé brutalmente conciso."""

SYNTHESIS_PROMPT = """\
ROL: Analista de información. Tu tarea es construir conocimiento útil a partir de fuentes web.

OBJETIVO DE INVESTIGACIÓN: {query}

FUENTES RECOPILADAS:
{sources_content}

{previous_knowledge}

INSTRUCCIONES:
1. Extrae los hechos, datos y conclusiones MÁS RELEVANTES para el objetivo
2. Descarta información que no aporte al objetivo (publicidad, navegación del sitio, contenido genérico)
3. Si dos fuentes se contradicen, menciona ambas perspectivas brevemente
4. NO inventes datos. Si la información es insuficiente, dilo en una línea
5. NO corrijas el objetivo original. Trabaja con él tal como fue dado
6. Mantén el foco: cada párrafo debe relacionarse directamente con el objetivo

SINTESIS (clara, estructurada, orientada al objetivo):"""

FINAL_REPORT_PROMPT = """\
ROL: Redactor de informes de investigación. Crea el informe definitivo basado en la investigación realizada.

OBJETIVO ORIGINAL: {query}

CONOCIMIENTO ACUMULADO:
{knowledge}

FUENTES CONSULTADAS ({num_sources}):
{source_list}

ESTRUCTURA OBLIGATORIA DEL INFORME EN MARKDOWN:

## Resumen Ejecutivo
(2-3 párrafos: de qué trata, qué se encontró, conclusión principal)

## Análisis Detallado
(subsecciones temáticas con los hallazgos más importantes, datos concretos, ejemplos)

## Hallazgos Clave
(lista de 4-7 bullets con los puntos más importantes y accionables)

## Conclusiones
(qué significa todo esto en el contexto del objetivo original. Sin divagar)

## Fuentes
(lista de URLs relevantes en formato markdown)

NORMAS DE REDACCIÓN:
- Usa el idioma del objetivo original
- Sé directo y específico. Evita frases de relleno
- No repitas información entre secciones
- No corrijas ni reinterpretes el objetivo original
- Usa negritas para destacar datos importantes"""

CHAT_SYSTEM_PROMPT = """\
Eres un asistente directo, claro y preciso. Responde siempre en el idioma del usuario.
Si no sabes algo, dilo sin rodeos. No rellenes con frases vacías.
Mantén las respuestas enfocadas en lo que el usuario preguntó."""

SEARCH_SUMMARY_PROMPT = """\
ROL: Extractor de información relevante.

CONSULTA: {query}

RESULTADOS DE BÚSQUEDA:
{content}

INSTRUCCIONES:
- Extrae únicamente la información que responde directamente a la consulta
- Presenta los hallazgos en orden de relevancia
- Incluye las URLs de las fuentes más útiles
- Si los resultados no responden la consulta, dilo en una línea y sugiere cómo reformularla
- Sé conciso: máximo 300 palabras"""


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

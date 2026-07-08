"""
search_orchestrator.py — Componente cognitivo centralizado de recuperación y unificación de conocimiento.

Coordina la ejecución de la estrategia planificada por KnowledgePlanner a través de
múltiples KnowledgeSource, consolidando recuerdos locales de SQLite y contenido
de Internet (Browserless) en un único RAG context estructurado con citas bibliográficas.
"""

from __future__ import annotations

import base64
import logging
import re
import urllib.parse
import json
import os
import asyncio
import unicodedata
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional

import httpx
from bs4 import BeautifulSoup
from knowledge_planner import KnowledgePlanner, KnowledgePlan

logger = logging.getLogger("cerebro.search_orchestrator")

# ─── Modelado de Items de Conocimiento ───

class KnowledgeItem:
    """Representa una unidad de conocimiento recuperada de cualquier fuente."""
    
    def __init__(
        self,
        title: str,
        url: str,
        content: str,
        score: float,
        source_type: str,
        created_at: int = 0
    ):
        self.title = title
        self.url = url
        self.content = content
        self.score = score
        self.source_type = source_type
        self.created_at = created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "score": self.score,
            "source_type": self.source_type,
            "created_at": self.created_at
        }


# ─── Abstracción de Fuentes de Conocimiento (Knowledge Sources) ───

class KnowledgeSource(ABC):
    """Interfaz abstracta para los proveedores de fuentes de conocimiento."""
    
    @abstractmethod
    async def retrieve(
        self,
        queries: List[str],
        plan: KnowledgePlan,
        orchestrator: KnowledgeOrchestrator
    ) -> List[KnowledgeItem]:
        """Recupera items de conocimiento basados en las consultas planificadas."""
        pass


class MemorySource(KnowledgeSource):
    """Fuente de conocimiento que consulta la memoria semántica local (SQLite)."""
    
    async def retrieve(
        self,
        queries: List[str],
        plan: KnowledgePlan,
        orchestrator: KnowledgeOrchestrator
    ) -> List[KnowledgeItem]:
        if not orchestrator.db:
            return []
            
        results = []
        for q in queries:
            try:
                # Obtener embedding para la consulta
                embedding = None
                if orchestrator.embeddings_client:
                    embedding = await orchestrator.embeddings_client.get_embedding(q)
                
                threshold = orchestrator.config.get("database", {}).get("similarity_threshold", 0.40)
                nodes = await orchestrator.db.search_semantic(
                    query_text=q,
                    query_embedding=embedding,
                    similarity_threshold=threshold,
                    limit=5
                )
                
                for node in nodes:
                    # Convertir distancia de sqlite-vec a un score de similitud
                    distance = node.get("distance", 1.0)
                    similarity = 1.0 - (distance / 2.0)
                    
                    results.append(KnowledgeItem(
                        title="Memoria Semántica Local",
                        url=f"local://node/{node.get('id')}",
                        content=node.get("content", ""),
                        score=similarity,
                        source_type="memoria",
                        created_at=node.get("created_at", 0)
                    ))
            except Exception as e:
                logger.error("[MemorySource] Error recuperando recuerdos: %s", e)
        return results


class WebSearchSource(KnowledgeSource):
    """Fuente de conocimiento general basada en motores de búsqueda de Internet."""
    
    async def retrieve(
        self,
        queries: List[str],
        plan: KnowledgePlan,
        orchestrator: KnowledgeOrchestrator
    ) -> List[KnowledgeItem]:
        provider = orchestrator.providers.get(plan.provider.lower(), orchestrator.providers["bing"])
        
        results = []
        for q in queries:
            try:
                raw_items = await provider.search(q, orchestrator.browserless_url)
                for item in raw_items:
                    url = item.get("url", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    score = item.get("score", 0.5)
                    stype = orchestrator._classify_source(url, title)
                    
                    results.append(KnowledgeItem(
                        title=title,
                        url=url,
                        content=snippet,
                        score=score,
                        source_type=stype
                    ))
            except Exception as e:
                logger.error("[WebSearchSource] Error en consulta web: %s", e)
        return results


class GitHubSource(KnowledgeSource):
    """Fuente especializada en el rastreo de repositorios de GitHub."""
    
    async def retrieve(
        self,
        queries: List[str],
        plan: KnowledgePlan,
        orchestrator: KnowledgeOrchestrator
    ) -> List[KnowledgeItem]:
        # Para GitHub, reescribimos las consultas para apuntar a github.com
        github_queries = [f"site:github.com {q}" if "github.com" not in q.lower() else q for q in queries]
        provider = orchestrator.providers.get(plan.provider.lower(), orchestrator.providers["bing"])
        
        results = []
        for q in github_queries:
            try:
                raw_items = await provider.search(q, orchestrator.browserless_url)
                for item in raw_items:
                    url = item.get("url", "")
                    # Forzar a que sea GitHub
                    if "github.com" in url.lower():
                        title = item.get("title", "")
                        snippet = item.get("snippet", "")
                        score = item.get("score", 0.5)
                        results.append(KnowledgeItem(
                            title=title,
                            url=url,
                            content=snippet,
                            score=score + 0.5,  # Boost inicial por coincidir con la fuente especializada
                            source_type="repositorio github"
                        ))
            except Exception as e:
                logger.error("[GitHubSource] Error rastreando GitHub: %s", e)
        return results


class OfficialDocsSource(KnowledgeSource):
    """Fuente especializada en guías y documentación oficial de desarrollo."""
    
    async def retrieve(
        self,
        queries: List[str],
        plan: KnowledgePlan,
        orchestrator: KnowledgeOrchestrator
    ) -> List[KnowledgeItem]:
        # Boost de términos de documentación
        docs_queries = [f"docs OR documentation {q}" for q in queries]
        provider = orchestrator.providers.get(plan.provider.lower(), orchestrator.providers["bing"])
        
        results = []
        for q in docs_queries:
            try:
                raw_items = await provider.search(q, orchestrator.browserless_url)
                for item in raw_items:
                    url = item.get("url", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    score = item.get("score", 0.5)
                    stype = orchestrator._classify_source(url, title)
                    
                    if stype == "documentación":
                        score += 0.5
                        
                    results.append(KnowledgeItem(
                        title=title,
                        url=url,
                        content=snippet,
                        score=score,
                        source_type=stype
                    ))
            except Exception as e:
                logger.error("[OfficialDocsSource] Error buscando documentación: %s", e)
        return results


# ─── Proveedores de Búsqueda a Bajo Nivel (Motores) ───

class SearchEngineProvider(ABC):
    """Interfaz abstracta para los proveedores de motores de búsqueda."""
    
    @abstractmethod
    async def search(self, query: str, browserless_url: str) -> List[Dict[str, Any]]:
        pass


class BingSearchProvider(SearchEngineProvider):
    """Búsqueda en Bing usando Browserless Headless."""
    
    async def search(self, query: str, browserless_url: str) -> List[Dict[str, Any]]:
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        logger.info("[BingSearchProvider] Consultando Bing via Browserless para: '%s'", query)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{browserless_url}/content",
                    json={"url": url}
                )
                resp.raise_for_status()
                html = resp.text
                
            soup = BeautifulSoup(html, "html.parser")
            results = []
            
            for idx, item in enumerate(soup.find_all("li", class_="b_algo")):
                h2 = item.find("h2")
                a = h2.find("a") if h2 else None
                snippet_div = item.find("div", class_="b_caption") or item.find("p")
                
                if a and a.has_attr("href"):
                    raw_url = a["href"]
                    resolved_url = _decode_bing_url(raw_url)
                    title = a.get_text(strip=True)
                    snippet = snippet_div.get_text(strip=True) if snippet_div else ""
                    
                    if title and resolved_url:
                        score = 1.0 - (idx * 0.05)
                        results.append({
                            "title": title,
                            "url": resolved_url,
                            "snippet": snippet,
                            "score": max(score, 0.1)
                        })
            return results
        except Exception as e:
            logger.error("[BingSearchProvider] Error en búsqueda Bing: %s", e)
            return []


class SearXNGSearchProvider(SearchEngineProvider):
    """Búsqueda directa en SearXNG local (puerto 8888)."""
    
    async def search(self, query: str, browserless_url: str) -> List[Dict[str, Any]]:
        logger.info("[SearXNGSearchProvider] Consultando SearXNG para: '%s'", query)
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "http://127.0.0.1:8888/search",
                    params={"q": query, "format": "json"}
                )
                resp.raise_for_status()
                data = resp.json()
                
            raw_results = data.get("results", [])
            results = []
            for r in raw_results:
                title = r.get("title", "").strip()
                url = r.get("url", "").strip()
                snippet = r.get("content", "").strip()
                score = float(r.get("score", 0.5))
                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": re.sub(r'<[^>]+>', '', snippet).strip(),
                        "score": score
                    })
            return results
        except Exception as e:
            logger.error("[SearXNGSearchProvider] Error en SearXNG: %s", e)
            return []


class DuckDuckGoSearchProvider(SearchEngineProvider):
    """Búsqueda en DuckDuckGo con SDK pythonic."""
    
    async def search(self, query: str, browserless_url: str) -> List[Dict[str, Any]]:
        logger.info("[DDGSearchProvider] Consultando DuckDuckGo para: '%s'", query)
        try:
            from ddgs import DDGS
            from ddgs.exceptions import RatelimitException

            with DDGS() as ddgs:
                try:
                    raw_results = ddgs.text(query, safesearch="moderate", max_results=5)
                    raw_results = raw_results if raw_results is not None else []
                except RatelimitException as e:
                    logger.warning("[DDGSearchProvider] DuckDuckGo Rate limit: %s", e)
                    return []

            results = []
            for idx, r in enumerate(raw_results):
                title = (r.get("title") or "").strip()
                url = (r.get("href") or "").strip()
                snippet = (r.get("body") or "").strip()
                score = 1.0 - (idx * 0.08)
                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "score": max(score, 0.1)
                    })
            return results
        except Exception as exc:
            logger.error("[DDGSearchProvider] Fallo en DuckDuckGo: %s", exc)
            return []


# ─── Utilerías de Decodificación y Parseo HTML ───

def _decode_bing_url(url: str) -> str:
    """Decodifica URLs enmascaradas de Bing mediante base64 seguro."""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        if "bing.com/ck/a" in url or "bing.com/ck" in url:
            query_params = urllib.parse.parse_qs(parsed.query)
            u_param = query_params.get("u")
            if u_param:
                val = u_param[0]
                if len(val) > 2:
                    encoded = val[2:]
                    padding = len(encoded) % 4
                    if padding:
                        encoded += "=" * (4 - padding)
                    decoded = base64.urlsafe_b64decode(encoded).decode("utf-8", errors="ignore")
                    return decoded
    except Exception as e:
        logger.debug("Error decodificando URL de Bing: %s", e)
    return url


def _html_to_markdown(html_content: str, max_length: int = 2000) -> str:
    """Extrae y formatea HTML en un markdown limpio."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    
    noise_tags = [
        "nav", "header", "footer", "script", "style", "aside", 
        "iframe", "noscript", "svg", "form", "button", "head", "meta", "link"
    ]
    for tag in soup.find_all(noise_tags):
        tag.decompose()
        
    main_element = soup.find(["article", "main", "[role='main']", "#content", ".content", "#main-content"])
    if main_element:
        soup = main_element  # type: ignore[assignment]
        
    markdown_lines = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "pre", "code"]):
        if element.name in ["h1", "h2", "h3", "h4"]:
            level = int(element.name[1])
            text = element.get_text().strip()
            if text:
                markdown_lines.append(f"\n{'#' * level} {text}\n")
        elif element.name == "p":
            text = element.get_text().strip()
            if text:
                markdown_lines.append(f"\n{text}\n")
        elif element.name == "li":
            text = element.get_text().strip()
            if text:
                markdown_lines.append(f"- {text}")
        elif element.name in ["pre", "code"]:
            text = element.get_text().strip()
            if text:
                markdown_lines.append(f"\n```\n{text}\n```\n")
                
    clean_text = "\n".join(markdown_lines).strip()
    if not clean_text:
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)
        
    if len(clean_text) > max_length:
        clean_text = clean_text[:max_length] + "\n... [Contenido Web Truncado]"
        
    return clean_text


# ─── Citation Builder (Citas y Referencias) ───

class CitationBuilder:
    """Clase encargada de construir referencias y asignar marcadores [N] a fuentes."""

    def __init__(self) -> None:
        self.sources: List[Dict[str, Any]] = []
        self.url_to_citation: Dict[str, str] = {}

    def get_citation_marker(self, title: str, url: str, domain: str, source_type: str) -> str:
        if url in self.url_to_citation:
            return self.url_to_citation[url]
            
        citation_num = len(self.sources) + 1
        marker = f"[{citation_num}]"
        self.url_to_citation[url] = marker
        self.sources.append({
            "num": citation_num,
            "title": title,
            "url": url,
            "domain": domain,
            "type": source_type
        })
        return marker

    def build_bibliography(self) -> str:
        if not self.sources:
            return ""
        lines = ["\n--- REFERENCIAS Y FUENTES BIBLIOGRÁFICAS ---"]
        for src in self.sources:
            lines.append(f"[{src['num']}] '{src['title']}' - Dominio: {src['domain']} (URL: {src['url']}) | Tipo: {src['type']}")
        return "\n".join(lines)


# ─── Orquestador Cognitivo de Conocimiento ───

class KnowledgeOrchestrator:
    """Orquestador cognitivo centralizado de RAG y unificación de conocimiento."""
    
    def __init__(self, config: dict, embeddings_client: Any, db: Any) -> None:
        self.config = config
        self.embeddings_client = embeddings_client
        self.db = db
        
        # Instanciar el KnowledgePlanner
        self.planner = KnowledgePlanner(config)
        
        search_config = config.get("search", {})
        self.browserless_url = search_config.get("browserless_url", "http://127.0.0.1:3000")
        self.provider_name = search_config.get("provider", "bing").lower()
        
        # Mapeo de proveedores de búsqueda a bajo nivel
        self.providers: Dict[str, SearchEngineProvider] = {
            "bing": BingSearchProvider(),
            "searxng": SearXNGSearchProvider(),
            "duckduckgo": DuckDuckGoSearchProvider(),
            "google": BingSearchProvider(), # Bing como fallback estable para evadir CAPTCHAs
            "brave": BingSearchProvider()
        }

        # Fuentes de conocimiento disponibles
        self.knowledge_sources: Dict[str, KnowledgeSource] = {
            "memory": MemorySource(),
            "web_search": WebSearchSource(),
            "github": GitHubSource(),
            "official_docs": OfficialDocsSource(),
            "news": WebSearchSource()
        }

    def _classify_source(self, url: str, title: str) -> str:
        url_lower = url.lower()
        title_lower = title.lower()
        
        if url_lower.startswith("local://"):
            return "memoria"
            
        for doc_dom in [
            "docs.python.org", "developer.mozilla.org", "react.dev", "svelte.dev", "tailwindcss.com",
            "nextjs.org", "vite.dev", "fastapi.tiangolo.com", "pkg.go.dev", "rust-lang.org",
            "docs.microsoft.com", "support.google.com", "aws.amazon.com/docs", "kubernetes.io/docs"
        ]:
            if doc_dom in url_lower:
                return "documentación"
                
        if "github.com" in url_lower or "gitlab.com" in url_lower:
            return "repositorio github"
            
        for news_dom in [
            "nytimes.com", "bbc.com", "elpais.com", "elmundo.es", "cnn.com", "reuters.com",
            "bloomberg.com", "theguardian.com", "xataka.com", "techcrunch.com", "wired.com"
        ]:
            if news_dom in url_lower:
                return "noticia"
                
        for forum_dom in ["stackoverflow.com", "reddit.com", "quora.com", "stackexchange.com"]:
            if forum_dom in url_lower:
                return "foro/comunidad"
                
        if any(url_lower.endswith(f".{tld}") or f".{tld}/" in url_lower for tld in ["gov", "edu"]):
            return "oficial"
            
        if "wikipedia.org" in url_lower:
            return "oficial"
            
        if any(x in url_lower or x in title_lower for x in ["blog", "opinion", "medium.com", "dev.to"]):
            return "blog"
            
        return "sitio web"

    def _rank_items_by_authority(self, items: List[KnowledgeItem], plan: KnowledgePlan) -> List[KnowledgeItem]:
        """Evalúa la autoridad de las fuentes según la prioridad cognitiva del plan."""
        def get_score(item: KnowledgeItem) -> float:
            url = item.url.lower()
            title = item.title.lower()
            score = item.score
            
            # Si proviene de la memoria local, dar prioridad alta para asegurar RAG local primero
            if item.source_type == "memoria":
                return score + 3.0
                
            # Boosting según el plan del KnowledgePlanner
            for p_type in plan.priority_types:
                if p_type == "github" and "repositorio github" in item.source_type:
                    score += 2.0
                elif p_type == "documentation" and "documentación" in item.source_type:
                    score += 2.0
                elif p_type == "news" and "noticia" in item.source_type:
                    score += 2.0
                elif p_type == "foro" and "foro" in item.source_type:
                    score += 1.0
                    
            # Boosts generales de autoridad
            if any(url.endswith(f".{tld}") or f".{tld}/" in url for tld in ["gov", "edu"]):
                score += 1.5
            elif "wikipedia.org" in url:
                score += 1.0
                
            # Excluir spam
            if any(spam in url for spam in ["pinterest.com", "pinterest.es", "adware", "doubleclick"]):
                score -= 5.0
                
            return score

        ranked = sorted(items, key=get_score, reverse=True)
        return [i for i in ranked if get_score(i) > -1.0]

    def _diversify_items(self, items: List[KnowledgeItem], max_per_domain: int = 2) -> List[KnowledgeItem]:
        """Aplica diversificación limitando la cantidad de aportaciones de un mismo dominio."""
        seen_urls = set()
        domain_counts = {}
        diversified = []
        
        for item in items:
            url = item.url.strip()
            if not url or url in seen_urls:
                continue
                
            # Si es local, no tiene dominio web estándar
            if url.startswith("local://"):
                seen_urls.add(url)
                diversified.append(item)
                continue
                
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            
            count = domain_counts.get(domain, 0)
            if count >= max_per_domain:
                continue
                
            seen_urls.add(url)
            domain_counts[domain] = count + 1
            diversified.append(item)
            
        return diversified

    async def _scrape_url_via_browserless(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.browserless_url}/content",
                    json={"url": url}
                )
                if resp.status_code == 200:
                    max_len = self.config.get("scraping", {}).get("max_content_length", 2000)
                    return _html_to_markdown(resp.text, max_len)
        except Exception as e:
            logger.warning("[KnowledgeOrchestrator] Error scraping %s: %s", url, e)
        return ""

    async def _handle_special_intents(self, query: str) -> Optional[str]:
        """Intercepciones directas."""
        query_lower = query.lower()
        if re.search(r'\b(clima|tiempo|pronostico|temperatura|weather|lluvia)\b', query_lower):
            # Lógica Clima
            try:
                match = re.search(r"(?:clima|tiempo|pronostico|temperatura)\s+(?:en|de|para|de\s+estos\s+dias\s+en)?\s*([^?.,\n]+)", query, re.IGNORECASE)
                city = match.group(1).strip() if match else "Reynosa, Tamaulipas"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    headers = {"User-Agent": "CerebroAutonomo/1.0"}
                    geo_resp = await client.get(
                        f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(city)}&format=json&limit=1",
                        headers=headers
                    )
                    if geo_resp.status_code == 200:
                        geo_data = geo_resp.json()
                        if geo_data:
                            lat = geo_data[0]["lat"]
                            lon = geo_data[0]["lon"]
                            display_name = geo_data[0]["display_name"]
                            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto"
                            weather_resp = await client.get(weather_url)
                            if weather_resp.status_code == 200:
                                weather_data = weather_resp.json()
                                loc_parts = display_name.split(",")
                                location = loc_parts[0] + ", " + loc_parts[-1].strip()
                                weather_payload = {"location": location, "current": weather_data["current_weather"], "daily": weather_data["daily"]}
                                summary = (
                                    f"Resultados del clima en {location}: Temperatura actual de {weather_payload['current']['temperature']}°C, "
                                    f"máxima hoy: {weather_data['daily']['temperature_2m_max'][0]}°C, "
                                    f"mínima: {weather_data['daily']['temperature_2m_min'][0]}°C, "
                                    f"probabilidad de lluvia: {weather_data['daily']['precipitation_probability_max'][0]}%."
                                )
                                return f"<weather_data>{json.dumps(weather_payload)}</weather_data>\n\n{summary}"
            except Exception as e:
                logger.warning("[KnowledgeOrchestrator] Error en clima: %s", e)
                
        if re.search(r'\b(youtube|video|musica|cancion|reproducir|videoclip)\b', query_lower):
            # Lógica YouTube
            youtube_api_key = os.getenv("YOUTUBE_API_KEY")
            if youtube_api_key:
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        yt_url = "https://www.googleapis.com/youtube/v3/search"
                        yt_resp = await client.get(
                            yt_url,
                            params={"part": "snippet", "q": query, "type": "video", "maxResults": 4, "key": youtube_api_key}
                        )
                        if yt_resp.status_code == 200:
                            items = yt_resp.json().get("items", [])
                            if items:
                                output_parts = []
                                for i, item in enumerate(items):
                                    video_id = item.get("id", {}).get("videoId")
                                    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                                    snippet = item.get("snippet", {})
                                    entry = f"Resultado {i+1}:\n- Título: {snippet.get('title')}\n- URL: {video_url}\n- Contenido: {snippet.get('description')}\n"
                                    output_parts.append(entry)
                                return f"Resultados de YouTube obtenidos en tiempo real para '{query}':\n\n" + "\n".join(output_parts)
                except Exception as e:
                    logger.warning("[KnowledgeOrchestrator] Error en YouTube: %s", e)
        return None

    async def search(self, query: str, history: list = None) -> str:
        """
        Flujo de procesamiento cognitivo de conocimiento.
        
        1. Consulta memoria semántica local de inmediato.
        2. Planifica la estrategia de conocimiento basándose en los recuerdos locales.
        3. Recupera de múltiples fuentes (memoria, docs, github, etc.) en paralelo.
        4. Agrupa, diversifica, evalúa la autoridad y scrapea contenido renderizado.
        5. Rerankea semánticamente y construye referencias citable precisas.
        """
        logger.info("[KnowledgeOrchestrator] Iniciando procesamiento de conocimiento para: '%s'", query)
        
        # Intercepciones directas
        special_output = await self._handle_special_intents(query)
        if special_output:
            return special_output

        # 1. Recuperar recuerdos locales de la memoria semántica inmediatamente
        local_memories = []
        query_embedding = None
        if self.embeddings_client:
            try:
                query_embedding = await self.embeddings_client.get_embedding(query)
            except Exception as e:
                logger.warning("Fallo obteniendo embedding de consulta: %s", e)
                
        if self.db:
            try:
                threshold = self.config.get("database", {}).get("similarity_threshold", 0.40)
                local_memories = await self.db.search_semantic(
                    query_text=query,
                    query_embedding=query_embedding,
                    similarity_threshold=threshold,
                    limit=5
                )
            except Exception as e:
                logger.error("Error consultando memoria semántica local: %s", e)

        # Convertir recuerdos locales a formato de KnowledgeItem
        memory_items = []
        for node in local_memories:
            distance = node.get("distance", 1.0)
            similarity = 1.0 - (distance / 2.0)
            memory_items.append(KnowledgeItem(
                title="Memoria Semántica Local",
                url=f"local://node/{node.get('id')}",
                content=node.get("content", ""),
                score=similarity,
                source_type="memoria",
                created_at=node.get("created_at", 0)
            ))

        # 2. Planificar Estrategia (KnowledgePlanner)
        plan = await self.planner.plan_knowledge(query, history, local_memories)
        logger.info("[KnowledgeOrchestrator] Razón del plan: '%s'", plan.strategy_explanation)

        # Si el planificador decide que la memoria es suficiente, evitar consulta web externa
        if plan.sufficient_in_memory:
            logger.info("[KnowledgeOrchestrator] Memoria semántica local declarada SUFICIENTE. Evitando web search.")
            if not memory_items:
                return "La memoria local se marcó como suficiente pero no se encontraron registros coincidentes."
            
            # Formatear el contexto únicamente con la memoria
            citation_builder = CitationBuilder()
            formatted_chunks = []
            
            for item in memory_items[:4]:
                marker = citation_builder.get_citation_marker(item.title, item.url, "local", item.source_type)
                entry = (
                    f"### Fragmento Citable {marker} (Memoria Local):\n"
                    f"- Contenido:\n{item.content}\n---"
                )
                formatted_chunks.append(entry)
                
            header = (
                "Información provista directamente desde la memoria semántica local persistente.\n"
                f"Consulta analizada: '{query}'\n\n"
                "INSTRUCCIONES DE CONTEXTO RAG:\n"
                "- Esta información proviene de interacciones o aprendizajes pasados.\n"
                "- Cita utilizando el marcador bibliográfico al final de tus oraciones (ej. [1]).\n\n"
                "--- INICIO DE CONTEXTO LOCAL ---\n\n"
            )
            
            bibliography = citation_builder.build_bibliography()
            return header + "\n".join(formatted_chunks) + "\n\n" + bibliography + "\n\n--- FIN DE CONTEXTO LOCAL ---"

        # 3. Recuperación Multi-Fuente en Paralelo
        all_retrieved_items = list(memory_items)  # Integrar recuerdos locales como candidatos principales
        
        source_tasks = []
        for src_cfg in plan.sources:
            sid = src_cfg.get("source_id")
            queries_for_source = src_cfg.get("queries", [query])
            
            source_impl = self.knowledge_sources.get(sid)
            if source_impl:
                source_tasks.append(source_impl.retrieve(queries_for_source, plan, self))
                
        if source_tasks:
            retrieved_lists = await asyncio.gather(*source_tasks)
            for r_list in retrieved_lists:
                all_retrieved_items.extend(r_list)

        # 4. Pipeline de Consolidación e IR
        # Diversificar por dominio
        diversified_items = self._diversify_items(all_retrieved_items, max_per_domain=2)
        # Ordenar por autoridad según el plan estratégico
        ranked_items = self._rank_items_by_authority(diversified_items, plan)
        
        if not ranked_items:
            return "No se pudo consolidar información útil de memoria ni de fuentes externas."

        # Tomar los mejores candidatos para raspado/consolidación de texto
        top_candidates = ranked_items[:4]
        
        # Separar candidatos locales y externos para optimizar scraping
        local_candidates = [i for i in top_candidates if i.url.startswith("local://")]
        external_candidates = [i for i in top_candidates if not i.url.startswith("local://")]
        
        # Raspado concurrente solo de páginas web
        scraped_texts = []
        if external_candidates:
            scrape_tasks = [self._scrape_url_via_browserless(item.url) for item in external_candidates]
            scraped_texts = await asyncio.gather(*scrape_tasks)
            
        # 5. Fragmentación y Reranking Semántico Unificado
        all_chunks = []
        chunk_to_item = {}
        
        # Procesar candidatos locales
        for item in local_candidates:
            if self.embeddings_client:
                chunks = self.embeddings_client.chunk_text(item.content, max_chars=1200)
                for ch in chunks:
                    ch_strip = ch.strip()
                    if ch_strip:
                        all_chunks.append(ch_strip)
                        chunk_to_item[ch_strip] = item
            else:
                all_chunks.append(item.content)
                chunk_to_item[item.content] = item

        # Procesar candidatos externos scrapeados
        for idx, item in enumerate(external_candidates):
            content = scraped_texts[idx] if idx < len(scraped_texts) else ""
            if not content or not content.strip():
                # Caer en el snippet del buscador si falló el scraping
                content = item.content
                
            if not content or not content.strip():
                continue
                
            if self.embeddings_client:
                chunks = self.embeddings_client.chunk_text(content, max_chars=1200)
                for ch in chunks:
                    ch_strip = ch.strip()
                    if ch_strip:
                        all_chunks.append(ch_strip)
                        chunk_to_item[ch_strip] = item
            else:
                all_chunks.append(content)
                chunk_to_item[content] = item

        if not all_chunks:
            return "No se encontró texto citable tras procesar los orígenes de conocimiento."

        # Reranking Semántico de todos los fragmentos consolidados (Memoria + Web)
        reranked_chunks = []
        if self.embeddings_client:
            try:
                reranked_chunks = await self.embeddings_client.rerank(query, all_chunks, top_n=4)
                reranked_chunks = reranked_chunks if reranked_chunks is not None else []
            except Exception as e:
                logger.error("[KnowledgeOrchestrator] Error en Rerank unificado: %s", e)
                
        if not reranked_chunks:
            reranked_chunks = all_chunks[:4]

        # 6. Citation Builder y Formateo Final
        citation_builder = CitationBuilder()
        formatted_chunks = []
        
        for chunk in reranked_chunks:
            item = chunk_to_item.get(chunk)
            if not item:
                continue
                
            parsed_url = urllib.parse.urlparse(item.url)
            domain = parsed_url.netloc.lower() if not item.url.startswith("local://") else "local"
            
            marker = citation_builder.get_citation_marker(
                item.title, item.url, domain, item.source_type
            )
            
            entry = (
                f"### Fragmento Citable {marker} [Origen: {item.source_type.upper()}]:\n"
                f"- Título: {item.title}\n"
                f"- URL: {item.url}\n"
                f"- Contenido:\n{chunk}\n---"
            )
            formatted_chunks.append(entry)
            
        bibliography = citation_builder.build_bibliography()
        
        header = (
            "Consolidación unificada de conocimiento (Memoria semántica local + Ingesta web en tiempo real).\n"
            f"Consulta analizada: '{query}'\n"
            f"Estrategia de recuperación: '{plan.strategy_explanation}'\n\n"
            "INSTRUCCIONES DE CONTEXTO RAG (ESTRICTAS):\n"
            "- Este bloque integra recuerdos locales e información externa. Considéralo tu única fuente de verdad.\n"
            "- Asocia tus afirmaciones detallando obligatoriamente el marcador bibliográfico al final de la oración (ej. [1]).\n"
            "- No inventes, extrapoles ni deduzcas nada que no aparezca textualmente en los fragmentos.\n"
            "- Si los fragmentos no responden la pregunta de forma completa, dilo de forma honesta.\n\n"
            "--- INICIO DE CONTEXTO UNIFICADO ---\n\n"
        )
        
        return header + "\n".join(formatted_chunks) + "\n\n" + bibliography + "\n\n--- FIN DE CONTEXTO UNIFICADO ---"


# Alias para compatibilidad externa con el nombre de clase previo
SearchOrchestrator = KnowledgeOrchestrator

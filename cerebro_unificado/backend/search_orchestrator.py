"""
search_orchestrator.py — Componente único y centralizado de recuperación de información web.

Implementa un pipeline avanzado de búsqueda, expansión de consultas (multi-query),
navegación y renderizado mediante Browserless, deduplicación por dominio, scraping en paralelo,
chunking y reordenamiento semántico (rerank).
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

logger = logging.getLogger("cerebro.search_orchestrator")

# ─── Configuración de Diccionarios y Constantes ───

_INTENT_KEYWORDS = {
    "clima": ["clima", "tiempo", "pronostico", "weather", "temperatura", "lluvia", "viento", "sol", "nieve", "humedad", "calor", "frio"],
    "youtube": ["youtube", "video", "musica", "music", "song", "cancion", "reproducir", "videoclip", "clip", "canal de yt", "trailer"],
    "noticias": ["noticias", "news", "periodico", "actualidad", "suceso", "rebelion", "elecciones", "presidente", "gobierno", "declaraciones", "crisis", "atentado", "guerra"],
    "deportes": ["deportes", "sports", "futbol", "soccer", "laliga", "champions", "nba", "nfl", "formula 1", "f1", "partido", "resultados", "clasificacion", "fichajes", "olimpiadas", "juegos olimpicos"],
    "precios": ["precio", "costo", "comprar", "venta", "tienda", "amazon", "ebay", "mercadolibre", "aliexpress", "oferta", "descuento", "barato", "dolares", "pesos", "euros"],
    "documentacion": ["documentacion", "documentation", "docs", "api", "reference", "manual", "guia", "guide", "tutorial"],
    "github": ["github", "repository", "repositorio", "commit", "pull request", "pr", "issue", "fork", "git"],
    "programacion": ["programacion", "codigo", "code", "desarrollo", "error", "exception", "bug", "stack overflow", "framework", "library", "libreria", "python", "javascript", "typescript", "rust", "c++", "java", "golang", "go-lang"],
    "empresas": ["empresa", "company", "corporation", "corp", "startup", "ceo", "acciones", "bolsa", "ingresos", "fundador", "adquisicion", "sede"],
    "productos": ["producto", "product", "review", "analisis", "especificaciones", "caracteristicas", "modelo", "marca", "lanzamiento", "hardware", "software"],
    "mapas": ["mapa", "map", "direccion", "como llegar", "ubicacion", "gps", "coordenadas", "ruta", "distancia", "calle", "ciudad", "pais"],
    "personas": ["biografia", "vida", "nacimiento", "muerte", "quien es", "trayectoria", "edad", "esposa", "esposo", "hijos", "actor", "cantante", "cientifico"],
    "eventos": ["evento", "concierto", "festival", "conferencia", "expo", "feria", "fecha", "lugar", "boletos", "entradas"],
    "musica": ["album", "disco", "artista", "banda", "letra", "lyrics", "genero musical", "concierto", "gira"],
    "peliculas": ["pelicula", "movie", "film", "cine", "director", "reparto", "elenco", "estreno", "oscar", "sinopsis"],
    "series": ["serie", "temporada", "episodio", "capitulo", "netflix", "hbo", "disney+", "show", "tv show"],
    "actualidad": ["hoy", "ayer", "mañana", "esta semana", "este mes", "este año", "actualizado", "reciente", "ultimo momento"]
}

_DOMAIN_CLASSIFICATION = {
    "documentacion": [
        "docs.python.org", "developer.mozilla.org", "react.dev", "svelte.dev", "tailwindcss.com",
        "nextjs.org", "vite.dev", "fastapi.tiangolo.com", "pkg.go.dev", "rust-lang.org",
        "docs.microsoft.com", "support.google.com", "aws.amazon.com/docs", "kubernetes.io/docs"
    ],
    "github": ["github.com", "gitlab.com", "bitbucket.org"],
    "noticias": [
        "nytimes.com", "bbc.com", "elpais.com", "elmundo.es", "cnn.com", "reuters.com",
        "bloomberg.com", "theguardian.com", "xataka.com", "techcrunch.com", "wired.com"
    ],
    "foro": ["stackoverflow.com", "reddit.com", "quora.com", "stackexchange.com", "discord.gg"],
    "video": ["youtube.com", "youtu.be", "vimeo.com", "twitch.tv"]
}

_SPAM_DOMAINS = [
    "pinterest.com", "pinterest.es", "clickbait", "adware", "spam", "doubleclick",
    "survey", "win-free", "sponsored", "cheap-deals"
]


# ─── Utilidades Auxiliares ───

def _decode_bing_url(url: str) -> str:
    """Decodifica el redireccionamiento base64 nativo en URLs de Bing."""
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
                    # Añadir padding si es necesario
                    padding = len(encoded) % 4
                    if padding:
                        encoded += "=" * (4 - padding)
                    decoded = base64.urlsafe_b64decode(encoded).decode("utf-8", errors="ignore")
                    return decoded
    except Exception as e:
        logger.debug("Error decodificando URL de Bing: %s", e)
    return url


def _html_to_markdown(html_content: str, max_length: int = 2000) -> str:
    """Extrae texto de un documento HTML y lo formatea como Markdown legible."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Eliminar tags de scripts, estilos, menús, etc.
    noise_tags = [
        "nav", "header", "footer", "script", "style", "aside", 
        "iframe", "noscript", "svg", "form", "button", "head", "meta", "link"
    ]
    for tag in soup.find_all(noise_tags):
        tag.decompose()
        
    # Intentar centrar en el contenedor principal
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


# ─── Motores de Búsqueda (Providers) ───

class SearchEngineProvider(ABC):
    """Interfaz abstracta para los proveedores de motores de búsqueda."""
    
    @abstractmethod
    async def search(self, query: str, browserless_url: str) -> List[Dict[str, str]]:
        """Realiza una búsqueda y devuelve una lista de diccionarios con title, url, snippet."""
        pass


class BingSearchProvider(SearchEngineProvider):
    """Proveedor de búsqueda basado en Bing mediante renderizado de Browserless."""
    
    async def search(self, query: str, browserless_url: str) -> List[Dict[str, str]]:
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        logger.info("[BingProvider] Consultando Bing via Browserless para: '%s'", query)
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
            
            for item in soup.find_all("li", class_="b_algo"):
                h2 = item.find("h2")
                a = h2.find("a") if h2 else None
                snippet_div = item.find("div", class_="b_caption") or item.find("p")
                
                if a and a.has_attr("href"):
                    raw_url = a["href"]
                    resolved_url = _decode_bing_url(raw_url)
                    title = a.get_text(strip=True)
                    snippet = snippet_div.get_text(strip=True) if snippet_div else ""
                    
                    if title and resolved_url:
                        results.append({
                            "title": title,
                            "url": resolved_url,
                            "snippet": snippet
                        })
            return results
        except Exception as e:
            logger.error("[BingProvider] Error realizando búsqueda: %s", e)
            return []


class SearXNGSearchProvider(SearchEngineProvider):
    """Proveedor de búsqueda directa al endpoint de SearXNG (puerto 8888)."""
    
    async def search(self, query: str, browserless_url: str) -> List[Dict[str, str]]:
        logger.info("[SearXNGProvider] Consultando SearXNG para: '%s'", query)
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
                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": re.sub(r'<[^>]+>', '', snippet).strip()
                    })
            return results
        except Exception as e:
            logger.error("[SearXNGProvider] Error consultando SearXNG: %s", e)
            return []


class DuckDuckGoSearchProvider(SearchEngineProvider):
    """Proveedor de búsqueda de respaldo usando DuckDuckGo."""
    
    async def search(self, query: str, browserless_url: str) -> List[Dict[str, str]]:
        logger.info("[DDGProvider] Intentando búsqueda en DuckDuckGo para: '%s'", query)
        try:
            from ddgs import DDGS
            from ddgs.exceptions import RatelimitException

            with DDGS() as ddgs:
                try:
                    raw_results = ddgs.text(query, safesearch="moderate", max_results=5)
                    raw_results = raw_results if raw_results is not None else []
                except RatelimitException as e:
                    logger.warning("[DDGProvider] DuckDuckGo rate limit: %s", e)
                    return []

            results = []
            for r in raw_results:
                title = (r.get("title") or "").strip()
                url = (r.get("href") or "").strip()
                snippet = (r.get("body") or "").strip()
                if title and url:
                    results.append({"title": title, "url": url, "snippet": snippet})
            return results
        except Exception as exc:
            logger.error("[DDGProvider] Fallo en DuckDuckGo provider: %s", exc)
            return []


# ─── Orquestador Principal ───

class SearchOrchestrator:
    """Orquestador único y centralizado de recuperación de información web (RAG)."""
    
    def __init__(self, config: dict, embeddings_client: Any, db: Any) -> None:
        self.config = config
        self.embeddings_client = embeddings_client
        self.db = db
        
        # Cargar configuraciones del orchestrator o proveer fallbacks
        search_config = config.get("search", {})
        self.browserless_url = search_config.get("browserless_url", "http://127.0.0.1:3000")
        self.provider_name = search_config.get("provider", "bing").lower()
        self.max_queries = search_config.get("max_queries", 2)
        self.max_results_per_query = search_config.get("max_results_per_query", 5)
        
        # Mapeo de proveedores
        self.providers: Dict[str, SearchEngineProvider] = {
            "bing": BingSearchProvider(),
            "searxng": SearXNGSearchProvider(),
            "duckduckgo": DuckDuckGoSearchProvider(),
            "google": BingSearchProvider(), # Google CAPTCHAs are severe; fallback to Bing on headless
            "brave": BingSearchProvider()   # Brave CAPTCHAs are severe; fallback to Bing on headless
        }
        
    def _get_provider(self) -> SearchEngineProvider:
        return self.providers.get(self.provider_name, BingSearchProvider())
        
    def _normalize_query(self, query: str) -> str:
        """Limpia espacios, remueve acentos y signos extraños de la consulta."""
        if not query:
            return ""
        query_clean = ''.join(
            c for c in unicodedata.normalize('NFD', query)
            if unicodedata.category(c) != 'Mn'
        )
        query_clean = re.sub(r'[^\w\s\-\.]', ' ', query_clean)
        query_clean = re.sub(r'\s+', ' ', query_clean).strip()
        return query_clean

    def _detect_search_type(self, query: str) -> str:
        """Detecta la intención semántica de la consulta."""
        query_lower = query.lower()
        if re.search(r'\b(clima|tiempo|pronostico|temperatura|weather|lluvia)\b', query_lower):
            return "clima"
        if re.search(r'\b(youtube|video|musica|cancion|reproducir|videoclip)\b', query_lower):
            return "youtube"
            
        intent_scores = {}
        for intent, keywords in _INTENT_KEYWORDS.items():
            score = 0
            for kw in keywords:
                if f" {kw} " in f" {query_lower} " or query_lower.startswith(kw) or query_lower.endswith(kw):
                    score += 3
                elif kw in query_lower:
                    score += 1
            if score > 0:
                intent_scores[intent] = score
                
        if intent_scores:
            return max(intent_scores, key=intent_scores.get)
        return "general"

    async def _expand_queries(self, query: str, history: list = None) -> List[str]:
        """Usa el LLM para reescribir y generar múltiples consultas web específicas."""
        queries = [query]
        if not history:
            # Búsqueda de un término corto sin historial
            words = query.strip().split()
            if len(words) <= 1:
                intent = self._detect_search_type(query)
                if intent in ["programacion", "documentacion"]:
                    queries.append(f"{query} oficial documentacion guia api")
                elif intent == "github":
                    queries.append(f"{query} github repository")
                elif intent in ["noticias", "actualidad"]:
                    queries.append(f"{query} ultimas noticias hoy")
            return list(set(queries))
            
        try:
            prompt = (
                "Dada la siguiente conversación y una nueva pregunta, genera hasta 3 consultas de búsqueda web "
                "específicas e independientes para obtener información completa de diferentes fuentes.\n"
                "Devuelve ÚNICAMENTE un bloque JSON con una lista de strings (ej. [\"query1\", \"query2\"]), sin explicaciones ni formato markdown.\n\n"
                "Historial de conversación:\n"
            )
            for msg in history[-4:]:
                role = "Usuario" if msg.get("role") == "user" else "IA"
                content = re.sub(r'<[^>]+>[\s\S]*?<\/[^>]+>', '', msg.get("content", "")).strip()
                prompt += f"{role}: {content[:150]}\n"
                
            prompt += f"Nueva pregunta: {query}\n"
            prompt += "Consultas de búsqueda JSON:"
            
            llm_url = self.config.get("llm", {}).get("server_url", "http://127.0.0.1:8080")
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{llm_url}/v1/chat/completions",
                    json={
                        "messages": [
                            {"role": "system", "content": "Eres un asistente experto en RAG que expande y formula búsquedas web precisas en formato JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 128,
                        "temperature": 0.0
                    }
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    if "</think>" in content:
                        content = content.split("</think>")[-1].strip()
                    # Limpiar markdown si el LLM lo retornó
                    content_clean = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', content).strip()
                    parsed = json.loads(content_clean)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        logger.info("[SearchOrchestrator] Multi-queries expandidas: %s", parsed)
                        return [q.strip() for q in parsed[:self.max_queries]]
        except Exception as e:
            logger.warning("[SearchOrchestrator] Error al expandir queries con el LLM: %s. Usando fallback.", e)
            
        return queries

    def _classify_source(self, url: str, title: str) -> str:
        """Clasifica el tipo de fuente (oficial, foro, blog, etc.) según su URL y título."""
        url_lower = url.lower()
        title_lower = title.lower()
        
        for doc_dom in _DOMAIN_CLASSIFICATION["documentacion"]:
            if doc_dom in url_lower:
                return "documentación"
        for gh_dom in _DOMAIN_CLASSIFICATION["github"]:
            if gh_dom in url_lower:
                return "repositorio"
        for news_dom in _DOMAIN_CLASSIFICATION["noticias"]:
            if news_dom in url_lower:
                return "noticia"
        for forum_dom in _DOMAIN_CLASSIFICATION["foro"]:
            if forum_dom in url_lower:
                return "foro"
        for video_dom in _DOMAIN_CLASSIFICATION["video"]:
            if video_dom in url_lower:
                return "video"
                
        if any(url_lower.endswith(f".{tld}") or f".{tld}/" in url_lower for tld in ["gov", "edu"]):
            return "oficial"
        if "wikipedia.org" in url_lower:
            return "oficial"
        if any(x in url_lower or x in title_lower for x in ["blog", "opinion", "medium.com", "dev.to"]):
            return "blog"
            
        return "sitio web"

    def _diversify_and_clean(self, results: list[dict], max_per_domain: int = 2) -> list[dict]:
        """Elimina URLs duplicadas, excluye spam y diversifica dominios (máximo N resultados por dominio)."""
        seen_urls = set()
        domain_counts = {}
        cleaned = []
        
        for r in results:
            url = r.get("url", "").strip()
            title = r.get("title", "").strip()
            snippet = r.get("snippet", "").strip()
            
            if not url or not title or url in seen_urls:
                continue
                
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            
            # Filtrar dominios spam
            if any(spam in domain for spam in _SPAM_DOMAINS):
                continue
                
            count = domain_counts.get(domain, 0)
            if count >= max_per_domain:
                continue
                
            seen_urls.add(url)
            domain_counts[domain] = count + 1
            cleaned.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "domain": domain
            })
            
        return cleaned

    async def _scrape_url_via_browserless(self, url: str) -> str:
        """Scrapea el contenido renderizado de una URL utilizando Browserless."""
        logger.info("[SearchOrchestrator] Scrapeando url via Browserless: %s", url)
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
            logger.warning("[SearchOrchestrator] Error scrapeando %s via Browserless: %s", url, e)
        return ""

    async def search(self, query: str, history: list = None) -> str:
        """
        Punto de entrada único del pipeline de recuperación de información de Internet.
        
        Intercepta de forma inteligente intenciones especiales (clima, youtube) y
        ejecuta un pipeline RAG completo (multi-query, Browserless, chunking, reranking)
        para búsquedas generales.
        """
        logger.info("[SearchOrchestrator] Iniciando pipeline de búsqueda para: '%s'", query)
        
        # 1. Normalización y detección de intención
        query_norm = self._normalize_query(query)
        intent = self._detect_search_type(query_norm)
        
        # Intercepción del Clima
        if intent == "clima":
            return await self._handle_weather(query)
            
        # Intercepción de YouTube
        if intent == "youtube":
            return await self._handle_youtube(query)
            
        # 2. Pipeline de Búsqueda Web RAG Avanzado
        try:
            # Expansión de consultas (Multi-Query)
            search_queries = await self._expand_queries(query, history)
            provider = self._get_provider()
            
            # Buscar en paralelo para cada query
            search_tasks = [provider.search(q, self.browserless_url) for q in search_queries]
            search_results_lists = await asyncio.gather(*search_tasks)
            
            # Fusionar todos los resultados
            merged_results = []
            for res_list in search_results_lists:
                merged_results.extend(res_list)
                
            # Deduplicación y diversificación de dominios
            clean_results = self._diversify_and_clean(merged_results, max_per_domain=2)
            if not clean_results:
                return "No se encontraron resultados relevantes en la web para esta consulta."
                
            # Seleccionar los top K enlaces más relevantes para raspar
            top_links = clean_results[:4]
            
            # Scraping en paralelo usando Browserless
            scrape_tasks = [self._scrape_url_via_browserless(item["url"]) for item in top_links]
            scraped_texts = await asyncio.gather(*scrape_tasks)
            
            # 3. Fragmentación (Chunking) y Reranking Semántico
            all_chunks = []
            chunk_to_source = {}
            
            for idx, item in enumerate(top_links):
                content = scraped_texts[idx]
                # Fallback al snippet si el scraping falló
                if not content or not content.strip():
                    snippet = item.get("snippet", "")
                    if snippet:
                        all_chunks.append(snippet)
                        chunk_to_source[snippet] = item
                    continue
                    
                # Dividir el texto en chunks
                if self.embeddings_client:
                    chunks = self.embeddings_client.chunk_text(content, max_chars=1200)
                    for ch in chunks:
                        ch_strip = ch.strip()
                        if ch_strip:
                            all_chunks.append(ch_strip)
                            chunk_to_source[ch_strip] = item
                else:
                    all_chunks.append(content)
                    chunk_to_source[content] = item
                    
            if not all_chunks:
                return "No se pudo recuperar contenido procesable de las páginas web."
                
            # Reranking semántico asíncrono
            reranked_chunks = []
            if self.embeddings_client:
                try:
                    reranked_chunks = await self.embeddings_client.rerank(query, all_chunks, top_n=4)
                    reranked_chunks = reranked_chunks if reranked_chunks is not None else []
                except Exception as e:
                    logger.error("[SearchOrchestrator] Error en Reranking semántico: %s", e)
                    
            if not reranked_chunks:
                reranked_chunks = all_chunks[:4]
                
            # 4. Formatear y construir contexto estructurado
            header = (
                "Estos resultados fueron obtenidos en tiempo real de internet mediante navegación virtual.\n"
                f"Consulta analizada: '{query}'\n\n"
                "INSTRUCCIONES DE CONTEXTO RAG:\n"
                "- Utiliza este bloque de información como tu única fuente principal y verídica.\n"
                "- Si varias fuentes coinciden en un dato, prioriza ese consenso.\n"
                "- Si existen discrepancias o contradicciones entre las fuentes, indícalas de forma transparente.\n"
                "- NO inventes, alucines o extrapolles información que no aparezca descrita explícitamente en el texto provisto.\n"
                "- En caso de que los datos sean insuficientes para responder, admítelo.\n\n"
                "--- INICIO DE CONTEXTO WEB ---\n\n"
            )
            
            formatted_parts = []
            for idx, chunk in enumerate(reranked_chunks):
                source = chunk_to_source.get(chunk, {})
                title = source.get("title", "Sitio Web")
                url = source.get("url", "")
                domain = source.get("domain", "")
                source_type = self._classify_source(url, title)
                
                entry = (
                    f"### Fragmento de Relevancia {idx+1}:\n"
                    f"- Título: {title}\n"
                    f"- Dominio: {domain}\n"
                    f"- URL: {url}\n"
                    f"- Tipo de fuente: {source_type}\n"
                    f"- Contenido:\n{chunk}\n---"
                )
                formatted_parts.append(entry)
                
            return header + "\n".join(formatted_parts) + "\n\n--- FIN DE CONTEXTO WEB ---"
            
        except Exception as exc:
            logger.error("[SearchOrchestrator] Fallo crítico en el pipeline: %s", exc)
            return f"[Error en la búsqueda y recuperación web]: {str(exc)}"

    async def _handle_weather(self, query: str) -> str:
        """Lógica de geocodificación y obtención de clima."""
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

                            weather_payload = {
                                "location": location,
                                "current": weather_data["current_weather"],
                                "daily": weather_data["daily"]
                            }

                            summary = (
                                f"Resultados del clima en {location}: Temperatura actual de {weather_payload['current']['temperature']}°C, "
                                f"máxima prevista hoy: {weather_data['daily']['temperature_2m_max'][0]}°C, "
                                f"mínima: {weather_data['daily']['temperature_2m_min'][0]}°C, "
                                f"probabilidad de lluvia: {weather_data['daily']['precipitation_probability_max'][0]}%."
                            )

                            return f"<weather_data>{json.dumps(weather_payload)}</weather_data>\n\n{summary}"
        except Exception as e:
            logger.warning("[SearchOrchestrator] Error en clima: %s", e)
        return "No se pudo recuperar la información del clima en este momento."

    async def _handle_youtube(self, query: str) -> str:
        """Lógica de búsqueda en la API oficial de YouTube."""
        youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        if not youtube_api_key:
            return "No se ha configurado la API Key de YouTube en las variables de entorno."
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                yt_url = "https://www.googleapis.com/youtube/v3/search"
                yt_resp = await client.get(
                    yt_url,
                    params={
                        "part": "snippet",
                        "q": query,
                        "type": "video",
                        "maxResults": 4,
                        "key": youtube_api_key
                    }
                )
                if yt_resp.status_code == 200:
                    yt_data = yt_resp.json()
                    items = yt_data.get("items", [])
                    if items:
                        output_parts = []
                        for i, item in enumerate(items):
                            video_id = item.get("id", {}).get("videoId")
                            video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                            snippet = item.get("snippet", {})
                            title = snippet.get("title", "")
                            description = snippet.get("description", "[No description]")
                            
                            entry = (
                                f"Resultado {i+1}:\n"
                                f"- Título: {title}\n"
                                f"- URL: {video_url}\n"
                                f"- Contenido: {description}\n"
                            )
                            output_parts.append(entry)

                        header = f"Resultados de YouTube obtenidos en tiempo real para '{query}':\n\n"
                        return header + "\n".join(output_parts)
        except Exception as e:
            logger.warning("[SearchOrchestrator] Error en YouTube: %s", e)
        return "No se pudieron obtener resultados de YouTube en este momento."

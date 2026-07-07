"""
web_scraper.py — Módulo de ingesta, limpieza y parsing de fuentes web.

Fase 5: Implementación completa del scraper asíncrono.
Ver Sección 5 del Proyecto.md para la especificación completa.
"""

from __future__ import annotations

import logging
import json
import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("cerebro.web_scraper")

SOURCES_PATH = Path(__file__).resolve().parent / "sources.json"


async def perform_web_search(query: str) -> list[dict]:
    """Realiza una consulta a la API local de SearXNG (puerto 8888) y devuelve los 4 enlaces más relevantes."""
    logger.info("[Web Search] Consultando SearXNG para: '%s'", query)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "http://127.0.0.1:8888/search",
                params={"q": query, "format": "json"}
            )
            response.raise_for_status()
            data = response.json()
            
        results = data.get("results", [])
        if not results:
            return []
            
        seen_urls = set()
        cleaned_results = []
        
        for r in results:
            title = r.get("title", "").strip()
            url = r.get("url", "").strip()
            snippet = r.get("content", "").strip()
            
            if not title or not url or url in seen_urls:
                continue
                
            seen_urls.add(url)
            
            # Saneamiento de HTML en snippet
            snippet_clean = re.sub(r'<[^>]+>', '', snippet).strip()
            
            cleaned_results.append({
                "title": title,
                "url": url,
                "snippet": snippet_clean
            })
            
            if len(cleaned_results) >= 4:
                break
                
        return cleaned_results
    except Exception as exc:
        logger.error("[Web Search] Error consultando SearXNG: %s", exc)
        return []


def html_to_markdown(html_content: str, max_length: int = 2000) -> str:
    """Extrae el contenido principal del HTML y lo convierte a Markdown limpio."""
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Eliminar elementos ruidosos
    noise_tags = [
        "nav", "header", "footer", "script", "style", "aside", 
        "iframe", "noscript", "svg", "form", "button", "head", "meta", "link"
    ]
    for tag in soup.find_all(noise_tags):
        tag.decompose()
        
    # Intentar detectar el contenedor principal
    main_element = soup.find(["article", "main", "[role='main']", "#content", ".content", "#main-content"])
    if main_element:
        soup = main_element  # type: ignore[assignment]
        
    markdown_lines = []
    
    # Recorrer elementos comunes y mapearlos a Markdown
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
    
    # Si no se pudo estructurar, hacer fallback al extractor genérico
    if not clean_text:
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)
        
    # Truncar para prevenir saturación
    if len(clean_text) > max_length:
        clean_text = clean_text[:max_length] + "\n... [Contenido Web Truncado]"
        
    return clean_text


async def scrape_url(url: str, max_length: int = 2000) -> str:
    """Descarga el HTML de la URL y extrae el texto principal formateado como Markdown limpio."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3"
    }
    logger.info("[Web Scraper] Raspando URL: %s", url)
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return html_to_markdown(response.text, max_length)
    except Exception as exc:
        logger.error("[Web Scraper] Fallo al raspar la URL %s: %s", url, exc)
        return f"[Error al cargar la URL]: {str(exc)}"


async def scrape_multiple_urls(urls: list[str], max_length: int = 2000) -> list[str]:
    """Raspa múltiples URLs en paralelo usando asyncio.gather."""
    tasks = [scrape_url(url, max_length) for url in urls]
    return await asyncio.gather(*tasks)


class WebScraper:
    """Orquestador de ingesta web modular y resiliente."""

    def __init__(self, config: dict) -> None:
        """
        Args:
            config: Configuración global cargada desde config.yaml.
        """
        self.config = config
        self.max_content_length = config["scraping"].get("max_content_length", 2000)
        self.rules: list[dict] = []
        self._load_rules()

    def _load_rules(self) -> None:
        """Carga las reglas de extracción específicas por dominio desde sources.json."""
        if SOURCES_PATH.exists():
            try:
                with open(SOURCES_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                    self.rules = data.get("sources", [])
                logger.info("Cargadas %d reglas de extracción específicas desde sources.json", len(self.rules))
            except Exception as exc:
                logger.error("Error al cargar sources.json: %s. Se usará scraping genérico.", exc)
        else:
            logger.warning("No se encontró sources.json en %s. Usando scraping genérico.", SOURCES_PATH)

    def _get_rule_for_url(self, url: str) -> dict | None:
        """Busca si hay una regla específica que coincida con el dominio de la URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            for rule in self.rules:
                rule_domain = rule.get("domain", "").lower()
                # Coincidir dominio completo o subdominio
                if rule_domain and (domain == rule_domain or domain.endswith("." + rule_domain)):
                    return rule
        except Exception as exc:
            logger.warning("Fallo al parsear dominio de URL %s: %s", url, exc)
        return None

    def clean_html(self, html_content: str, rule: dict | None = None) -> str:
        """Limpia el código HTML y extrae el texto plano legible."""
        return html_to_markdown(html_content, self.max_content_length)

    async def scrape_url(self, url: str) -> str:
        """Realiza la petición HTTP asíncrona a la URL y devuelve el texto plano limpio."""
        return await scrape_url(url, self.max_content_length)

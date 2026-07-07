"""
web_scraper.py — Módulo de ingesta, limpieza y parsing de fuentes web.

Fase 5: Implementación completa del scraper asíncrono.
Ver Sección 5 del Proyecto.md para la especificación completa.
"""

from __future__ import annotations

import logging
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("cerebro.web_scraper")

SOURCES_PATH = Path(__file__).resolve().parent / "sources.json"


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
                if rule_domain and (domain == rule_domain or domain.endsWith("." + rule_domain)):
                    return rule
        except Exception as exc:
            logger.warning("Fallo al parsear dominio de URL %s: %s", url, exc)
        return None

    def clean_html(self, html_content: str, rule: dict | None = None) -> str:
        """Limpia el código HTML y extrae el texto plano legible.

        Usa selectores específicos si hay una regla, o algoritmos genéricos si no.
        Descarta elementos ruidosos como barras de navegación, menús, scripts, estilos.
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Si hay una regla específica con selector, extraer solo esa sección
        if rule and rule.get("selector"):
            selector = rule["selector"]
            element = soup.select_one(selector)
            if element:
                # Reemplazar soup con la sección seleccionada
                soup = element
                logger.debug("Aplicado selector específico '%s' para extracción", selector)
            else:
                logger.warning("Selector '%s' no encontró elementos en el HTML. Usando fallback genérico.", selector)

        # 2. Si es genérico, descartar elementos de ruido ruidosos (cabeceras, scripts, etc.)
        if not rule or not rule.get("selector"):
            noise_tags = [
                "nav", "header", "footer", "script", "style", "aside", 
                "iframe", "noscript", "svg", "form", "button"
            ]
            for tag in soup.find_all(noise_tags):
                tag.decompose()

            # Intentar buscar un contenedor de contenido principal común
            main_element = soup.find(["article", "main", "#content", ".content", "#main-content"])
            if main_element:
                soup = main_element  # type: ignore[assignment]
                logger.debug("Selector genérico auto-detectó contenedor principal")

        # 3. Extraer el texto limpio
        # Reemplazar saltos de línea múltiples por simples y espaciado consistente
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        # 4. Truncar para prevenir saturación de la base de datos (Anti-Saturación, Sección 5)
        if len(clean_text) > self.max_content_length:
            logger.info("Contenido web truncado de %d a %d caracteres", len(clean_text), self.max_content_length)
            clean_text = clean_text[:self.max_content_length] + "\n... [Contenido Web Truncado]"

        return clean_text

    async def scrape_url(self, url: str) -> str:
        """Realiza la petición HTTP asíncrona a la URL y devuelve el texto plano limpio.

        Aplica las cabeceras configuradas en sources.json o cabeceras de navegador por defecto.
        """
        rule = self._get_rule_for_url(url)
        
        # Cabeceras por defecto
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3"
        }
        
        # Mezclar con cabeceras específicas de la regla si existen
        if rule and rule.get("headers"):
            headers.update(rule["headers"])

        logger.info("Realizando petición GET asíncrona a: %s", url)

        # Usar httpx asíncrono con timeout estricto
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            html_content = response.text
            clean_text = self.clean_html(html_content, rule)
            return clean_text

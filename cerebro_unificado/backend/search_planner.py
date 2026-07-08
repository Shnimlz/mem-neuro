"""
search_planner.py — Componente de planificación inteligente de estrategias de búsqueda (RAG).

Decide si se requiere buscar en la web, qué consultas formular, qué buscador
emplear y qué tipo de fuentes priorizar basándose en el historial y la consulta del usuario.
"""

from __future__ import annotations

import logging
import re
import json
from typing import Any, List, Dict, Optional
import httpx

logger = logging.getLogger("cerebro.search_planner")

class SearchPlan:
    """Representa la estrategia planificada para la recuperación de información."""
    
    def __init__(
        self,
        needs_search: bool,
        provider: str,
        queries: List[str],
        prioritize_github: bool,
        prioritize_documentation: bool,
        information_recency: str,
        reasoning_explanation: str
    ):
        self.needs_search = needs_search
        self.provider = provider
        self.queries = queries
        self.prioritize_github = prioritize_github
        self.prioritize_documentation = prioritize_documentation
        self.information_recency = information_recency  # "fresh", "standard", "none"
        self.reasoning_explanation = reasoning_explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "needs_search": self.needs_search,
            "provider": self.provider,
            "queries": self.queries,
            "prioritize_github": self.prioritize_github,
            "prioritize_documentation": self.prioritize_documentation,
            "information_recency": self.information_recency,
            "reasoning_explanation": self.reasoning_explanation
        }


class SearchPlanner:
    """Clase encargada de razonar y decidir la estrategia de búsqueda."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.llm_url = config.get("llm", {}).get("server_url", "http://127.0.0.1:8080")
        self.default_provider = config.get("search", {}).get("provider", "bing")

    def _generate_heuristic_plan(self, query: str) -> SearchPlan:
        """Genera un plan de búsqueda basado en heurísticas/reglas deterministas si falla el LLM."""
        query_lower = query.lower()
        
        # Heurística para ver si requiere búsqueda
        is_conversational = any(
            re.search(rf"\b{word}\b", query_lower)
            for word in ["hola", "buenos dias", "gracias", "adios", "como estas", "quien eres", "jajaja"]
        )
        needs_search = not is_conversational
        
        # Heurísticas de prioridad
        prioritize_github = any(x in query_lower for x in ["github", "repository", "repositorio", "commit", "pr", "issue", "fork"])
        prioritize_documentation = any(x in query_lower for x in ["docs", "api", "reference", "manual", "tutorial", "guia", "libreria", "library", "framework"])
        
        # Recency
        fresh_words = ["hoy", "ayer", "noticias", "clima", "precio", "dolar", "bolsa", "futbol", "partido", "resultados", "reciente"]
        information_recency = "fresh" if any(x in query_lower for x in fresh_words) else "standard"
        
        # Consultas de búsqueda
        queries = [query]
        
        return SearchPlan(
            needs_search=needs_search,
            provider=self.default_provider,
            queries=queries,
            prioritize_github=prioritize_github,
            prioritize_documentation=prioritize_documentation,
            information_recency=information_recency,
            reasoning_explanation="Planificación por heurísticas de respaldo."
        )

    async def plan_search(self, query: str, history: List[Dict[str, str]] = None) -> SearchPlan:
        """Determina la estrategia óptima de búsqueda consultando al LLM o cayendo en la heurística."""
        # Si la búsqueda está explícitamente deshabilitada en la config
        if not self.config.get("scraping", {}).get("enabled", True):
            return SearchPlan(
                needs_search=False,
                provider=self.default_provider,
                queries=[],
                prioritize_github=False,
                prioritize_documentation=False,
                information_recency="none",
                reasoning_explanation="Búsqueda web deshabilitada globalmente."
            )
            
        try:
            prompt = (
                "Analiza la consulta del usuario y el historial del chat para decidir si es necesario buscar información en internet "
                "y cómo hacerlo de forma óptima.\n"
                "Responde ÚNICAMENTE con un objeto JSON válido que siga este esquema exacto:\n"
                "{\n"
                "  \"needs_search\": bool,\n"
                "  \"provider\": \"bing\" | \"searxng\" | \"duckduckgo\" | \"google\",\n"
                "  \"queries\": [\"consulta 1\", \"consulta 2\"],\n"
                "  \"prioritize_github\": bool,\n"
                "  \"prioritize_documentation\": bool,\n"
                "  \"information_recency\": \"fresh\" | \"standard\" | \"none\",\n"
                "  \"reasoning_explanation\": \"breve justificación\"\n"
                "}\n\n"
                "No agregues texto explicativo ni bloques markdown. Responde solo con el JSON.\n\n"
            )
            
            if history:
                prompt += "Historial de conversación:\n"
                for msg in history[-4:]:
                    role = "Usuario" if msg.get("role") == "user" else "IA"
                    content = re.sub(r'<[^>]+>[\s\S]*?<\/[^>]+>', '', msg.get("content", "")).strip()
                    prompt += f"{role}: {content[:150]}\n"
                    
            prompt += f"\nPregunta del usuario: {query}\n"
            prompt += "JSON:"

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{self.llm_url}/v1/chat/completions",
                    json={
                        "messages": [
                            {"role": "system", "content": "Eres un asistente experto en RAG que diseña estrategias de búsqueda y planifica la recuperación de información."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 256,
                        "temperature": 0.0
                    }
                )
                
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    if "</think>" in content:
                        content = content.split("</think>")[-1].strip()
                    content_clean = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', content).strip()
                    
                    data = json.loads(content_clean)
                    
                    needs_search = bool(data.get("needs_search", True))
                    provider = str(data.get("provider", self.default_provider)).lower()
                    if provider not in ["bing", "searxng", "duckduckgo", "google"]:
                        provider = self.default_provider
                        
                    queries_raw = data.get("queries", [query])
                    queries = [q.strip() for q in queries_raw if q.strip()] if isinstance(queries_raw, list) else [query]
                    if not queries:
                        queries = [query]
                        
                    prioritize_github = bool(data.get("prioritize_github", False))
                    prioritize_documentation = bool(data.get("prioritize_documentation", False))
                    information_recency = str(data.get("information_recency", "standard")).lower()
                    if information_recency not in ["fresh", "standard", "none"]:
                        information_recency = "standard"
                        
                    reasoning = str(data.get("reasoning_explanation", "Planificación generada por el LLM."))
                    
                    logger.info("[SearchPlanner] Plan generado exitosamente por el LLM: %s", data)
                    return SearchPlan(
                        needs_search=needs_search,
                        provider=provider,
                        queries=queries,
                        prioritize_github=prioritize_github,
                        prioritize_documentation=prioritize_documentation,
                        information_recency=information_recency,
                        reasoning_explanation=reasoning
                    )
        except Exception as e:
            logger.warning("[SearchPlanner] Error al planificar búsqueda con el LLM: %s. Usando heurística.", e)
            
        return self._generate_heuristic_plan(query)

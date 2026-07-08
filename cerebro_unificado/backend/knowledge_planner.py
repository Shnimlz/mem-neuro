"""
knowledge_planner.py — Componente cognitivo de planificación de conocimiento (RAG).

Analiza el historial, la consulta y los recuerdos locales para determinar si la
memoria es suficiente o está desactualizada, y planifica una estrategia de
recuperación multi-fuente.
"""

from __future__ import annotations

import logging
import re
import json
import datetime
from typing import Any, List, Dict, Optional
import httpx

logger = logging.getLogger("cerebro.knowledge_planner")

class KnowledgePlan:
    """Estrategia planificada para la adquisición y consolidación de conocimiento."""
    
    def __init__(
        self,
        sufficient_in_memory: bool,
        strategy_explanation: str,
        sources: List[Dict[str, Any]],
        priority_types: List[str],
        recency_needed: str
    ):
        self.sufficient_in_memory = sufficient_in_memory
        self.strategy_explanation = strategy_explanation
        self.sources = sources  # Lista de dicts: [{"source_id": "...", "queries": [...]}]
        self.priority_types = priority_types  # ["documentation", "github", "news", "foro", "wikipedia"]
        self.recency_needed = recency_needed  # "fresh", "standard", "none"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sufficient_in_memory": self.sufficient_in_memory,
            "strategy_explanation": self.strategy_explanation,
            "sources": self.sources,
            "priority_types": self.priority_types,
            "recency_needed": self.recency_needed
        }


class KnowledgePlanner:
    """Planificador cognitivo que evalúa la suficiencia y actualidad del conocimiento."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.llm_url = config.get("llm", {}).get("server_url", "http://127.0.0.1:8080")
        self.default_provider = config.get("search", {}).get("provider", "bing")

    def _format_memories(self, memories: List[Dict[str, Any]]) -> str:
        """Formatea los recuerdos locales de forma descriptiva para el LLM."""
        if not memories:
            return "Ninguno (la memoria semántica no retornó coincidencias para esta consulta)."
        
        formatted = []
        for idx, m in enumerate(memories):
            created_val = m.get("created_at", 0)
            try:
                dt_str = datetime.datetime.fromtimestamp(created_val).strftime("%Y-%m-%d")
            except Exception:
                dt_str = "Desconocida"
                
            content = m.get("content", "").strip()
            # Limpiar etiquetas XML para no confundir al planificador
            content_clean = re.sub(r'<[^>]+>[\s\S]*?<\/[^>]+>', '', content).strip()
            content_snippet = content_clean[:350] + "..." if len(content_clean) > 350 else content_clean
            
            formatted.append(
                f"Recuerdo {idx+1} [Tipo: {m.get('type', 'CONOCIMIENTO')}, Fecha Registro: {dt_str}]:\n"
                f"{content_snippet}"
            )
        return "\n\n".join(formatted)

    def _generate_heuristic_plan(self, query: str, memories: List[Dict[str, Any]]) -> KnowledgePlan:
        """Genera un plan heurístico/reglas deterministas si falla el LLM."""
        query_lower = query.lower()
        
        # Si no hay recuerdos, o la similitud es baja
        has_good_memory = len(memories) > 0
        
        # Palabras que denotan necesidad de información en tiempo real
        fresh_words = ["hoy", "ayer", "noticias", "clima", "precio", "dolar", "bolsa", "futbol", "partido", "resultados", "reciente", "lanzamiento", "nvidia"]
        needs_fresh = any(x in query_lower for x in fresh_words)
        
        # Decidir suficiencia
        sufficient_in_memory = has_good_memory and not needs_fresh
        
        sources = []
        priority_types = []
        
        if not sufficient_in_memory:
            # Planificar fuentes externas
            prioritize_github = any(x in query_lower for x in ["github", "repo", "repositorio", "commit", "pr", "issue"])
            prioritize_documentation = any(x in query_lower for x in ["docs", "api", "reference", "manual", "tutorial", "guia", "libreria", "library", "framework"])
            
            source_queries = [query]
            
            if prioritize_github:
                sources.append({"source_id": "github", "queries": source_queries})
                priority_types.append("github")
            elif prioritize_documentation:
                sources.append({"source_id": "official_docs", "queries": source_queries})
                priority_types.append("documentation")
            elif needs_fresh:
                sources.append({"source_id": "news", "queries": source_queries})
                priority_types.append("news")
            else:
                sources.append({"source_id": "web_search", "queries": source_queries})
                priority_types.extend(["documentation", "wikipedia"])
                
        return KnowledgePlan(
            sufficient_in_memory=sufficient_in_memory,
            strategy_explanation="Estrategia determinada mediante reglas deterministas de respaldo.",
            sources=sources,
            priority_types=priority_types,
            recency_needed="fresh" if needs_fresh else "standard"
        )

    async def plan_knowledge(
        self,
        query: str,
        history: List[Dict[str, str]] = None,
        local_memories: List[Dict[str, Any]] = None
    ) -> KnowledgePlan:
        """Determina la estrategia cognitiva óptima de recuperación de conocimiento."""
        if not self.config.get("scraping", {}).get("enabled", True):
            return KnowledgePlan(
                sufficient_in_memory=True,
                strategy_explanation="Recuperación externa deshabilitada en la configuración global.",
                sources=[],
                priority_types=[],
                recency_needed="none"
            )
            
        memories = local_memories or []
        
        try:
            formatted_memories = self._format_memories(memories)
            
            prompt = (
                "Eres el Planificador de Conocimiento del Cerebro Unificado. Tu rol es decidir si la consulta del usuario "
                "puede responderse con los recuerdos de la memoria local o si es necesario adquirir conocimiento externo "
                "y cómo hacerlo.\n\n"
                f"Fecha actual del sistema: {datetime.date.today().strftime('%Y-%m-%d')}\n\n"
                f"Consulta del usuario: \"{query}\"\n\n"
                "Recuerdos locales recuperados de la memoria semántica:\n"
                f"{formatted_memories}\n\n"
            )
            
            if history:
                prompt += "Historial reciente del chat:\n"
                for msg in history[-3:]:
                    role = "Usuario" if msg.get("role") == "user" else "IA"
                    content = re.sub(r'<[^>]+>[\s\S]*?<\/[^>]+>', '', msg.get("content", "")).strip()
                    prompt += f"{role}: {content[:150]}\n"
                    
            prompt += (
                "\nAnaliza si los recuerdos son suficientes, precisos y actuales para responder la consulta.\n"
                "Responde ÚNICAMENTE con un JSON que cumpla este esquema exacto:\n"
                "{\n"
                "  \"sufficient_in_memory\": bool,\n"
                "  \"strategy_explanation\": \"breve justificación (ej. 'la memoria local contiene tauri v1 pero el usuario pregunta por v2, requiere buscar docs oficiales')\",\n"
                "  \"sources\": [\n"
                "    {\n"
                "      \"source_id\": \"web_search\" | \"github\" | \"official_docs\" | \"news\",\n"
                "      \"queries\": [\"consulta específica 1\", \"consulta específica 2\"]\n"
                "    }\n"
                "  ],\n"
                "  \"priority_types\": [\"documentation\", \"github\", \"news\", \"foro\", \"wikipedia\"],\n"
                "  \"recency_needed\": \"fresh\" | \"standard\" | \"none\"\n"
                "}\n"
                "No agregues explicaciones fuera del bloque JSON. Responde solo con el JSON."
            )

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{self.llm_url}/v1/chat/completions",
                    json={
                        "messages": [
                            {"role": "system", "content": "Eres un asistente experto en RAG que diseña estrategias cognitivas y planifica la adquisición de conocimiento."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 300,
                        "temperature": 0.0
                    }
                )
                
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"].strip()
                    if "</think>" in content:
                        content = content.split("</think>")[-1].strip()
                    content_clean = re.sub(r'```(?:json)?\s*([\s\S]*?)\s*```', r'\1', content).strip()
                    
                    data = json.loads(content_clean)
                    
                    sufficient = bool(data.get("sufficient_in_memory", False))
                    strategy = str(data.get("strategy_explanation", "Plan del modelo."))
                    sources = data.get("sources", [])
                    if not isinstance(sources, list):
                        sources = []
                        
                    # Validar e interpolar fuentes
                    cleaned_sources = []
                    for src in sources:
                        sid = str(src.get("source_id", "web_search")).lower()
                        if sid not in ["web_search", "github", "official_docs", "news"]:
                            sid = "web_search"
                        queries_raw = src.get("queries", [query])
                        queries = [q.strip() for q in queries_raw if q.strip()] if isinstance(queries_raw, list) else [query]
                        if queries:
                            cleaned_sources.append({"source_id": sid, "queries": queries})
                            
                    priority = data.get("priority_types", ["documentation"])
                    if not isinstance(priority, list):
                        priority = ["documentation"]
                        
                    recency = str(data.get("recency_needed", "standard")).lower()
                    if recency not in ["fresh", "standard", "none"]:
                        recency = "standard"
                        
                    logger.info("[KnowledgePlanner] Plan cognitivo generado por el LLM: %s", data)
                    return KnowledgePlan(
                        sufficient_in_memory=sufficient,
                        strategy_explanation=strategy,
                        sources=cleaned_sources,
                        priority_types=priority,
                        recency_needed=recency
                    )
        except Exception as e:
            logger.warning("[KnowledgePlanner] Error al planificar conocimiento con LLM: %s. Usando heurística.", e)
            
        return self._generate_heuristic_plan(query, memories)

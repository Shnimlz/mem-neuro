"""
classifier.py — Clasificador de intenciones híbrido.

Implementa el sistema de metacognición del Cerebro Autónomo Unificado
(Secciones 4 y 12 del Proyecto.md):

1. Pre-filtro rápido por palabras clave (latencia mínima)
2. Escalamiento al LLM (DeepSeek-R1) solo cuando el resultado es ambiguo
3. Fallback a 'consulta' si el LLM no responde o timeout
"""

from __future__ import annotations

import logging
import re
from enum import Enum

import httpx

logger = logging.getLogger("cerebro.classifier")


class Intention(str, Enum):
    """Categorías exclusivas de intención del usuario."""

    CONSULTA = "consulta"
    CORRECCION_ERROR = "corrección_de_error"
    INGESTA_WEB = "ingesta_web"


# ─── Palabras clave para el pre-filtro (Sección 12) ────────────────────────────

# Patrones claros de corrección de error
ERROR_KEYWORDS = [
    r"\bno\s+funcion[óa]\b",
    r"\bno\s+sirv[eió]\b",
    r"\berror\b",
    r"\bfal[ol]ó?\b",
    r"\bfallo\b",
    r"\brompi[óo]\b",
    r"\bse\s+rompió\b",
    r"\bno\s+compil[aó]\b",
    r"\bbug\b",
    r"\bcrash\b",
    r"\bexcep[ct]i[oó]n\b",
    r"\btraceback\b",
    r"\bstack\s*trace\b",
    r"\bsegfault\b",
    r"\bpanic\b",
    r"\beso\s+no\b",
    r"\bno\s+anda\b",
    r"\bsigue\s+fallando\b",
    r"\bsigue\s+sin\s+funcionar\b",
    r"\bno\s+resolvió\b",
]

# Patrones claros de ingesta web
WEB_KEYWORDS = [
    r"\bscrap[ea]\b",
    r"\bindex[ar]\b",
    r"\bingesta\b",
    r"\bimport(?:a|ar)\s+(?:de|desde)\s+(?:la\s+)?(?:web|url|página)\b",
    r"\blee\s+(?:esta|la)\s+(?:url|página|web)\b",
    r"\bhttps?://\S+",
    r"\bvs\b",
    r"\bquien\s+ganó\b|\bquién\s+ganó\b",
    r"\bresultado\b|\bmarcador\b",
    r"\bmundial\b|\bcopa\s+del\s+mundo\b",
    r"\bclima\b|\btiempo\s+actual\b",
    r"\bhora\s+en\b",
]

# Compilar regex una sola vez
_ERROR_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ERROR_KEYWORDS]
_WEB_PATTERNS = [re.compile(p, re.IGNORECASE) for p in WEB_KEYWORDS]

# ─── Prompt del sistema para clasificación LLM (Sección 4) ─────────────────────

CLASSIFY_SYSTEM_PROMPT = (
    "Clasifica el siguiente mensaje del usuario en una de estas categorías exclusivas:\n"
    "['consulta', 'corrección_de_error', 'ingesta_web'].\n"
    "Responde únicamente con la palabra de la categoría."
)


class IntentionClassifier:
    """Clasificador híbrido: pre-filtro por keywords → LLM → fallback."""

    def __init__(self, llm_url: str, timeout: float = 5.0) -> None:
        """
        Args:
            llm_url: URL base del servidor LLM (ej. http://127.0.0.1:8080).
            timeout: Segundos máximos para la llamada de clasificación al LLM.
        """
        self.llm_url = llm_url.rstrip("/")
        self.timeout = timeout

    def keyword_prefilter(self, message: str) -> Intention | None:
        """Primera pasada rápida por palabras clave.

        Returns:
            La intención si es clara, o None si es ambiguo y requiere LLM.
        """
        error_matches = sum(1 for p in _ERROR_PATTERNS if p.search(message))
        web_matches = sum(1 for p in _WEB_PATTERNS if p.search(message))

        # Si hay matches claros en una sola categoría
        if error_matches > 0 and web_matches == 0:
            logger.debug("Pre-filtro → corrección_de_error (%d matches)", error_matches)
            return Intention.CORRECCION_ERROR

        if web_matches > 0 and error_matches == 0:
            logger.debug("Pre-filtro → ingesta_web (%d matches)", web_matches)
            return Intention.INGESTA_WEB

        # Ambiguo o sin match → necesita LLM
        if error_matches == 0 and web_matches == 0:
            # Sin indicadores claros, probablemente consulta, pero dejamos al LLM decidir
            # a menos que sea muy genérico
            logger.debug("Pre-filtro → sin match, escalando a LLM")
            return None

        # Ambiguo (matches en ambas categorías)
        logger.debug(
            "Pre-filtro → ambiguo (error=%d, web=%d), escalando a LLM",
            error_matches,
            web_matches,
        )
        return None

    async def llm_classify(self, message: str) -> Intention:
        """Clasifica usando el LLM con timeout estricto.

        Returns:
            La intención clasificada, o CONSULTA si falla/timeout.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.llm_url}/v1/chat/completions",
                    json={
                        "messages": [
                            {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                            {"role": "user", "content": message},
                        ],
                        "max_tokens": 256,
                        "temperature": 0.0,
                    },
                )
                response.raise_for_status()

            data = response.json()
            raw = data["choices"][0]["message"]["content"].strip().lower()

            # Normalizar la respuesta del LLM
            for intention in Intention:
                if intention.value in raw:
                    logger.info("LLM clasificó → %s (raw: '%s')", intention.value, raw)
                    return intention

            # Respuesta fuera de las categorías válidas → fallback (Sección 12)
            logger.warning(
                "LLM respondió fuera de categorías válidas: '%s' → fallback a consulta",
                raw,
            )
            return Intention.CONSULTA

        except httpx.TimeoutException:
            logger.warning("Timeout en clasificación LLM (%.1fs) → fallback a consulta", self.timeout)
            return Intention.CONSULTA
        except Exception as exc:
            logger.warning("Error en clasificación LLM: %s → fallback a consulta", exc)
            return Intention.CONSULTA

    async def classify(self, message: str) -> Intention:
        """Orquestador principal: pre-filtro → LLM → fallback.

        Nunca bloquea la respuesta al usuario esperando una clasificación válida
        (Sección 12).
        """
        # Paso 1: Pre-filtro rápido
        result = self.keyword_prefilter(message)
        if result is not None:
            logger.info("Clasificación por pre-filtro: %s", result.value)
            return result

        # Paso 2: Escalar al LLM
        result = await self.llm_classify(message)
        logger.info("Clasificación final: %s", result.value)
        return result

"""
embeddings.py — Cliente de embeddings para el Cerebro Autónomo Unificado.

Conecta con la instancia dedicada de llama-server (puerto 8081)
y opcionalmente normaliza los vectores L2 para asegurar distancias
L2 consistentes que se mapean con la similitud de coseno.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx

logger = logging.getLogger("cerebro.embeddings")


class EmbeddingsClient:
    """Cliente asíncrono para consumir embeddings desde llama-server u OpenAI API."""

    def __init__(
        self,
        server_url: str,
        model: str = "bge-m3",
        dimension: int = 1024,
        normalize: bool = True,
        timeout: float = 5.0,
    ) -> None:
        """
        Args:
            server_url: URL base del servidor de embeddings (ej. http://127.0.0.1:8081).
            model: Identificador del modelo a enviar en el payload.
            dimension: Dimensión esperada del embedding.
            normalize: Si es True, fuerza la normalización L2 del vector en cliente.
            timeout: Tiempo máximo de espera en segundos.
        """
        self.server_url = server_url.rstrip("/")
        self.model = model
        self.dimension = dimension
        self.normalize = normalize
        self.timeout = timeout

    @staticmethod
    def l2_normalize(vector: list[float]) -> list[float]:
        """Aplica normalización L2 a un vector para que su magnitud sea 1.0."""
        squared_sum = sum(x * x for x in vector)
        magnitude = math.sqrt(squared_sum)
        if magnitude == 0:
            return vector
        return [x / magnitude for x in vector]

    async def get_embedding(self, text: str) -> list[float] | None:
        """Obtiene el vector de embeddings para el texto dado.

        Intenta primero usar el endpoint estándar /v1/embeddings de OpenAI.
        Si este falla o no está soportado, intenta el endpoint nativo /embeddings.

        Returns:
            Lista de floats que representa el vector, o None si ocurre un error/timeout.
        """
        # Limpiar texto de saltos de línea innecesarios
        clean_text = text.strip()
        if not clean_text:
            return None

        # Intentar endpoint estándar /v1/embeddings (OpenAI compatible)
        payload = {
            "model": self.model,
            "input": clean_text
        }

        urls_to_try = [
            f"{self.server_url}/v1/embeddings",
            f"{self.server_url}/embeddings"  # Endpoint nativo clásico de llama.cpp
        ]

        for url in urls_to_try:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.debug("Llamando a embeddings: %s con modelo %s", url, self.model)
                    response = await client.post(url, json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Extraer vector según la estructura de respuesta
                        vector = self._parse_response(data)
                        if vector:
                            if len(vector) != self.dimension:
                                logger.warning(
                                    "La dimensión del vector recibido (%d) no coincide con la configurada (%d)",
                                    len(vector),
                                    self.dimension,
                                )
                            
                            if self.normalize:
                                return self.l2_normalize(vector)
                            return vector
            except httpx.HTTPError as exc:
                logger.debug("Fallo al llamar a %s: %s", url, exc)
                continue
            except Exception as exc:
                logger.warning("Error inesperado procesando embeddings en %s: %s", url, exc)
                continue

        logger.error("No se pudo obtener embedding de %s tras probar todos los endpoints", self.server_url)
        return None

    def _parse_response(self, data: dict[str, Any]) -> list[float] | None:
        """Parsea la respuesta JSON de embeddings del servidor."""
        try:
            # 1. Estructura estándar OpenAI /v1/embeddings
            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                item = data["data"][0]
                if "embedding" in item:
                    return [float(x) for x in item["embedding"]]

            # 2. Estructura nativa llama.cpp /embeddings (anteriormente usaba {"embedding": [...]})
            if "embedding" in data and isinstance(data["embedding"], list):
                return [float(x) for x in data["embedding"]]

        except (KeyError, TypeError, ValueError) as exc:
            logger.error("Error al parsear JSON de respuesta de embeddings: %s", exc)

        return None

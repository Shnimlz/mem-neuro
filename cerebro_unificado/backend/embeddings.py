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

        Divide el texto en fragmentos de tamaño máximo aproximado de 1500 caracteres
        para prevenir desbordamiento de lote en llama-server, promedia los vectores de cada
        fragmento, y normaliza el resultado final.
        """
        clean_text = text.strip()
        if not clean_text:
            return None

        # Fragmentar texto
        chunks = self.chunk_text(clean_text, 1500)
        vectors = []
        for chunk in chunks:
            vector = await self._get_single_embedding(chunk)
            if vector:
                vectors.append(vector)

        if not vectors:
            return None

        if len(vectors) == 1:
            if self.normalize:
                return self.l2_normalize(vectors[0])
            return vectors[0]

        # Promediar vectores por dimensión
        dimension = len(vectors[0])
        averaged_vector = [0.0] * dimension
        for vec in vectors:
            for i in range(dimension):
                averaged_vector[i] += vec[i]

        if self.normalize:
            return self.l2_normalize(averaged_vector)
        else:
            num_vectors = len(vectors)
            return [val / num_vectors for val in averaged_vector]

    async def _get_single_embedding(self, text: str) -> list[float] | None:
        """Obtiene el vector de embeddings para un fragmento individual de texto."""
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
                        vector = self._parse_response(data)
                        if vector:
                            if len(vector) != self.dimension:
                                logger.warning(
                                    "La dimensión del vector recibido (%d) no coincide con la configurada (%d)",
                                    len(vector),
                                    self.dimension,
                                )
                            return vector
            except httpx.HTTPError as exc:
                logger.debug("Fallo al llamar a %s: %s", url, exc)
                continue
            except Exception as exc:
                logger.warning("Error inesperado procesando embeddings en %s: %s", url, exc)
                continue

        logger.error("No se pudo obtener embedding de %s tras probar todos los endpoints", self.server_url)
        return None

    @staticmethod
    def chunk_text(text: str, max_chars: int = 1500) -> list[str]:
        """Divide el texto utilizando un algoritmo divisor recursivo inteligente (estilo Open WebUI / LangChain)."""
        separators = ["\n\n", "\n", " ", ""]
        chunk_overlap = 200

        def split_text(txt: str, separator_idx: int) -> list[str]:
            if len(txt) <= max_chars:
                return [txt]

            if separator_idx >= len(separators):
                # Caso base: sin separadores, cortar directamente
                return [txt[i : i + max_chars] for i in range(0, len(txt), max_chars - chunk_overlap)]

            sep = separators[separator_idx]
            splits = list(txt) if sep == "" else txt.split(sep)

            final_chunks = []
            current_chunk: list[str] = []
            current_len = 0

            for part in splits:
                part_len = len(part)
                # Si agregar esta parte excede el tamaño máximo
                if current_len + part_len + (len(sep) if current_chunk else 0) > max_chars:
                    if part_len > max_chars:
                        # Si una sola parte excede el tamaño máximo, dividirla recursivamente
                        if current_chunk:
                            final_chunks.append(sep.join(current_chunk))
                            current_chunk = []
                            current_len = 0
                        recursive_splits = split_text(part, separator_idx + 1)
                        final_chunks.extend(recursive_splits[:-1])
                        current_chunk = [recursive_splits[-1]]
                        current_len = len(recursive_splits[-1])
                    else:
                        # Guardar el chunk actual y comenzar uno nuevo
                        if current_chunk:
                            final_chunks.append(sep.join(current_chunk))
                        current_chunk = [part]
                        current_len = part_len
                else:
                    current_chunk.append(part)
                    current_len += part_len + (len(sep) if len(current_chunk) > 1 else 0)

            if current_chunk:
                final_chunks.append(sep.join(current_chunk))

            return final_chunks

        return split_text(text, 0)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 3,
        external_reranker_url: str | None = None
    ) -> list[str]:
        """Reordena una lista de documentos/fragmentos por relevancia respecto a una consulta.
        
        Intenta primero usar un servidor de reranking externo compatible (si se proporciona URL).
        Como fallback asíncrono y resiliente, calcula la similitud de coseno
        utilizando los embeddings de EmbeddingsClient.
        """
        if documents is None or not isinstance(documents, list) or not documents:
            return []
            
        # 1. Intentar Reranker Externo si está configurado
        if external_reranker_url:
            try:
                payload = {
                    "model": "reranker",
                    "query": query,
                    "documents": documents,
                    "top_n": top_n
                }
                async with httpx.AsyncClient(timeout=4.0) as client:
                    response = await client.post(external_reranker_url, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get("results", [])
                        results = sorted(results, key=lambda x: x.get("relevance_score", 0.0), reverse=True)
                        reranked_docs = []
                        for res in results[:top_n]:
                            idx = res.get("index")
                            if idx is not None and 0 <= idx < len(documents):
                                reranked_docs.append(documents[idx])
                        if reranked_docs:
                            logger.info("[Reranker] Ordenación completada usando reordenador externo.")
                            return reranked_docs
            except Exception as exc:
                logger.warning("[Reranker] Fallo en Reranker externo (%s). Usando fallback de embeddings...", exc)

            # 2. Fallback: Similitud de coseno basada en embeddings bi-encoder
            import asyncio
            try:
                logger.info("[Reranker] Ejecutando reordenamiento semántico por embeddings en paralelo...")
                query_vector = await self.get_embedding(query)
                if not query_vector:
                    logger.warning("[Reranker] No se pudo obtener el embedding de la query. Retornando orden original.")
                    return documents[:top_n]
                    
                # Lanzar todas las peticiones de embeddings en paralelo
                tasks = [self.get_embedding(doc) for doc in documents]
                doc_vectors = await asyncio.gather(*tasks)
                
                scored_docs = []
                for doc, doc_vector in zip(documents, doc_vectors):
                    if doc_vector:
                        # Similitud coseno (al estar normalizados L2, es solo el producto escalar)
                        score = sum(q * d for q, d in zip(query_vector, doc_vector))
                        scored_docs.append((score, doc))
                    else:
                        scored_docs.append((0.0, doc))
                        
                scored_docs.sort(key=lambda x: x[0], reverse=True)
                logger.info("[Reranker] Reordenamiento por embeddings completado.")
                return [doc for _, doc in scored_docs[:top_n]]
                
            except Exception as exc:
                logger.error("[Reranker] Error en fallback de embeddings: %s. Retornando orden original.", exc)
                return documents[:top_n]

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

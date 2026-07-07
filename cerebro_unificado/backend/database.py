"""
database.py — Capa de acceso a datos para el Cerebro Autónomo Unificado.

Gestiona todas las operaciones sobre SQLite:
- Tablas: nodes, edges, nodes_fts (FTS5), vec_embeddings (sqlite-vec)
- Modo WAL para concurrencia segura (Sección 10)
- Búsqueda semántica vectorial nativa (Sección 9)
- Búsqueda full-text como fallback semántico (Sección 7)
- Mecanismo de Split/Bifurcación (Sección 3)
"""

from __future__ import annotations

import logging
import uuid
import time
import asyncio
from pathlib import Path
from typing import Any

import aiosqlite
import sqlite_vec

logger = logging.getLogger("cerebro.database")

# ─── Esquema SQL ────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Pragmas de concurrencia (Sección 10)
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

-- Tabla principal de neuronas (Sección 2)
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    session_id TEXT,
    content TEXT,
    type TEXT DEFAULT 'CONOCIMIENTO',
    created_at INTEGER,
    FOREIGN KEY(parent_id) REFERENCES nodes(id)
);

-- Tabla de sinapsis (Sección 2)
CREATE TABLE IF NOT EXISTS edges (
    source_id TEXT,
    target_id TEXT,
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (source_id, target_id),
    FOREIGN KEY(source_id) REFERENCES nodes(id),
    FOREIGN KEY(target_id) REFERENCES nodes(id)
);

-- Tabla de caché web para Scraping (Sección 5)
CREATE TABLE IF NOT EXISTS web_cache (
    url TEXT PRIMARY KEY,
    content TEXT,
    created_at INTEGER
);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_nodes_session ON nodes(session_id);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_web_cache_url ON web_cache(url);
"""

FTS_SCHEMA_SQL = """
-- Tabla virtual FTS5 para búsqueda de texto (Sección 7 — fallback semántico)
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    id UNINDEXED,
    content,
    tokenize='unicode61'
);
"""

# Peso prioritario para aristas de bifurcación (Sección 3)
SPLIT_EDGE_WEIGHT = 10.0


class Database:
    """Gestiona la conexión y operaciones sobre storage/brain.db."""

    def __init__(self, db_path: str | Path, embedding_dim: int = 1024) -> None:
        self.db_path = Path(db_path)
        self.embedding_dim = embedding_dim
        self._conn: aiosqlite.Connection | None = None

    # ─── Ciclo de vida ──────────────────────────────────────────────────

    async def connect(self) -> None:
        """Abre la conexión y crea el esquema si no existe."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row

        # Habilitar carga de extensiones y cargar sqlite-vec dinámicamente
        try:
            await self._conn.enable_load_extension(True)
            # Cargar sqlite-vec
            vec_path = sqlite_vec.loadable_path()
            await self._conn.execute("SELECT load_extension(?)", (vec_path,))
            logger.info("Extensión sqlite-vec cargada correctamente desde %s", vec_path)
        except Exception as exc:
            logger.error("No se pudo cargar la extensión sqlite-vec: %s. La búsqueda vectorial no estará disponible.", exc)

        # Ejecutar pragmas y esquema principal
        await self._conn.executescript(SCHEMA_SQL)

        # FTS5
        try:
            await self._conn.executescript(FTS_SCHEMA_SQL)
        except Exception:
            # La tabla ya existe
            pass

        # Crear tabla virtual vec_embeddings (Sección 2)
        # La tabla utiliza rowid de 64 bits implícito mapeado al rowid de nodes
        try:
            await self._conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0("
                f"  rowid INTEGER PRIMARY KEY,"
                f"  embedding float[{self.embedding_dim}]"
                f");"
            )
            logger.info("Tabla vec_embeddings (dimensión=%d) inicializada", self.embedding_dim)
        except Exception as exc:
            logger.error("Fallo al crear la tabla virtual vec_embeddings: %s", exc)

        await self._conn.commit()
        logger.info("Base de datos inicializada: %s (WAL mode)", self.db_path)

    async def close(self) -> None:
        """Cierra la conexión limpiamente."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Conexión a la base de datos cerrada")

    async def reset_database(self) -> None:
        """Cierra la conexión actual, elimina los archivos físicos de la base de datos y la reinicializa."""
        logger.info("Iniciando el reinicio completo de la base de datos...")
        await self.close()

        # Intentar borrar los archivos físicos de brain.db, brain.db-wal, y brain.db-shm
        db_files = [
            self.db_path,
            self.db_path.with_name(f"{self.db_path.name}-wal"),
            self.db_path.with_name(f"{self.db_path.name}-shm")
        ]

        for file in db_files:
            try:
                if file.exists():
                    file.unlink()
                    logger.info("Archivo de base de datos eliminado: %s", file)
            except Exception as exc:
                logger.error("No se pudo eliminar el archivo %s: %s", file, exc)

        # Reinicializar la conexión y las tablas
        await self.connect()

        # Ejecutar VACUUM
        try:
            await self.conn.execute("VACUUM")
            await self.conn.commit()
            logger.info("VACUUM completado con éxito.")
        except Exception as exc:
            logger.warning("Fallo al ejecutar VACUUM: %s", exc)

        logger.info("Base de datos reiniciada e inicializada con éxito.")

    @property
    def conn(self) -> aiosqlite.Connection:
        """Acceso seguro a la conexión activa."""
        if self._conn is None:
            raise RuntimeError("La base de datos no está conectada. Llama a connect() primero.")
        return self._conn

    # ─── Nodos ──────────────────────────────────────────────────────────

    async def insert_node(
        self,
        content: str,
        session_id: str,
        parent_id: str | None = None,
        node_type: str = "CONOCIMIENTO",
        node_id: str | None = None,
        embedding: list[float] | None = None,
    ) -> dict[str, Any]:
        """Inserta un nuevo nodo cognitivo.

        Opcionalmente inserta su embedding asociado en vec_embeddings.

        Returns:
            Diccionario con los datos del nodo creado.
        """
        nid = node_id or str(uuid.uuid4())
        now = int(time.time())

        # Insertar en nodes y capturar el rowid generado automáticamente
        cursor = await self.conn.execute(
            "INSERT INTO nodes (id, parent_id, session_id, content, type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (nid, parent_id, session_id, content, node_type, now),
        )
        rowid = cursor.lastrowid

        # Sincronizar con FTS5
        await self.conn.execute(
            "INSERT INTO nodes_fts (id, content) VALUES (?, ?)",
            (nid, content),
        )

        # Sincronizar con vec_embeddings si se proporciona
        if embedding is not None and rowid is not None:
            try:
                await self.conn.execute(
                    "INSERT INTO vec_embeddings (rowid, embedding) VALUES (?, ?)",
                    (rowid, str(embedding)),
                )
                logger.debug("Embedding guardado para nodo %s (rowid=%d)", nid[:8], rowid)
            except Exception as exc:
                logger.error("Fallo al guardar embedding en la base de datos para nodo %s: %s", nid[:8], exc)

        await self.conn.commit()

        node = {
            "id": nid,
            "parent_id": parent_id,
            "session_id": session_id,
            "content": content,
            "type": node_type,
            "created_at": now,
        }
        logger.info("Nodo creado: %s [%s] sesión=%s", nid[:8], node_type, session_id)
        return node

    async def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Obtiene un nodo por su ID."""
        cursor = await self.conn.execute(
            "SELECT id, parent_id, session_id, content, type, created_at "
            "FROM nodes WHERE id = ?",
            (node_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def get_children(self, parent_id: str) -> list[dict[str, Any]]:
        """Obtiene todos los nodos hijos de un padre."""
        cursor = await self.conn.execute(
            "SELECT id, parent_id, session_id, content, type, created_at "
            "FROM nodes WHERE parent_id = ? ORDER BY created_at",
            (parent_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_session_nodes(self, session_id: str) -> list[dict[str, Any]]:
        """Obtiene todos los nodos de una sesión, ordenados cronológicamente."""
        cursor = await self.conn.execute(
            "SELECT id, parent_id, session_id, content, type, created_at "
            "FROM nodes WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_last_node_in_session(self, session_id: str) -> dict[str, Any] | None:
        """Obtiene el último nodo de una sesión (para el mecanismo de Split)."""
        cursor = await self.conn.execute(
            "SELECT id, parent_id, session_id, content, type, created_at "
            "FROM nodes WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def update_node_type(self, node_id: str, new_type: str) -> dict[str, Any] | None:
        """Actualiza el tipo de un nodo (para el endpoint PATCH, Sección 13)."""
        await self.conn.execute(
            "UPDATE nodes SET type = ? WHERE id = ?",
            (new_type, node_id),
        )
        await self.conn.commit()
        node = await self.get_node(node_id)
        if node:
            logger.info("Nodo %s actualizado a tipo: %s", node_id[:8], new_type)
        return node

    # ─── Aristas ────────────────────────────────────────────────────────

    async def insert_edge(
        self, source_id: str, target_id: str, weight: float = 1.0
    ) -> dict[str, Any]:
        """Inserta una arista entre dos nodos."""
        await self.conn.execute(
            "INSERT OR REPLACE INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)",
            (source_id, target_id, weight),
        )
        await self.conn.commit()
        edge = {"source_id": source_id, "target_id": target_id, "weight": weight}
        logger.info("Arista creada: %s → %s (peso=%.1f)", source_id[:8], target_id[:8], weight)
        return edge

    async def delete_edge(self, source_id: str, target_id: str) -> bool:
        """Elimina una arista (para el endpoint DELETE, Sección 13)."""
        cursor = await self.conn.execute(
            "DELETE FROM edges WHERE source_id = ? AND target_id = ?",
            (source_id, target_id),
        )
        await self.conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Arista eliminada: %s → %s", source_id[:8], target_id[:8])
        return deleted

    async def get_edges_for_node(self, node_id: str) -> list[dict[str, Any]]:
        """Obtiene todas las aristas conectadas a un nodo (entrantes y salientes)."""
        cursor = await self.conn.execute(
            "SELECT source_id, target_id, weight FROM edges "
            "WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ─── Búsqueda Semántica Vectorial con Fallback FTS5 ────────────────

    async def search_semantic(
        self,
        query_text: str,
        query_embedding: list[float] | None = None,
        similarity_threshold: float = 0.40,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Realiza búsqueda semántica nativa (vectorial) usando vec_embeddings.

        Filtra los resultados que superen el threshold de similitud.
        Si query_embedding es None, o si ocurre un fallo al buscar vectorialmente,
        conmuta automáticamente a búsqueda clásica por texto (FTS5) (Sección 7).

        La distancia máxima L2 al cuadrado para un threshold de similitud coseno S es:
        D2 = 2.0 - (2.0 * S) (Asumiendo vectores normalizados).
        """
        # Si no hay embedding de consulta, usar directamente FTS5
        if query_embedding is None:
            logger.info("Búsqueda vectorial no disponible (sin query_embedding), conmutando a FTS5")
            return await self.search_fts(query_text, limit)

        # Convertir threshold de similitud coseno a distancia L2 máxima permitida
        # S >= threshold  ===>  2.0 - 2.0*S <= 2.0 - 2.0*threshold
        max_distance = 2.0 - (2.0 * similarity_threshold)

        try:
            # Consulta KNN sobre vec_embeddings uniendo con nodes a través de rowid
            cursor = await self.conn.execute(
                """
                SELECT 
                    n.id, 
                    n.parent_id, 
                    n.session_id, 
                    n.content, 
                    n.type, 
                    n.created_at, 
                    v.distance
                FROM vec_embeddings v
                JOIN nodes n ON v.rowid = n.rowid
                WHERE v.embedding MATCH ? 
                  AND v.distance <= ?
                  AND k = ?
                ORDER BY v.distance ASC
                """,
                (str(query_embedding), max_distance, limit),
            )
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                node = dict(row)
                # Intercepción de errores aprendidos → redirigir a fix (Sección 3)
                if node.get("type") == "ERROR_APRENDIDO":
                    fix_node = await self._find_fix_for_error(node["id"])
                    if fix_node:
                        logger.info(
                            "Redirigiendo ERROR_APRENDIDO %s → BIFURCACION_FIX %s (distancia: %.4f)",
                            node["id"][:8],
                            fix_node["id"][:8],
                            node["distance"],
                        )
                        # Preservar la metadata de distancia en el nodo redirigido
                        fix_node["distance"] = node["distance"]
                        node = fix_node

                results.append(node)

            logger.info(
                "Búsqueda vectorial completada: %d resultados bajo threshold %s (distancia max: %.3f)",
                len(results),
                similarity_threshold,
                max_distance,
            )
            return results

        except Exception as exc:
            logger.warning(
                "Búsqueda vectorial falló: %s. Conmutando automáticamente a fallback FTS5 (Sección 7)",
                exc,
            )
            return await self.search_fts(query_text, limit)

    async def search_fts(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Búsqueda full-text sobre el contenido de los nodos como fallback semántico."""
        # Escapar caracteres especiales de FTS5
        safe_query = query.replace('"', '""')

        try:
            cursor = await self.conn.execute(
                "SELECT f.id, n.parent_id, n.session_id, n.content, n.type, n.created_at, "
                "       rank "
                "FROM nodes_fts f "
                "JOIN nodes n ON f.id = n.id "
                "WHERE nodes_fts MATCH ? "
                "ORDER BY rank "
                "LIMIT ?",
                (f'"{safe_query}"', limit),
            )
            rows = await cursor.fetchall()
        except Exception:
            # Si la query FTS falla (caracteres especiales, etc.), intentar búsqueda LIKE
            logger.warning("FTS5 falló para query '%s', usando LIKE como respaldo", query[:50])
            cursor = await self.conn.execute(
                "SELECT id, parent_id, session_id, content, type, created_at "
                "FROM nodes WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", limit),
            )
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            node = dict(row)

            # Intercepción de errores aprendidos → redirigir a fix (Sección 3)
            if node.get("type") == "ERROR_APRENDIDO":
                fix_node = await self._find_fix_for_error(node["id"])
                if fix_node:
                    logger.info(
                        "Redirigiendo ERROR_APRENDIDO %s → BIFURCACION_FIX %s",
                        node["id"][:8],
                        fix_node["id"][:8],
                    )
                    node = fix_node

            results.append(node)

        return results

    async def _find_fix_for_error(self, error_node_id: str) -> dict[str, Any] | None:
        """Busca el nodo BIFURCACION_FIX conectado a un ERROR_APRENDIDO con mayor peso."""
        cursor = await self.conn.execute(
            "SELECT n.id, n.parent_id, n.session_id, n.content, n.type, n.created_at "
            "FROM edges e "
            "JOIN nodes n ON e.target_id = n.id "
            "WHERE e.source_id = ? AND n.type = 'BIFURCACION_FIX' "
            "ORDER BY e.weight DESC LIMIT 1",
            (error_node_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # ─── Mecanismo de Split/Bifurcación (Sección 3) ────────────────────

    async def split_node(
        self,
        error_node_id: str,
        fix_content: str,
        session_id: str,
        fix_embedding: list[float] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Ejecuta el mecanismo de bifurcación ante errores.

        1. Muta el nodo original a ERROR_APRENDIDO.
        2. Crea un nodo hijo BIFURCACION_FIX con la corrección y su embedding.
        3. Crea una arista con peso prioritario entre ambos.

        Returns:
            Tupla (nodo_error_actualizado, nodo_fix, arista).
        """
        # 1. Mutar el nodo original
        await self.conn.execute(
            "UPDATE nodes SET type = 'ERROR_APRENDIDO' WHERE id = ?",
            (error_node_id,),
        )

        # 2. Crear el nodo de corrección
        fix_id = str(uuid.uuid4())
        now = int(time.time())
        cursor = await self.conn.execute(
            "INSERT INTO nodes (id, parent_id, session_id, content, type, created_at) "
            "VALUES (?, ?, ?, ?, 'BIFURCACION_FIX', ?)",
            (fix_id, error_node_id, session_id, fix_content, now),
        )
        rowid = cursor.lastrowid

        # Sincronizar FTS5
        await self.conn.execute(
            "INSERT INTO nodes_fts (id, content) VALUES (?, ?)",
            (fix_id, fix_content),
        )

        # Sincronizar vec_embeddings si se proporciona
        if fix_embedding is not None and rowid is not None:
            try:
                await self.conn.execute(
                    "INSERT INTO vec_embeddings (rowid, embedding) VALUES (?, ?)",
                    (rowid, str(fix_embedding)),
                )
                logger.debug("Embedding guardado para nodo bifurcación %s (rowid=%d)", fix_id[:8], rowid)
            except Exception as exc:
                logger.error("Fallo al guardar embedding para bifurcación %s: %s", fix_id[:8], exc)

        # 3. Crear arista con peso prioritario
        await self.conn.execute(
            "INSERT OR REPLACE INTO edges (source_id, target_id, weight) VALUES (?, ?, ?)",
            (error_node_id, fix_id, SPLIT_EDGE_WEIGHT),
        )

        await self.conn.commit()

        error_node = await self.get_node(error_node_id)
        fix_node = await self.get_node(fix_id)
        edge = {
            "source_id": error_node_id,
            "target_id": fix_id,
            "weight": SPLIT_EDGE_WEIGHT,
        }

        logger.info(
            "Split ejecutado: %s (ERROR_APRENDIDO) → %s (BIFURCACION_FIX) peso=%.1f",
            error_node_id[:8],
            fix_id[:8],
            SPLIT_EDGE_WEIGHT,
        )

        return error_node, fix_node, edge  # type: ignore[return-value]

    # ─── Grafo completo ────────────────────────────────────────────────

    async def get_graph(self) -> dict[str, Any]:
        """Devuelve toda la estructura del grafo para el visualizador (GET /graph)."""
        nodes_cursor = await self.conn.execute(
            "SELECT id, parent_id, session_id, content, type, created_at "
            "FROM nodes ORDER BY created_at"
        )
        nodes = [dict(r) for r in await nodes_cursor.fetchall()]

        edges_cursor = await self.conn.execute(
            "SELECT source_id, target_id, weight FROM edges"
        )
        edges = [dict(r) for r in await edges_cursor.fetchall()]

        return {"nodes": nodes, "edges": edges}

    # ─── Estadísticas ──────────────────────────────────────────────────

    async def get_stats(self) -> dict[str, int]:
        """Devuelve estadísticas básicas de la base de datos."""
        nodes_cursor = await self.conn.execute("SELECT COUNT(*) FROM nodes")
        nodes_count = (await nodes_cursor.fetchone())[0]

        edges_cursor = await self.conn.execute("SELECT COUNT(*) FROM edges")
        edges_count = (await edges_cursor.fetchone())[0]

        return {"nodes": nodes_count, "edges": edges_count}

    # ─── Caché de Ingesta Web (Sección 5) ──────────────────────────────

    async def get_cached_url(self, url: str, ttl_seconds: int) -> str | None:
        """Busca en caché si la URL ya fue raspada y sigue siendo válida.

        Returns:
            Contenido HTML/texto raspado, o None si no existe o expiró.
        """
        now = int(time.time())
        min_timestamp = now - ttl_seconds

        cursor = await self.conn.execute(
            "SELECT content FROM web_cache WHERE url = ? AND created_at >= ?",
            (url, min_timestamp),
        )
        row = await cursor.fetchone()
        if row:
            logger.info("Lectura de caché web exitosa para URL: %s", url)
            return row[0]
        return None

    async def save_cached_url(self, url: str, content: str) -> None:
        """Guarda o actualiza el contenido de una URL en caché con el timestamp actual."""
        now = int(time.time())
        await self.conn.execute(
            "INSERT OR REPLACE INTO web_cache (url, content, created_at) VALUES (?, ?, ?)",
            (url, content, now),
        )
        await self.conn.commit()
        logger.info("URL guardada en caché: %s (tamaño: %d caracteres)", url, len(content))

    # ─── Respaldo y Poda (Sección 11) ─────────────────────────────────

    async def backup_database(self, keep_last: int) -> Path | None:
        """Realiza una copia de seguridad consistente en caliente usando el API backup de sqlite.
        
        Rota las copias de seguridad viejas manteniendo solo 'keep_last' archivos en storage/backups/.
        """
        import sqlite3
        import glob
        import os

        # Determinar rutas
        backups_dir = self.db_path.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_file = backups_dir / f"brain-{timestamp}.db"

        logger.info("Iniciando copia de seguridad en caliente de la base de datos a: %s", backup_file)
        
        try:
            # Función síncrona ejecutada en un thread pool para no bloquear el loop de FastAPI
            def _do_backup(src_path: Path, dst_path: Path):
                src_conn = sqlite3.connect(str(src_path))
                dst_conn = sqlite3.connect(str(dst_path))
                with dst_conn:
                    src_conn.backup(dst_conn)
                src_conn.close()
                dst_conn.close()

            await asyncio.to_thread(_do_backup, self.db_path, backup_file)
            logger.info("Copia de seguridad completada con éxito.")

            # Rotación de copias viejas
            backup_pattern = str(backups_dir / "brain-*.db")
            all_backups = sorted(glob.glob(backup_pattern), key=os.path.getmtime)
            
            if len(all_backups) > keep_last:
                to_delete = all_backups[:-keep_last]
                for file_path in to_delete:
                    try:
                        os.remove(file_path)
                        logger.info("Copia de seguridad antigua eliminada por rotación: %s", file_path)
                    except Exception as exc:
                        logger.warning("No se pudo eliminar copia antigua %s: %s", file_path, exc)
            
            return backup_file
        except Exception as exc:
            logger.error("Error al realizar copia de seguridad: %s", exc)
            return None

    async def consolidate_and_prune(
        self, older_than_seconds: int, embedding_client: Any = None
    ) -> dict[str, Any] | None:
        """Identifica recuerdos antiguos de tipo CONOCIMIENTO con baja centralidad y los consolida.
        
        Nodos que no tienen aristas entrantes en la tabla edges son agrupados y eliminados.
        Los nodos tipo ERROR_APRENDIDO y BIFURCACION_FIX están protegidos al 100%.
        """
        now = int(time.time())
        max_timestamp = now - older_than_seconds

        logger.info(
            "Iniciando tarea de poda y consolidación de recuerdos de CONOCIMIENTO antiguos (creados antes de %s)",
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(max_timestamp))
        )

        # 1. Encontrar nodos de tipo CONOCIMIENTO antiguos que no tienen aristas que apunten a ellos (baja centralidad/acceso)
        query_candidates = """
            SELECT id, content, created_at 
            FROM nodes 
            WHERE type = 'CONOCIMIENTO' 
              AND created_at < ? 
              AND id NOT IN (SELECT target_id FROM edges)
        """
        cursor = await self.conn.execute(query_candidates, (max_timestamp,))
        candidates = [dict(r) for r in await cursor.fetchall()]

        if not candidates:
            logger.info("No se encontraron recuerdos de CONOCIMIENTO antiguos para podar.")
            return None

        logger.info("Encontrados %d recuerdos candidatos para poda. Iniciando consolidación...", len(candidates))

        # 2. Generar el contenido agrupado
        lines = []
        for i, c in enumerate(candidates, 1):
            date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(c["created_at"]))
            lines.append(f"--- Recuerdo Antiguo {i} ({date_str}) ---\n{c['content']}")
            
        date_now = time.strftime("%Y-%m-%d %H:%M:%S")
        consolidated_content = (
            f"Consolidación de recuerdos antiguos ({date_now}):\n\n"
            f"Esta neurona consolida información histórica para optimizar el grafo de conocimientos:\n\n"
            + "\n\n".join(lines)
        )

        # Truncar si supera un límite seguro
        if len(consolidated_content) > 10000:
            consolidated_content = consolidated_content[:10000] + "\n... [Contenido de consolidación truncado]"

        # 3. Vectorizar el nodo consolidado
        embedding = None
        if embedding_client:
            try:
                embedding = await embedding_client.get_embedding(consolidated_content)
            except Exception as exc:
                logger.warning("No se pudo obtener embedding para el nodo consolidado: %s", exc)

        # 4. Insertar el nuevo nodo de consolidación
        consolidated_node = await self.insert_node(
            content=consolidated_content,
            session_id="consolidated",
            parent_id=None,
            node_type="CONOCIMIENTO",
            embedding=embedding
        )

        # 5. Eliminar los candidatos de la base de datos
        candidate_ids = [c["id"] for c in candidates]
        
        # Eliminar las aristas salientes asociadas
        placeholders = ",".join("?" for _ in candidate_ids)
        await self.conn.execute(
            f"DELETE FROM edges WHERE source_id IN ({placeholders})", candidate_ids
        )
        
        # Eliminar los registros de embeddings vectoriales asociados a través del rowid
        await self.conn.execute(
            f"DELETE FROM vec_embeddings WHERE rowid IN (SELECT rowid FROM nodes WHERE id IN ({placeholders}))",
            candidate_ids
        )

        # Eliminar del FTS5
        await self.conn.execute(
            f"DELETE FROM nodes_fts WHERE id IN ({placeholders})", candidate_ids
        )

        # Eliminar de la tabla nodes principal
        await self.conn.execute(
            f"DELETE FROM nodes WHERE id IN ({placeholders})", candidate_ids
        )

        await self.conn.commit()

        logger.info(
            "Consolidación exitosa. Se eliminaron %d nodos antiguos e insertó el nodo consolidado %s",
            len(candidates),
            consolidated_node["id"][:8]
        )

        return {
            "deleted_nodes_count": len(candidates),
            "new_node": consolidated_node
        }



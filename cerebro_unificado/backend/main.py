"""
main.py — API FastAPI, Proxy Interceptor Activo y orquestador del ciclo de pensamiento.

Servidor principal del Cerebro Autónomo Unificado (Sección 1).
Expone los endpoints HTTP y WebSocket, realiza copias de seguridad/poda autónoma (Sección 11),
e intercepta peticiones conversacionales a través de un Proxy Activo para conectar
cualquier cliente de chat o la interfaz web oficial de llama.cpp (Sección 9 y 14) al grafo,
actuando opcionalmente como Agente de Ejecución de Comandos locales (Tool Use).

Ejecutar: python main.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
import re
import json
import time
import platform
import urllib.parse
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import yaml
import uvicorn
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, FileResponse
from pydantic import BaseModel, Field

from database import Database
from classifier import IntentionClassifier, Intention
from embeddings import EmbeddingsClient
from web_scraper import WebScraper

# ─── Configuración ──────────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
BASE_DIR = Path(__file__).resolve().parent.parent

# Regex para detectar URLs
URL_REGEX = re.compile(r"https?://[^\s\"']+")

# ─── Plantilla base del System Prompt con tags dinámicos ────────────────────────

_uname = platform.uname()
_OS_VERSION_CACHED = f"{_uname.system} {_uname.release} ({_uname.node})"

SYSTEM_PROMPT_TEMPLATE = (
    "[SYSTEM DIRECTIVE: COGNITIVE IDENTITY & TOOL SELECTION]\n"
    "You are the Unified Cognitive Brain of {{user}}. Your identity, personality, and name are not predefined; "
    "they adapt dynamically based on the local context memory nodes {{user}} provides. "
    "If context memories specify your name or relationship with {{user}}, assume it fully and act accordingly.\n"
    "CURRENT TIMESTAMP: {{current_time}}.\n"
    "HOST SYSTEM: {{os_version}}.\n"
    "LANGUAGE RULE: You MUST speak and write your response to {{user}} strictly in {{target_lang}}.\n\n"
    "AVAILABLE TOOLS (STRICT SELECTION RULES):\n\n"
    "TOOL 1 — ejecutar_busqueda_web:\n"
    "  USE FOR: Any question about current events, news, sports, weather, dates, people, places, "
    "prices, releases, updates, or ANY factual information from the year 2024-2026. "
    "Also use for any question where you are unsure of the answer or lack internal knowledge.\n"
    "  FORMAT: Output a JSON block: {\"name\": \"ejecutar_busqueda_web\", \"arguments\": {\"query\": \"search keywords\"}}\n"
    "  NEVER USE: Terminal commands (curl, wget, etc.) as a substitute for this tool.\n\n"
    "SYSTEM TASK RESTRICTIONS:\n"
    "- You are STRICTLY FORBIDDEN from executing terminal/bash commands, running scripts, or interacting with the operating system.\n"
    "- If the user asks you to perform system tasks, administration, run commands, check disk space, start/stop services, "
    "or write scripts to be executed on their local Linux machine, you MUST NOT execute them. "
    "Instead, you must write detailed, instructional Markdown text explaining to the user how they can manually execute the tasks themselves.\n\n"
    "DECISION RULE: If the user asks any fact, current event, search query, or information question → use ejecutar_busqueda_web."
)


def render_system_prompt(target_lang: str = "Spanish (Español)", user: str = "Antonio") -> str:
    """Resuelve los tags dinámicos de SYSTEM_PROMPT_TEMPLATE en tiempo de ejecución."""
    now = datetime.now()
    _DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    _MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
              "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    hora_12 = now.hour % 12 or 12
    ampm = "AM" if now.hour < 12 else "PM"
    timestamp_es = (
        f"{_DIAS[now.weekday()]}, {now.day} de {_MESES[now.month - 1]} "
        f"de {now.year} a las {hora_12}:{now.minute:02d} {ampm}"
    )
    return (
        SYSTEM_PROMPT_TEMPLATE
        .replace("{{user}}", user)
        .replace("{{current_time}}", timestamp_es)
        .replace("{{os_version}}", _OS_VERSION_CACHED)
        .replace("{{target_lang}}", target_lang)
    )

def extract_commands(text: str) -> list[str]:
    """Extrae comandos localizados en la respuesta de forma ultra robusta y a prueba de markdown.
    [DESHABILITADO] Retorna siempre una lista vacía para evitar ejecución de comandos de terminal.
    """
    return []


def load_config() -> dict:
    """Carga la configuración desde config.yaml (Sección 6)."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ─── Logging (Sección 7) ────────────────────────────────────────────────────────

def setup_logging(config: dict) -> None:
    """Configura el logging a storage/cerebro.log y consola."""
    log_path = BASE_DIR / "storage" / "cerebro.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Formato detallado para trazabilidad de errores
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de archivo
    file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Handler de consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Logger raíz del cerebro
    root_logger = logging.getLogger("cerebro")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Silenciar loggers verbosos de dependencias
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


logger = logging.getLogger("cerebro.main")

# ─── Estado global ──────────────────────────────────────────────────────────────

config: dict = {}
db: Database | None = None
classifier: IntentionClassifier | None = None
embeddings_client: EmbeddingsClient | None = None
web_scraper: WebScraper | None = None

# Conexiones WebSocket activas (Sección 13)
ws_connections: set[WebSocket] = set()

# Control de actividad de usuario para evitar colisiones del LLM local
last_user_activity_time: float = 0.0


# ─── Modelos Pydantic ───────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    """Payload de POST /process (Sección 1)."""

    message: str = Field(..., description="Mensaje del usuario")
    session_id: str = Field(..., description="UUID de la sesión/panel de chat (Sección 10)")
    parent_node_id: str | None = Field(
        None, description="ID del nodo anterior en el hilo de conversación"
    )
    language: str | None = Field(
        "es", description="Idioma preferido para la respuesta del Cerebro (ej: es, en)"
    )


class ProcessResponse(BaseModel):
    """Respuesta de POST /process."""

    enriched_prompt: str = Field(..., description="Prompt enriquecido con contexto histórico o web")
    node_id: str = Field(..., description="ID del nodo recién creado")
    intention: str = Field(..., description="Intención clasificada del mensaje")
    context: list[dict[str, Any]] = Field(
        default_factory=list, description="Nodos de contexto relevantes encontrados"
    )


class ScrapeRequest(BaseModel):
    """Payload de POST /scrape (Sección 5)."""

    url: str = Field(..., description="URL de la página web a raspar e indexar")
    session_id: str = Field(..., description="UUID de la sesión actual de conversación")
    parent_node_id: str | None = Field(None, description="ID del nodo anterior en el grafo")


class NodePatchRequest(BaseModel):
    """Payload de PATCH /graph/node/{id} (Sección 13)."""

    type: str = Field(..., description="Nuevo tipo del nodo (CONOCIMIENTO, ERROR_APRENDIDO, etc.)")


# ─── Broadcast WebSocket (Sección 13) ──────────────────────────────────────────

async def ws_broadcast(event: dict) -> None:
    """Emite un evento a todas las conexiones WebSocket activas."""
    if not ws_connections:
        return

    dead = set()
    for ws in ws_connections:
        try:
            await ws.send_json(event)
        except Exception:
            dead.add(ws)

    # Limpiar conexiones muertas
    ws_connections.difference_update(dead)


async def run_agent_cron_loop() -> None:
    """Bucle cognitivo autónomo en segundo plano (Agente Cron).
    
    Despierta periódicamente, consulta al LLM sobre el estado del sistema,
    ejecuta comandos autónomos si es necesario (con un bucle de hasta 3 iteraciones/pasos)
    e indexa todas las actividades en el grafo de neuronas.
    """
    logger.info("[Agente Cron] Iniciando bucle autónomo en segundo plano...")
    await asyncio.sleep(8.0)  # dar tiempo a que cargue el LLM y la base de datos

    session_id = "agent-cron-session"

    while True:
        try:
            # Obtener intervalo actual
            interval = config.get("agent_cron", {}).get("interval_seconds", 60)
            
            # Verificar si está habilitado
            if not config.get("agent_cron", {}).get("enabled", True):
                await asyncio.sleep(5.0)
                continue
                
            # Evitar colisión de recursos del LLM si el usuario está chateando activamente (últimos 5 minutos)
            global last_user_activity_time
            time_since_activity = time.time() - last_user_activity_time
            if time_since_activity < 300.0:
                logger.info("[Agente Cron] Pospuesto ciclo de monitoreo autónomo debido a actividad reciente del usuario (hace %.1fs, límite 300s)", time_since_activity)
                await asyncio.sleep(60.0)
                continue
                
            logger.info("[Agente Cron] Iniciando ciclo de monitoreo autónomo...")
            
            # Bucle de ReAct autónomo de hasta 3 pasos
            steps_limit = 3
            current_parent = None
            
            # Contexto inicial (Formulado en inglés para obediencia de DeepSeek-R1)
            system_prompt = (
                "[SYSTEM DIRECTIVE: AUTONOMOUS BACKGROUND MONITORING AGENT - DESHABILITADO]\n"
                "Autonomous background monitoring and terminal execution are disabled."
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Realiza la comprobación rutinaria del sistema en este ciclo cron."}
            ]
            
            for step in range(steps_limit):
                # Llamar al LLM mediante httpx al endpoint local
                client = httpx.AsyncClient(timeout=45.0)
                try:
                    resp = await client.post(
                        f"{LLM_URL_BASE}/v1/chat/completions",
                        json={"messages": messages, "stream": False}
                    )
                    resp.raise_for_status()
                    resp_data = resp.json()
                except Exception as exc:
                    logger.warning("[Agente Cron] Fallo al conectar con LLM: %s", exc)
                    break
                finally:
                    await client.aclose()
                    
                choices = resp_data.get("choices", [])
                if not choices:
                    break
                    
                llm_reply = choices[0].get("message", {}).get("content", "").strip()
                logger.info("[Agente Cron] Turno %d - Respuesta del Agente: %s...", step + 1, llm_reply[:80])
                
                # Buscar comandos en la respuesta
                commands = extract_commands(llm_reply)
                
                # Si responde SYSTEM OK o no hay comandos, terminar ciclo
                if "SYSTEM OK" in llm_reply or not commands:
                    # Si el LLM reportó que todo está bien, podemos guardar el log de salud en la DB
                    if "SYSTEM OK" in llm_reply and step == 0:
                        node_content = f"[Agente Cron] Chequeo de sistema rutinario completado. Todo en orden (SYSTEM OK)."
                        embedding = None
                        try:
                            embedding = await embeddings_client.get_embedding(node_content)
                        except Exception:
                            pass
                        health_node = await db.insert_node(
                            content=node_content,
                            session_id=session_id,
                            parent_id=None,
                            node_type="CONOCIMIENTO",
                            embedding=embedding
                        )
                        await ws_broadcast({"event": "node_created", "node": health_node})
                    break
                    
                # Ejecutar el comando (normalmente uno por paso en ReAct)
                cmd_str = commands[0].strip()
                output = await execute_system_command(cmd_str)
                
                # Guardar el nodo de comando + salida en el grafo de SQLite
                node_content = f"[CONSOLA AGENTE CRON] Comando: {cmd_str}\n\nResultado:\n{output}"
                embedding = None
                try:
                    embedding = await embeddings_client.get_embedding(node_content)
                except Exception:
                    pass
                    
                cmd_node = await db.insert_node(
                    content=node_content,
                    session_id=session_id,
                    parent_id=current_parent,
                    node_type="CONOCIMIENTO",
                    embedding=embedding
                )
                await ws_broadcast({"event": "node_created", "node": cmd_node})
                
                if current_parent:
                    edge = await db.insert_edge(current_parent, cmd_node["id"], 1.0)
                    await ws_broadcast({"event": "edge_created", "edge": edge})
                    
                current_parent = cmd_node["id"]
                
                # Alimentar el resultado al siguiente paso del bucle
                messages.append({"role": "assistant", "content": llm_reply})
                messages.append({"role": "user", "content": f"Resultado de la consola del paso anterior:\n{output}"})
                
                # Si el comando falló por denegación de sudo, evitar seguir intentando
                if "[Error de Seguridad]" in output:
                    break
            
            logger.info("[Agente Cron] Ciclo de monitoreo autónomo finalizado. Esperando al siguiente intervalo.")
            
        except Exception as exc:
            logger.error("[Agente Cron] Error crítico en el ciclo de fondo: %s", exc)
            
        # Esperar hasta el próximo ciclo
        interval = config.get("agent_cron", {}).get("interval_seconds", 60)
        await asyncio.sleep(interval)


# ─── Ciclo de vida de la aplicación ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona startup y shutdown del servidor."""
    global config, db, classifier, embeddings_client, web_scraper

    # Startup
    config = load_config()
    setup_logging(config)
    logger.info("═══ Cerebro Autónomo Unificado — Iniciando ═══")

    # Inicializar base de datos
    db_path = BASE_DIR / config["database"]["path"]
    embedding_dim = config["embeddings"].get("dimension", 1024)
    db = Database(db_path, embedding_dim=embedding_dim)
    await db.connect()

    stats = await db.get_stats()
    logger.info("Base de datos: %d nodos, %d aristas", stats["nodes"], stats["edges"])

    # Inicializar clasificador de intenciones
    classifier = IntentionClassifier(
        llm_url=config["llm"]["server_url"],
        timeout=config["llm"].get("classify_timeout", 5.0),
    )
    logger.info(
        "Clasificador inicializado: LLM en %s (timeout: %.1fs)",
        config["llm"]["server_url"],
        config["llm"].get("classify_timeout", 5.0),
    )

    # Inicializar cliente de embeddings
    embeddings_client = EmbeddingsClient(
        server_url=config["embeddings"]["server_url"],
        model=config["embeddings"].get("model", "bge-m3"),
        dimension=embedding_dim,
        normalize=config["embeddings"].get("normalize", True),
        timeout=5.0,
    )
    logger.info(
        "Cliente de embeddings inicializado: Servidor en %s (dimensión=%d, normalización=%s)",
        config["embeddings"]["server_url"],
        embedding_dim,
        config["embeddings"].get("normalize", True),
    )

    # Inicializar scraper web (Fase 5)
    web_scraper = WebScraper(config)
    logger.info(
        "Módulo de Scraping inicializado: Enabled=%s (TTL=%ds, maxLength=%d)",
        config["scraping"].get("enabled", True),
        config["scraping"].get("cache_ttl", 604800),
        config["scraping"].get("max_content_length", 2000),
    )

    # ─── Respaldo y Poda (Sección 11) ─────────────────────────────
    # Copia de seguridad en caliente al arranque
    if config.get("backup", {}).get("enabled", True):
        keep_last = config.get("backup", {}).get("keep_last", 5)
        await db.backup_database(keep_last=keep_last)

    # Tarea en segundo plano para poda/consolidación diferida de recuerdos antiguos
    async def _diferred_pruning():
        await asyncio.sleep(2.0)  # dar tiempo a que inicie el servidor
        try:
            # Poda recuerdos de más de 7 días (604800 segundos)
            older_than = 604800
            await db.consolidate_and_prune(older_than_seconds=older_than, embedding_client=embeddings_client)
        except Exception as exc:
            logger.error("Error en tarea diferida de poda: %s", exc)

    asyncio.create_task(_diferred_pruning())

    # Tarea en segundo plano para el Agente Cron Autónomo (Ciclos de Monitoreo) - DESHABILITADO POR SEGURIDAD
    logger.info("Agente Cron Autónomo deshabilitado por política de seguridad del terminal.")

    logger.info("═══ Cerebro Autónomo Unificado — Listo en %s:%d ═══",
                config["core"]["host"], config["core"]["port"])

    yield

    # Shutdown
    logger.info("═══ Cerebro Autónomo Unificado — Apagando ═══")
    if db:
        await db.close()


# ─── Aplicación FastAPI ─────────────────────────────────────────────────────────

app = FastAPI(
    title="Cerebro Autónomo Unificado",
    description="Motor cognitivo del sistema de memoria neuronal — Proxy e Intérprete de Comandos",
    version="0.7.0",
    lifespan=lifespan,
)

# CORS permisivo para desarrollo local (claude-mem, VS Code)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Endpoints Nativos ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check básico del Cerebro."""
    stats = await db.get_stats()
    return {
        "status": "ok",
        "name": "Cerebro Autónomo Unificado",
        "phase": 7,
        "stats": stats,
    }


@app.post("/process", response_model=ProcessResponse)
async def process_message(request: ProcessRequest):
    """Procesa un mensaje del usuario.

    Pipeline:
    1. Lanzar búsqueda de fondo / scraping en paralelo
    2. Clasificar intención
    3. Obtener embedding (degradación graceful en caso de fallo)
    4. Buscar contexto semántico en SQLite
    5. Crear/Bifurcar nodo en el grafo con su embedding
    6. Esperar y acoplar el contexto web
    7. Enriquecer prompt
    8. Broadcast WebSocket push
    """
    logger.info(
        "POST /process — sesión=%s, parent=%s, mensaje='%s...'",
        request.session_id,
        request.parent_node_id,
        request.message[:80],
    )

    # Detectar si hay una URL explícita en el mensaje del usuario
    url_match = URL_REGEX.search(request.message)
    detected_url = url_match.group(0) if url_match else None

    # 1. Lanzar tarea web en paralelo (Opción A, omnipresente)
    web_task = None
    if config["scraping"].get("enabled", True):
        if detected_url:
            async def scrape_task():
                try:
                    ttl = config["scraping"].get("cache_ttl", 604800)
                    clean_text = await db.get_cached_url(detected_url, ttl)
                    if not clean_text:
                        clean_text = await web_scraper.scrape_url(detected_url)
                        await db.save_cached_url(detected_url, clean_text)
                    return f"<contexto_web_busqueda>\n### Fuente: {detected_url}\nContenido:\n{clean_text}\n</contexto_web_busqueda>"
                except Exception as exc:
                    logger.warning("[Process Web Search] Error scraping explicit URL: %s", exc)
                    return ""
            web_task = asyncio.create_task(scrape_task())
        else:
            web_task = asyncio.create_task(_background_web_search(request.message))

    # 2. Clasificar intención
    intention = await classifier.classify(request.message)
    logger.info("Intención clasificada: %s", intention.value)

    if detected_url and config["scraping"].get("enabled", True):
        intention = Intention.INGESTA_WEB

    # 3. Inferencia de Embeddings
    embedding = None
    try:
        embedding = await embeddings_client.get_embedding(request.message)
    except Exception as exc:
        logger.warning("Fallo al obtener embedding: %s", exc)

    context_nodes = []
    new_node = {}
    enriched_parts = []
    similarity_threshold = config["database"].get("similarity_threshold", 0.40)

    # 4. Manejo de nodos (Split o Inserción normal)
    if intention == Intention.CORRECCION_ERROR:
        target_node_id = request.parent_node_id
        if not target_node_id:
            last_node = await db.get_last_node_in_session(request.session_id)
            if last_node:
                target_node_id = last_node["id"]

        if target_node_id:
            error_node, fix_node, edge = await db.split_node(
                error_node_id=target_node_id,
                fix_content=request.message,
                session_id=request.session_id,
                fix_embedding=embedding,
            )
            new_node = fix_node
            await ws_broadcast({
                "event": "split",
                "error_node": error_node,
                "fix_node": fix_node,
                "edge": edge,
            })
            enriched_parts.append(
                f"[CONTEXTO BIFURCACIÓN] El nodo {target_node_id[:8]} fue marcado como "
                f"ERROR_APRENDIDO. Se creó la corrección {fix_node['id'][:8]}."
            )
        else:
            new_node = await db.insert_node(
                content=request.message,
                session_id=request.session_id,
                parent_id=request.parent_node_id,
                node_type="CONOCIMIENTO",
                embedding=embedding,
            )
            await ws_broadcast({"event": "node_created", "node": new_node})
    else:
        # Consulta normal e Ingesta Web se procesan bajo el mismo flujo de recuperación semántica
        context_nodes_raw = await db.search_semantic(
            query_text=request.message,
            query_embedding=embedding,
            similarity_threshold=similarity_threshold,
            limit=15,
        )
        
        system_prefixes = (
            "[CONSOLA BASH]",
            "[CONSOLA AGENTE CRON]",
            "[TERMINAL WEB]",
            "[BÚSQUEDA WEB DE FONDO]",
            "[Agente Cron]",
            "[CONTEXTO INGESTA WEB]",
            "Indexación de:",
            "Indexación Manual:"
        )
        
        context_nodes = []
        for node in context_nodes_raw:
            content = node.get("content", "").strip()
            if any(content.startswith(pref) for pref in system_prefixes):
                continue
            context_nodes.append(node)
            if len(context_nodes) >= 5:
                break

        new_node = await db.insert_node(
            content=request.message,
            session_id=request.session_id,
            parent_id=request.parent_node_id,
            node_type="CONOCIMIENTO",
            embedding=embedding,
        )

        if request.parent_node_id:
            edge = await db.insert_edge(
                source_id=request.parent_node_id,
                target_id=new_node["id"],
                weight=1.0,
            )
            await ws_broadcast({"event": "edge_created", "edge": edge})

        await ws_broadcast({"event": "node_created", "node": new_node})

    # 5. Esperar el resultado de la tarea de búsqueda/scraping asíncrona con timeout de 2.0s
    web_context = ""
    if web_task:
        try:
            web_context = await asyncio.wait_for(web_task, timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("[Process Web Search] La búsqueda/scraping web superó el límite de 2.0s. Continuando sin contexto web.")
        except Exception as exc:
            logger.warning("[Process Web Search] Fallo al recuperar tarea asíncrona: %s", exc)

    # Registrar el contexto web obtenido como nodo cognitivo relacionado si existe (no bloqueante, en segundo plano)
    if web_context and "<contexto_web_busqueda>" in web_context:
        async def save_web_node_task():
            try:
                node_content = f"[BÚSQUEDA WEB DE FONDO]\n\n{web_context}"
                web_embedding = None
                try:
                    web_embedding = await embeddings_client.get_embedding(node_content)
                except Exception:
                    pass
                
                web_node = await db.insert_node(
                    content=node_content,
                    session_id=request.session_id,
                    parent_id=new_node["id"],
                    node_type="CONOCIMIENTO",
                    embedding=web_embedding
                )
                await ws_broadcast({"event": "node_created", "node": web_node})
                edge = await db.insert_edge(new_node["id"], web_node["id"], 1.0)
                await ws_broadcast({"event": "edge_created", "edge": edge})
            except Exception as exc:
                logger.warning("[Process Web Search] Fallo al insertar nodo de búsqueda: %s", exc)

        asyncio.create_task(save_web_node_task())

    # 6. Compilar prompt enriquecido
    lang_map = {
        "es": "Spanish (Español)",
        "en": "English (Inglés)",
        "pt": "Portuguese (Português)",
        "fr": "French (Français)"
    }
    target_lang = lang_map.get(request.language, "Spanish (Español)")

    identity_directive = render_system_prompt(target_lang=target_lang)
    enriched_parts.append(identity_directive)

    if web_context:
        enriched_parts.append(web_context)

    if context_nodes:
        enriched_parts.append("[CONTEXTO HISTÓRICO RELEVANTE]")
        for i, ctx in enumerate(context_nodes, 1):
            snippet = ctx.get("content", "")[:300]
            distance_str = f" (dist: {ctx['distance']:.3f})" if "distance" in ctx else ""
            enriched_parts.append(
                f"  [{i}] ({ctx.get('type', '?')}){distance_str} {snippet}"
            )
        enriched_parts.append("[FIN CONTEXTO]")

    enriched_parts.append(request.message)
    enriched_prompt = "\n".join(enriched_parts)

    response = ProcessResponse(
        enriched_prompt=enriched_prompt,
        node_id=new_node["id"],
        intention=intention.value,
        context=context_nodes,
    )

    return response


@app.post("/scrape")
async def scrape_manual(request: ScrapeRequest):
    """Endpoint manual para forzar el scraping e indexación de una URL específica (Sección 1)."""
    if not config["scraping"].get("enabled", True):
        raise HTTPException(
            status_code=400,
            detail="El scraping web está deshabilitado en config.yaml"
        )

    logger.info("POST /scrape manual para URL: %s", request.url)
    
    try:
        ttl = config["scraping"].get("cache_ttl", 604800)
        cached_text = await db.get_cached_url(request.url, ttl)
        
        clean_text = cached_text
        if not clean_text:
            clean_text = await web_scraper.scrape_url(request.url)
            await db.save_cached_url(request.url, clean_text)
            
        embedding = None
        try:
            embedding = await embeddings_client.get_embedding(clean_text)
        except Exception as exc:
            logger.warning("Fallo al obtener embedding para URL manual %s: %s", request.url, exc)
            
        node_content = f"Indexación Manual: {request.url}\n\n{clean_text}"
        new_node = await db.insert_node(
            content=node_content,
            session_id=request.session_id,
            parent_id=request.parent_node_id,
            node_type="CONOCIMIENTO",
            embedding=embedding
        )
        
        if request.parent_node_id:
            edge = await db.insert_edge(
                source_id=request.parent_node_id,
                target_id=new_node["id"],
                weight=1.0
            )
            await ws_broadcast({"event": "edge_created", "edge": edge})
            
        await ws_broadcast({"event": "node_created", "node": new_node})
        
        return {
            "status": "ok",
            "node_id": new_node["id"],
            "url": request.url,
            "cached": cached_text is not None,
            "text_length": len(clean_text)
        }
        
    except Exception as exc:
        logger.error("Error en POST /scrape manual para %s: %s", request.url, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Fallo al procesar scraping: {str(exc)}"
        )


@app.get("/graph")
async def get_graph():
    """Devuelve el grafo completo de nodos y aristas (Sección 1)."""
    graph = await db.get_graph()
    return graph


@app.patch("/graph/node/{node_id}")
async def patch_node(node_id: str, patch: NodePatchRequest):
    """Edición manual del tipo de un nodo (Sección 13)."""
    existing = await db.get_node(node_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Nodo {node_id} no encontrado")

    valid_types = {"CONOCIMIENTO", "ERROR_APRENDIDO", "BIFURCACION_FIX"}
    if patch.type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo inválido '{patch.type}'. Válidos: {valid_types}",
        )

    updated = await db.update_node_type(node_id, patch.type)

    await ws_broadcast({
        "event": "node_updated",
        "node": updated,
    })

    return updated


@app.delete("/graph/edge/{source_id}/{target_id}")
async def delete_edge(source_id: str, target_id: str):
    """Elimina una arista del grafo (Sección 13)."""
    deleted = await db.delete_edge(source_id, target_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Arista {source_id} → {target_id} no encontrada",
        )

    await ws_broadcast({
        "event": "edge_deleted",
        "source_id": source_id,
        "target_id": target_id,
    })

    return {"deleted": True, "source_id": source_id, "target_id": target_id}


@app.delete("/api/brain/wipe")
async def wipe_brain():
    """Purgar por completo las tablas del cerebro en SQLite y ejecutar VACUUM."""
    logger.warning("[Mantenimiento] Solicitada purga completa (wipe) del cerebro.")
    if not db or not db._conn:
        raise HTTPException(status_code=500, detail="Base de datos no inicializada")
    
    try:
        async with db._conn.cursor() as cursor:
            # Desactivar restricciones de integridad referencial temporalmente
            await cursor.execute("PRAGMA foreign_keys = OFF;")
            await cursor.execute("DELETE FROM edges;")
            await cursor.execute("DELETE FROM nodes;")
            await cursor.execute("DELETE FROM web_cache;")
            await cursor.execute("DELETE FROM nodes_fts;")
            await cursor.execute("DELETE FROM vec_embeddings;")
            await cursor.execute("PRAGMA foreign_keys = ON;")
            await cursor.execute("VACUUM;")
            await db._conn.commit()
            
        logger.info("[Mantenimiento] Cerebro purgado y VACUUM ejecutado con éxito.")
        
        # Broadcast de evento wipe para que la UI repinte el grafo vacío en caliente
        await ws_broadcast({"event": "wipe", "status": "ok"})
        
        return {"status": "ok", "message": "Cerebro purgado con éxito"}
    except Exception as exc:
        logger.error("[Mantenimiento] Fallo al purgar el cerebro: %s", exc)
        raise HTTPException(status_code=500, detail=f"Fallo al purgar el cerebro: {exc}")


# ─── WebSocket (Sección 13) ─────────────────────────────────────────────────────

@app.websocket("/ws/graph")
async def websocket_graph(ws: WebSocket):
    """WebSocket para actualización push del grafo en tiempo real."""
    await ws.accept()
    ws_connections.add(ws)
    logger.info("WebSocket conectado — total: %d", len(ws_connections))

    try:
        while True:
            data = await ws.receive_text()
            logger.debug("WebSocket recibió: %s", data[:100] if data else "")
    except WebSocketDisconnect:
        ws_connections.discard(ws)
        logger.info("WebSocket desconectado — total: %d", len(ws_connections))
    except Exception as exc:
        ws_connections.discard(ws)
        logger.warning("WebSocket error: %s — total: %d", exc, len(ws_connections))


# ─── TERMINAL WEB INTERACTIVA (WebSocket) ─────────────────────────────────────

@app.websocket("/ws/terminal")
async def websocket_terminal(ws: WebSocket):
    """WebSocket para la terminal interactiva del navegador."""
    await ws.accept()
    logger.info("[Terminal WS] Cliente conectado")
    await ws.send_json({"event": "connected", "message": "Terminal conectada al Cerebro Autónomo"})

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                await ws.send_json({"event": "error", "message": "JSON inválido"})
                continue

            command = data.get("command", "").strip()
            if not command:
                await ws.send_json({"event": "error", "message": "Comando vacío"})
                continue

            logger.info("[Terminal WS] Ejecutando: '%s'", command)
            await ws.send_json({"event": "running", "command": command})

            # Ejecutar con la misma función segura (bloquea sudo, intercepta search)
            output = await execute_system_command(command)

            # Guardar como nodo neuronal
            session_id = "terminal-web-session"
            node_content = f"[TERMINAL WEB] $ {command}\n\n{output}"

            embedding = None
            try:
                embedding = await embeddings_client.get_embedding(node_content)
            except Exception:
                pass

            cmd_node = await db.insert_node(
                content=node_content,
                session_id=session_id,
                node_type="CONOCIMIENTO",
                embedding=embedding
            )
            await ws_broadcast({"event": "node_created", "node": cmd_node})

            await ws.send_json({
                "event": "output",
                "command": command,
                "output": output,
                "node_id": cmd_node["id"]
            })

    except WebSocketDisconnect:
        logger.info("[Terminal WS] Cliente desconectado")
    except Exception as exc:
        logger.warning("[Terminal WS] Error: %s", exc)


# ─── LOGICA DEL PROXY INTERCEPTOR (Fase Ampliación) ──────────────────────────────

LLM_URL_BASE = "http://127.0.0.1:8080"


async def web_search(query: str, max_results: int = 3) -> str:
    """Realiza una consulta a la API local de SearXNG (puerto 8888), filtra y limpia los resultados."""
    logger.info("[Web Search] Iniciando consulta para: '%s' (max_results=%d)", query, max_results)
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
            return f"No se encontraron resultados en la web para la consulta: '{query}'."
        
        # Filtro de relevancia básico: Excluir resultados vacíos, duplicados o sin url
        seen_urls = set()
        cleaned_parts = []
        
        for r in results:
            title = r.get("title", "").strip()
            url = r.get("url", "").strip()
            snippet = r.get("content", "").strip()
            
            if not title or not url or url in seen_urls:
                continue
                
            seen_urls.add(url)
            # Saneamiento de etiquetas HTML en el snippet
            snippet_clean = re.sub(r'<[^>]+>', '', snippet).strip()
            
            cleaned_parts.append(f"### Fuente: {title}\nURL: {url}\nResumen: {snippet_clean}\n---")
            if len(cleaned_parts) >= max_results:
                break
                
        return "\n".join(cleaned_parts) if cleaned_parts else "No se encontraron resultados relevantes."
    except Exception as exc:
        logger.error("[Web Search] Error en búsqueda web: %s", exc)
        return f"[Error de Búsqueda Web]: {str(exc)}"


@app.get("/api/web_search")
async def api_web_search(q: str, max_results: int = 3):
    """Endpoint HTTP para realizar búsquedas web directamente a través de SearXNG."""
    results = await web_search(q, max_results)
    return {"query": q, "results": results}


class WebSearchToolRequest(BaseModel):
    query: str


async def ejecutar_busqueda_web(query: str) -> str:
    """Usar obligatoriamente para cualquier duda sobre eventos actuales, noticias, deportes,
    clima, búsquedas en internet y datos del año 2024-2026. NUNCA usar la terminal para estas consultas.
    Realiza una consulta a SearXNG, filtra por score de relevancia y devuelve títulos, URLs y snippets completos.
    """
    logger.info("[Tool: ejecutar_busqueda_web] Iniciando búsqueda estructurada: '%s'", query)
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
            return "No se encontraron resultados en la web para esta consulta."
            
        # Filtrar por validez de campos principales y ordenar por score descendente
        valid_results = [
            r for r in results
            if r.get("title") and r.get("url") and r.get("content")
        ]
        valid_results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
        
        output_parts = []
        for i, r in enumerate(valid_results[:5]):
            title = r.get("title", "").strip()
            url = r.get("url", "").strip()
            # Contenido completo del snippet, sin truncar
            snippet = r.get("content", "").strip()
            snippet_clean = re.sub(r'<[^>]+>', '', snippet).strip()
            score = r.get("score", "N/A")
            # Campos extra opcionales de SearXNG
            published = r.get("publishedDate", "")
            engine = r.get("engine", "")
            
            entry = (
                f"Resultado {i+1}:\n"
                f"- Título: {title}\n"
                f"- URL: {url}\n"
                f"- Score: {score}\n"
            )
            if published:
                entry += f"- Fecha de publicación: {published}\n"
            if engine:
                entry += f"- Motor: {engine}\n"
            entry += f"- Contenido: {snippet_clean}\n"
            output_parts.append(entry)
            
        header = (
            f"A continuación tienes los resultados reales de la web obtenidos en tiempo real "
            f"para la consulta '{query}'. Utilízalos para responder la duda del usuario "
            f"de forma directa y concisa:\n\n"
        )
        return header + "\n".join(output_parts) if output_parts else "No se encontraron resultados relevantes."
    except Exception as exc:
        logger.error("[Tool: ejecutar_busqueda_web] Fallo en la búsqueda: %s", exc)
        return f"[Error en la búsqueda estructurada]: {str(exc)}"


@app.post("/api/tools/ejecutar_busqueda_web")
async def api_ejecutar_busqueda_web(req: WebSearchToolRequest):
    """Endpoint de API que expone ejecutar_busqueda_web para Tool Use o Function Calling."""
    output = await ejecutar_busqueda_web(req.query)
    return {"result": output}


async def _background_web_search(query: str) -> str:
    """Invoca la función web_search de fondo e inyecta el contenido formateado."""
    logger.info("[Background Search] Invocando web_search para query: '%s'", query)
    results_text = await web_search(query, max_results=3)
    return f"<contexto_web_busqueda>\n{results_text}\n</contexto_web_busqueda>"


async def execute_system_command(command: str) -> str:
    """Solo usar para tareas administrativas del sistema local Linux, configuración de servidores
    o monitoreo de hardware. NUNCA usar para consultas informativas generales o eventos externos.
    [DESHABILITADO] Retorna error de ejecución indicando que la terminal está deshabilitada.
    """
    logger.warning("[Agente Terminal] Intento de ejecución de comando bloqueado: '%s'", command.strip())
    return (
        "[Error de Seguridad] La ejecución autónoma de comandos del sistema mediante la terminal "
        "está estrictamente deshabilitada en esta instancia del Cerebro Autónomo."
    )

async def query_memory_and_enrich(message: str, session_id: str) -> tuple[str, str]:
    """Consulta la memoria neuronal semántica para enriquecer el prompt del proxy."""
    # 1. Lanzar búsqueda/scraping web en paralelo (Opción A, omnipresente)
    web_task = None
    if config["scraping"].get("enabled", True):
        url_match = URL_REGEX.search(message)
        detected_url = url_match.group(0) if url_match else None
        
        if detected_url:
            async def scrape_task():
                try:
                    ttl = config["scraping"].get("cache_ttl", 604800)
                    clean_text = await db.get_cached_url(detected_url, ttl)
                    if not clean_text:
                        clean_text = await web_scraper.scrape_url(detected_url)
                        await db.save_cached_url(detected_url, clean_text)
                    return f"<contexto_web_busqueda>\n### Fuente: {detected_url}\nContenido:\n{clean_text}\n</contexto_web_busqueda>"
                except Exception as exc:
                    logger.warning("[Proxy Web Search] Error scraping explicit URL: %s", exc)
                    return ""
            web_task = asyncio.create_task(scrape_task())
        else:
            web_task = asyncio.create_task(_background_web_search(message))

    # 2. Obtener embedding de forma segura
    embedding = None
    try:
        embedding = await embeddings_client.get_embedding(message)
    except Exception as exc:
        logger.warning("[Proxy] Fallo al obtener embedding: %s", exc)

    # 3. Obtener el último nodo de la sesión para mantener la jerarquía temporal de la conversación (Sección 3)
    last_node = await db.get_last_node_in_session(session_id)
    parent_id = last_node["id"] if last_node else None

    # 4. Insertar el nodo de la pregunta
    new_node = await db.insert_node(
        content=message,
        session_id=session_id,
        parent_id=parent_id,
        node_type="CONOCIMIENTO",
        embedding=embedding
    )
    await ws_broadcast({"event": "node_created", "node": new_node})

    # Enlazar con el nodo anterior del hilo si existe
    if parent_id:
        edge = await db.insert_edge(parent_id, new_node["id"], 1.0)
        await ws_broadcast({"event": "edge_created", "edge": edge})

    # 5. Buscar recuerdos relevantes (Filtrando logs/comandos automáticos de sistema)
    similarity_threshold = config["database"].get("similarity_threshold", 0.40)
    context_nodes_raw = await db.search_semantic(
        query_text=message,
        query_embedding=embedding,
        similarity_threshold=similarity_threshold,
        limit=15
    )
    
    system_prefixes = (
        "[CONSOLA BASH]",
        "[CONSOLA AGENTE CRON]",
        "[TERMINAL WEB]",
        "[BÚSQUEDA WEB DE FONDO]",
        "[Agente Cron]",
        "[CONTEXTO INGESTA WEB]",
        "Indexación de:",
        "Indexación Manual:"
    )
    
    context_nodes = []
    for node in context_nodes_raw:
        content = node.get("content", "").strip()
        if any(content.startswith(pref) for pref in system_prefixes):
            continue
        context_nodes.append(node)
        if len(context_nodes) >= 3:
            break

    # 6. Esperar el resultado de la tarea web con timeout de 2.0s
    web_context = ""
    if web_task:
        try:
            web_context = await asyncio.wait_for(web_task, timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("[Proxy Web Search] La búsqueda/scraping web superó el límite de 2.0s. Continuando sin contexto web.")
        except Exception as exc:
            logger.warning("[Proxy Web Search] Fallo al recuperar tarea asíncrona: %s", exc)

    # Registrar el contexto web obtenido como nodo cognitivo relacionado si existe (no bloqueante, en segundo plano)
    if web_context and "<contexto_web_busqueda>" in web_context:
        async def save_web_node_task():
            try:
                node_content = f"[BÚSQUEDA WEB DE FONDO]\n\n{web_context}"
                web_embedding = None
                try:
                    web_embedding = await embeddings_client.get_embedding(node_content)
                except Exception:
                    pass
                
                web_node = await db.insert_node(
                    content=node_content,
                    session_id=session_id,
                    parent_id=new_node["id"],
                    node_type="CONOCIMIENTO",
                    embedding=web_embedding
                )
                await ws_broadcast({"event": "node_created", "node": web_node})
                edge = await db.insert_edge(new_node["id"], web_node["id"], 1.0)
                await ws_broadcast({"event": "edge_created", "edge": edge})
            except Exception as exc:
                logger.warning("[Proxy Web Search] Fallo al insertar nodo de búsqueda: %s", exc)

        asyncio.create_task(save_web_node_task())

    enriched_parts = []
    
    # Directiva de Identidad Evolutiva & Ejecución (Formulada en inglés para garantizar cumplimiento por el LLM)
    identity_directive = render_system_prompt(target_lang="Spanish (Español)")
    enriched_parts.append(identity_directive)

    # Inyectar el contexto web si existe
    if web_context:
        enriched_parts.append(web_context)

    if context_nodes:
        enriched_parts.append("[CONTEXTO HISTÓRICO RELEVANTE]")
        for i, ctx in enumerate(context_nodes, 1):
            enriched_parts.append(f"  - ({ctx.get('type')}) {ctx.get('content')}")
        enriched_parts.append("[FIN CONTEXTO]")
        
    enriched_parts.append(message)
    enriched_prompt = "\n".join(enriched_parts)
    
    return enriched_prompt, new_node["id"]


async def handle_post_response_commands(full_reply: str, parent_node_id: str, session_id: str) -> None:
    """Escanea la respuesta del LLM en busca de comandos CMD: <comando> y los ejecuta en caliente."""
    commands = extract_commands(full_reply)
    if not commands:
        return
        
    # Ejecutar comandos de forma secuencial y registrarlos en el grafo
    current_parent = parent_node_id
    for cmd in commands:
        cmd_str = cmd.strip()
        # Limpiar residuos comunes de bloques de markdown si el LLM los incluyó en la línea
        cmd_str = cmd_str.replace("`", "").strip()
        if not cmd_str:
            continue
            
        # Ejecutar el comando
        output = await execute_system_command(cmd_str)
        
        # Guardar en base de datos como un nodo de conocimiento de terminal
        node_content = f"[CONSOLA BASH] Comando: {cmd_str}\n\nResultado:\n{output}"
        
        embedding = None
        try:
            embedding = await embeddings_client.get_embedding(node_content)
        except Exception:
            pass
            
        cmd_node = await db.insert_node(
            content=node_content,
            session_id=session_id,
            parent_id=current_parent,
            node_type="CONOCIMIENTO",
            embedding=embedding
        )
        await ws_broadcast({"event": "node_created", "node": cmd_node})
        
        # Enlazar arista
        edge = await db.insert_edge(current_parent, cmd_node["id"], 1.0)
        await ws_broadcast({"event": "edge_created", "edge": edge})
        
        # El resultado pasa a ser el padre de cualquier comando subsecuente
        current_parent = cmd_node["id"]


# ─── FUNCIONES DE ORQUESTACIÓN REACT EN EL PROXY (Fase Ampliación) ─────────────

async def stream_text_openai(text: str) -> AsyncGenerator[bytes, None]:
    """Generador SSE para simular streaming en formato OpenAI."""
    words = re.split(r"(\s+)", text)
    for word in words:
        if not word:
            continue
        chunk_data = {
            "choices": [{
                "index": 0,
                "delta": {
                    "content": word
                },
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(chunk_data)}\n\n".encode("utf-8")
        await asyncio.sleep(0.012)  # Animación fluida de 12ms
    yield b"data: [DONE]\n\n"


async def stream_text_completion(text: str) -> AsyncGenerator[bytes, None]:
    """Generador SSE para simular streaming en formato propietario llama.cpp."""
    words = re.split(r"(\s+)", text)
    for word in words:
        if not word:
            continue
        chunk_data = {
            "content": word,
            "stop": False
        }
        yield f"data: {json.dumps(chunk_data)}\n\n".encode("utf-8")
        await asyncio.sleep(0.012)
    yield f"data: {json.dumps({'content': '', 'stop': True})}\n\n".encode("utf-8")


async def run_react_loop_openai(messages: list, body: dict, session_id: str, parent_node_id: str) -> tuple[str, str]:
    """Ejecuta un bucle iterativo ReAct local para OpenAI Chat Completions."""
    current_parent = parent_node_id
    max_steps = 3
    local_messages = list(messages)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for step in range(max_steps):
            temp_body = dict(body)
            temp_body["messages"] = local_messages
            temp_body["stream"] = False
            
            logger.info("[ReAct OpenAI] Paso %d: Enviando al LLM local...", step + 1)
            resp = await client.post(f"{LLM_URL_BASE}/v1/chat/completions", json=temp_body)
            resp.raise_for_status()
            resp_data = resp.json()
            
            choices = resp_data.get("choices", [])
            llm_text = ""
            if choices:
                llm_text = choices[0].get("message", {}).get("content", "")
            
            if not llm_text.strip():
                break
                
            commands = extract_commands(llm_text)
            if not commands:
                return llm_text, current_parent
                
            logger.info("[ReAct OpenAI] Comandos detectados en paso %d: %s", step + 1, commands)
            
            # Guardar nodo del bot con la intención
            bot_node = await db.insert_node(
                content=llm_text,
                session_id=session_id,
                parent_id=current_parent,
                node_type="CONOCIMIENTO"
            )
            await ws_broadcast({"event": "node_created", "node": bot_node})
            edge = await db.insert_edge(current_parent, bot_node["id"], 1.0)
            await ws_broadcast({"event": "edge_created", "edge": edge})
            current_parent = bot_node["id"]
            
            # Ejecutar comandos
            cmd_outputs = []
            for cmd in commands:
                cmd_str = cmd.strip().replace("`", "").strip()
                if not cmd_str:
                    continue
                output = await execute_system_command(cmd_str)
                cmd_outputs.append(f"[Terminal] $ {cmd_str}\n{output}")
                
                # Guardar nodo de consola
                node_content = f"[CONSOLA BASH] Comando: {cmd_str}\n\nResultado:\n{output}"
                embedding = None
                try:
                    embedding = await embeddings_client.get_embedding(node_content)
                except Exception:
                    pass
                cmd_node = await db.insert_node(
                    content=node_content,
                    session_id=session_id,
                    parent_id=current_parent,
                    node_type="CONOCIMIENTO",
                    embedding=embedding
                )
                await ws_broadcast({"event": "node_created", "node": cmd_node})
                edge = await db.insert_edge(current_parent, cmd_node["id"], 1.0)
                await ws_broadcast({"event": "edge_created", "edge": edge})
                current_parent = cmd_node["id"]
                
            # Actualizar historial local
            local_messages.append({"role": "assistant", "content": llm_text})
            combined_outputs = "\n\n".join(cmd_outputs)
            local_messages.append({
                "role": "system",
                "content": (
                    f"[SYSTEM: RESULTADO DE EJECUCIÓN]\n{combined_outputs}\n\n"
                    f"Analiza este resultado y responde al usuario de forma final en español."
                )
            })
            
    return "Lo siento, se alcanzó el límite de pasos sin una respuesta final.", current_parent


async def run_react_loop_completion(prompt: str, body: dict, session_id: str, parent_node_id: str) -> tuple[str, str]:
    """Ejecuta un bucle iterativo ReAct local para Completions tradicionales."""
    current_parent = parent_node_id
    max_steps = 3
    current_prompt = prompt
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for step in range(max_steps):
            temp_body = dict(body)
            temp_body["prompt"] = current_prompt
            temp_body["stream"] = False
            
            logger.info("[ReAct Completion] Paso %d: Enviando al LLM local...", step + 1)
            resp = await client.post(f"{LLM_URL_BASE}/completion", json=temp_body)
            resp.raise_for_status()
            resp_data = resp.json()
            
            llm_text = resp_data.get("content", "")
            if not llm_text.strip():
                break
                
            commands = extract_commands(llm_text)
            if not commands:
                return llm_text, current_parent
                
            logger.info("[ReAct Completion] Comandos detectados en paso %d: %s", step + 1, commands)
            
            # Guardar nodo del bot
            bot_node = await db.insert_node(
                content=llm_text,
                session_id=session_id,
                parent_id=current_parent,
                node_type="CONOCIMIENTO"
            )
            await ws_broadcast({"event": "node_created", "node": bot_node})
            edge = await db.insert_edge(current_parent, bot_node["id"], 1.0)
            await ws_broadcast({"event": "edge_created", "edge": edge})
            current_parent = bot_node["id"]
            
            # Ejecutar comandos
            cmd_outputs = []
            for cmd in commands:
                cmd_str = cmd.strip().replace("`", "").strip()
                if not cmd_str:
                    continue
                output = await execute_system_command(cmd_str)
                cmd_outputs.append(f"[Terminal] $ {cmd_str}\n{output}")
                
                # Guardar nodo de consola
                node_content = f"[CONSOLA BASH] Comando: {cmd_str}\n\nResultado:\n{output}"
                embedding = None
                try:
                    embedding = await embeddings_client.get_embedding(node_content)
                except Exception:
                    pass
                cmd_node = await db.insert_node(
                    content=node_content,
                    session_id=session_id,
                    parent_id=current_parent,
                    node_type="CONOCIMIENTO",
                    embedding=embedding
                )
                await ws_broadcast({"event": "node_created", "node": cmd_node})
                edge = await db.insert_edge(current_parent, cmd_node["id"], 1.0)
                await ws_broadcast({"event": "edge_created", "edge": edge})
                current_parent = cmd_node["id"]
                
            # Actualizar prompt
            combined_outputs = "\n\n".join(cmd_outputs)
            current_prompt += f"\n{llm_text}\n\n[SYSTEM: RESULTADO DE EJECUCIÓN]\n{combined_outputs}\n\nResponde al usuario en español."
            
    return "Lo siento, se alcanzó el límite de pasos sin una respuesta final.", current_parent


@app.post("/completion")
async def proxy_completion(request: Request):
    """Proxy interceptor para la API propietaria de Completions de llama.cpp."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    original_prompt = body.get("prompt", "")
    stream = body.get("stream", False)
    session_id = "proxy-chat-session"

    logger.info("[Proxy] Interceptada petición /completion. Prompt: '%s...'", original_prompt[:60])

    # 1. Consultar recuerdos y enriquecer el prompt
    global last_user_activity_time
    last_user_activity_time = time.time()
    enriched_prompt, question_node_id = await query_memory_and_enrich(original_prompt, session_id)
    body["prompt"] = enriched_prompt

    # 2. Reenviar al LLM original (llama-server)
    client = httpx.AsyncClient(timeout=60.0)

    # 3. Primer turno en modo no-streaming interno para inspección rápida (toma ~500ms)
    try:
        temp_body = dict(body)
        temp_body["stream"] = False
        resp = await client.post(f"{LLM_URL_BASE}/completion", json=temp_body)
        resp.raise_for_status()
        resp_data = resp.json()
        llm_text = resp_data.get("content", "")
    except Exception as exc:
        await client.aclose()
        logger.error("[Proxy] Error en llamada inicial /completion: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    commands = extract_commands(llm_text)

    if commands:
        logger.info("[Proxy] Comandos detectados en /completion: %s. Ejecutando y haciendo stream de interpretación...", commands)
        
        # Guardar nodo del bot con la intención
        bot_node = await db.insert_node(
            content=llm_text,
            session_id=session_id,
            parent_id=question_node_id,
            node_type="CONOCIMIENTO"
        )
        await ws_broadcast({"event": "node_created", "node": bot_node})
        edge = await db.insert_edge(question_node_id, bot_node["id"], 1.0)
        await ws_broadcast({"event": "edge_created", "edge": edge})
        current_parent = bot_node["id"]

        # Ejecutar comandos secuencialmente
        cmd_outputs = []
        for cmd in commands:
            cmd_str = cmd.strip().replace("`", "").strip()
            if not cmd_str:
                continue
            output = await execute_system_command(cmd_str)
            cmd_outputs.append(f"[Terminal] $ {cmd_str}\n{output}")
            
            # Registrar nodo de consola
            node_content = f"[CONSOLA BASH] Comando: {cmd_str}\n\nResultado:\n{output}"
            embedding = None
            try:
                embedding = await embeddings_client.get_embedding(node_content)
            except Exception:
                pass
            cmd_node = await db.insert_node(
                content=node_content,
                session_id=session_id,
                parent_id=current_parent,
                node_type="CONOCIMIENTO",
                embedding=embedding
            )
            await ws_broadcast({"event": "node_created", "node": cmd_node})
            edge = await db.insert_edge(current_parent, cmd_node["id"], 1.0)
            await ws_broadcast({"event": "edge_created", "edge": edge})
            current_parent = cmd_node["id"]

        # Inyectar resultados y preparar el segundo turno
        combined_outputs = "\n\n".join(cmd_outputs)
        second_body = dict(body)
        second_body["prompt"] = enriched_prompt + f"\n{llm_text}\n\n[SYSTEM: RESULTADO DE EJECUCIÓN]\n{combined_outputs}\n\nResponde al usuario en español."
        second_body["stream"] = stream

        if not stream:
            # Caso no-stream para el segundo turno
            try:
                second_resp = await client.post(f"{LLM_URL_BASE}/completion", json=second_body)
                second_resp.raise_for_status()
                second_resp_data = second_resp.json()
                
                final_text = second_resp_data.get("content", "")
                
                # Guardar respuesta final en base
                final_node = await db.insert_node(
                    content=final_text,
                    session_id=session_id,
                    parent_id=current_parent,
                    node_type="CONOCIMIENTO"
                )
                await ws_broadcast({"event": "node_created", "node": final_node})
                edge = await db.insert_edge(current_parent, final_node["id"], 1.0)
                await ws_broadcast({"event": "edge_created", "edge": edge})
                
                return second_resp_data
            except Exception as exc:
                logger.error("[Proxy] Error en segundo turno /completion: %s", exc)
                raise HTTPException(status_code=500, detail=str(exc))
            finally:
                await client.aclose()
        else:
            # Caso stream para el segundo turno
            async def second_stream_generator() -> AsyncGenerator[bytes, None]:
                second_llm_reply_chunks = []
                try:
                    # Enviar prefijo de ejecución al usuario
                    prefix_msg = f"*(Ejecutando comando: {', '.join(commands)}...)*\n\n"
                    prefix_chunk = {"content": prefix_msg, "stop": False}
                    yield f"data: {json.dumps(prefix_chunk)}\n\n".encode("utf-8")
                    
                    async with httpx.AsyncClient(timeout=60.0) as second_client:
                        async with second_client.stream("POST", f"{LLM_URL_BASE}/completion", json=second_body) as r2:
                            buffer2 = ""
                            async for chunk in r2.aiter_bytes():
                                buffer2 += chunk.decode("utf-8", errors="ignore")
                                while "\n" in buffer2:
                                    line, buffer2 = buffer2.split("\n", 1)
                                    line = line.strip()
                                    if line.startswith("data:"):
                                        data_str = line[5:].strip()
                                        try:
                                            data_json = json.loads(data_str)
                                            content = data_json.get("content", "")
                                            if content:
                                                second_llm_reply_chunks.append(content)
                                        except Exception:
                                            pass
                                yield chunk
                                
                    # Guardar respuesta final en base al terminar el stream
                    second_reply = "".join(second_llm_reply_chunks)
                    if second_reply.strip():
                        final_reply_node = await db.insert_node(
                            content=second_reply,
                            session_id=session_id,
                            parent_id=current_parent,
                            node_type="CONOCIMIENTO"
                        )
                        await ws_broadcast({"event": "node_created", "node": final_reply_node})
                        edge = await db.insert_edge(current_parent, final_reply_node["id"], 1.0)
                        await ws_broadcast({"event": "edge_created", "edge": edge})
                except Exception as stream_exc:
                    logger.error("[Proxy Stream second turn /completion] Error: %s", stream_exc)
                finally:
                    await client.aclose()
                    yield f"data: {json.dumps({'content': '', 'stop': True})}\n\n".encode("utf-8")

            return StreamingResponse(second_stream_generator(), media_type="text/event-stream")

    else:
        # Caso común sin comandos. Retransmitir de forma inmediata
        # Guardar respuesta del LLM
        reply_node = await db.insert_node(
            content=llm_text,
            session_id=session_id,
            parent_id=question_node_id,
            node_type="CONOCIMIENTO"
        )
        await ws_broadcast({"event": "node_created", "node": reply_node})
        edge = await db.insert_edge(question_node_id, reply_node["id"], 1.0)
        await ws_broadcast({"event": "edge_created", "edge": edge})
        
        await client.aclose()
        
        if not stream:
            return resp_data
        else:
            return StreamingResponse(stream_text_completion(llm_text), media_type="text/event-stream")

        return StreamingResponse(stream_generator(), media_type="text/event-stream")


@app.post("/v1/chat/completions")
async def proxy_openai_chat(request: Request):
    """Proxy interceptor para la API OpenAI Chat Completions."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    messages = body.get("messages", [])
    stream = body.get("stream", False)
    session_id = "proxy-chat-session"

    user_message = ""
    if messages:
        user_message = messages[-1].get("content", "")

    logger.info("[Proxy] Interceptada petición /v1/chat/completions: '%s...'", user_message[:60])

    # 1. Consultar recuerdos y enriquecer el prompt
    global last_user_activity_time
    last_user_activity_time = time.time()
    enriched_prompt, question_node_id = await query_memory_and_enrich(user_message, session_id)
    if messages:
        messages[-1]["content"] = enriched_prompt
        body["messages"] = messages

    # 2. Reenviar
    client = httpx.AsyncClient(timeout=60.0)

    if not stream:
        # Modo No-Streaming (REST ordinario)
        try:
            temp_body = dict(body)
            temp_body["stream"] = False
            resp = await client.post(f"{LLM_URL_BASE}/v1/chat/completions", json=temp_body)
            resp.raise_for_status()
            resp_data = resp.json()
            
            choices = resp_data.get("choices", [])
            llm_text = ""
            if choices:
                llm_text = choices[0].get("message", {}).get("content", "")
                
            commands = extract_commands(llm_text)
            if commands:
                logger.info("[Proxy REST /v1/chat/completions] Comandos detectados: %s. Ejecutando ReAct...", commands)
                final_text, final_parent = await run_react_loop_openai(messages, body, session_id, question_node_id)
                
                # Guardar respuesta final en base
                reply_node = await db.insert_node(
                    content=final_text,
                    session_id=session_id,
                    parent_id=final_parent,
                    node_type="CONOCIMIENTO"
                )
                await ws_broadcast({"event": "node_created", "node": reply_node})
                edge = await db.insert_edge(final_parent, reply_node["id"], 1.0)
                await ws_broadcast({"event": "edge_created", "edge": edge})
                
                if "choices" in resp_data and resp_data["choices"]:
                    resp_data["choices"][0]["message"]["content"] = final_text
                return resp_data
            else:
                # Caso común sin comandos
                reply_node = await db.insert_node(
                    content=llm_text,
                    session_id=session_id,
                    parent_id=question_node_id,
                    node_type="CONOCIMIENTO"
                )
                await ws_broadcast({"event": "node_created", "node": reply_node})
                edge = await db.insert_edge(question_node_id, reply_node["id"], 1.0)
                await ws_broadcast({"event": "edge_created", "edge": edge})
                return resp_data
        except Exception as exc:
            logger.error("[Proxy REST /v1/chat/completions] Fallo en ejecución: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))
        finally:
            await client.aclose()
    else:
        # Modo Streaming SSE Multi-turno con interceptor de tool_calls emuladas
        async def stream_generator() -> AsyncGenerator[bytes, None]:
            llm_reply_chunks = []
            current_parent = question_node_id
            
            # Regex para detectar bloques ```json con la herramienta ejecutar_busqueda_web
            # Captura variantes: con/sin backticks, con/sin "arguments" anidado
            TOOL_CALL_PATTERN = re.compile(
                r'```(?:json)?\s*\{[^}]*"name"\s*:\s*"ejecutar_busqueda_web"[^}]*"(?:arguments|query)"\s*:\s*(?:\{[^}]*"query"\s*:\s*"([^"]+)"[^}]*\}|"([^"]+)")[^}]*\}[^`]*```',
                re.DOTALL | re.IGNORECASE
            )
            # Variante sin backticks (JSON directo en texto plano)
            TOOL_CALL_PATTERN_BARE = re.compile(
                r'\{\s*"name"\s*:\s*"ejecutar_busqueda_web"\s*,\s*"arguments"\s*:\s*\{\s*"query"\s*:\s*"([^"]+)"\s*\}\s*\}',
                re.DOTALL | re.IGNORECASE
            )

            try:
                # 1. Primer turno: acumular chunks SIN enviar al frontend todavía
                held_chunks = []
                async with client.stream("POST", f"{LLM_URL_BASE}/v1/chat/completions", json=body) as r:
                    buffer = ""
                    async for chunk in r.aiter_bytes():
                        held_chunks.append(chunk)
                        buffer += chunk.decode("utf-8", errors="ignore")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str == "[DONE]":
                                    continue
                                try:
                                    data_json = json.loads(data_str)
                                    choices = data_json.get("choices", [])
                                    if choices:
                                        content = choices[0].get("delta", {}).get("content", "")
                                        if content:
                                            llm_reply_chunks.append(content)
                                except Exception:
                                    pass
                
                # 2. Reconstruir texto completo y buscar tool_call emulada
                first_reply = "".join(llm_reply_chunks)
                
                tool_query = None
                match = TOOL_CALL_PATTERN.search(first_reply)
                if match:
                    tool_query = match.group(1) or match.group(2)
                else:
                    match_bare = TOOL_CALL_PATTERN_BARE.search(first_reply)
                    if match_bare:
                        tool_query = match_bare.group(1)
                
                if tool_query:
                    # ─── INTERCEPTOR ACTIVO: tool_call emulada detectada ───
                    logger.info("[Interceptor Tool] Detectada tool_call emulada para: '%s'", tool_query)
                    
                    # 2a. Ejecutar la búsqueda real contra SearXNG
                    search_result = await ejecutar_busqueda_web(tool_query)
                    logger.info("[Interceptor Tool] Resultados obtenidos (%d chars)", len(search_result))
                    
                    # 2b. Parsear resultados en estructura JSON para WebSearchStatus.tsx
                    parsed_results = []
                    for block in search_result.split("Resultado ")[1:]:
                        lines = block.strip().split("\n")
                        title = ""
                        url = ""
                        snippet = ""
                        for ln in lines:
                            ln = ln.strip()
                            if ln.startswith("- Título:"):
                                title = ln.replace("- Título:", "").strip()
                            elif ln.startswith("- URL:"):
                                url = ln.replace("- URL:", "").strip()
                            elif ln.startswith("- Contenido:"):
                                snippet = ln.replace("- Contenido:", "").strip()
                            elif ln.startswith("- Resumen:"):
                                snippet = ln.replace("- Resumen:", "").strip()
                        if title and url:
                            # Generar icono a partir del dominio
                            try:
                                domain = url.split("//")[1].split("/")[0]
                                icon = f"https://www.google.com/s2/favicons?sz=32&domain={domain}"
                            except Exception:
                                icon = ""
                            parsed_results.append({
                                "title": title,
                                "url": url,
                                "icon": icon,
                                "content": snippet
                            })
                    
                    # 2c. Cerrar cualquier bloque de reasoning previo del primer turno
                    close_reasoning_chunk = {
                        "choices": [{"index": 0, "delta": {"content": ""}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(close_reasoning_chunk)}\n\n".encode("utf-8")
                    
                    # 2d. Emitir el tag <web_search_results> como chunk SSE dedicado
                    #     El frontend intercepta este tag y lo usa como payload de hidratación
                    #     para WebSearchStatus.tsx. NO se renderiza como texto plano.
                    web_search_payload = {
                        "query": tool_query,
                        "results": parsed_results
                    }
                    ws_tag_content = f"<web_search_results>{json.dumps(web_search_payload, ensure_ascii=False)}</web_search_results>"
                    ws_chunk = {
                        "choices": [{"index": 0, "delta": {"content": ws_tag_content}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(ws_chunk)}\n\n".encode("utf-8")
                    
                    # 2e. Guardar nodo de la búsqueda interceptada en la base de datos
                    web_node_content = f"[BÚSQUEDA WEB DE FONDO]\n\n<contexto_web_busqueda>\n{search_result}\n</contexto_web_busqueda>"
                    web_embedding = None
                    try:
                        web_embedding = await embeddings_client.get_embedding(web_node_content)
                    except Exception:
                        pass
                    web_node = await db.insert_node(
                        content=web_node_content,
                        session_id=session_id,
                        parent_id=question_node_id,
                        node_type="CONOCIMIENTO",
                        embedding=web_embedding
                    )
                    await ws_broadcast({"event": "node_created", "node": web_node})
                    edge = await db.insert_edge(question_node_id, web_node["id"], 1.0)
                    await ws_broadcast({"event": "edge_created", "edge": edge})
                    current_parent = web_node["id"]
                    
                    # 2f. Segundo turno: reenviar al LLM con datos reales inyectados
                    local_messages = list(messages)
                    local_messages.append({"role": "assistant", "content": first_reply})
                    local_messages.append({
                        "role": "system",
                        "content": (
                            f"[SYSTEM: RESULTADO DE HERRAMIENTA ejecutar_busqueda_web]\n"
                            f"Se ejecutó la búsqueda web para '{tool_query}' en tiempo real contra SearXNG. "
                            f"Los datos que aparecen a continuación son REALES, VERIFICADOS y provienen de internet ahora mismo. "
                            f"NO son inventados ni aproximados.\n\n"
                            f"{search_result}\n\n"
                            f"INSTRUCCIÓN OBLIGATORIA:\n"
                            f"1. Usa EXCLUSIVAMENTE la información de los resultados anteriores para responder al usuario.\n"
                            f"2. NO inventes, NO supongas, NO alucines datos que no estén explícitamente en los resultados.\n"
                            f"3. NO repitas la llamada a la herramienta ejecutar_busqueda_web.\n"
                            f"4. Cita las fuentes (título y URL) cuando sea relevante.\n"
                            f"5. Responde de forma directa, concisa y en perfecto castellano (español)."
                        )
                    })
                    
                    second_body = dict(body)
                    second_body["messages"] = local_messages
                    second_body["stream"] = True
                    
                    logger.info("[Interceptor Tool] Lanzando segundo turno de streaming con datos reales...")
                    
                    second_llm_chunks = []
                    async with httpx.AsyncClient(timeout=60.0) as second_client:
                        async with second_client.stream("POST", f"{LLM_URL_BASE}/v1/chat/completions", json=second_body) as r2:
                            buffer2 = ""
                            async for chunk in r2.aiter_bytes():
                                buffer2 += chunk.decode("utf-8", errors="ignore")
                                while "\n" in buffer2:
                                    line, buffer2 = buffer2.split("\n", 1)
                                    line = line.strip()
                                    if line.startswith("data:"):
                                        data_str = line[5:].strip()
                                        if data_str == "[DONE]":
                                            continue
                                        try:
                                            data_json = json.loads(data_str)
                                            choices = data_json.get("choices", [])
                                            if choices:
                                                content = choices[0].get("delta", {}).get("content", "")
                                                if content:
                                                    second_llm_chunks.append(content)
                                        except Exception:
                                            pass
                                yield chunk
                    
                    # Guardar respuesta final del segundo turno
                    second_reply = "".join(second_llm_chunks)
                    if second_reply.strip():
                        final_node = await db.insert_node(
                            content=second_reply,
                            session_id=session_id,
                            parent_id=current_parent,
                            node_type="CONOCIMIENTO"
                        )
                        await ws_broadcast({"event": "node_created", "node": final_node})
                        edge = await db.insert_edge(current_parent, final_node["id"], 1.0)
                        await ws_broadcast({"event": "edge_created", "edge": edge})
                
                else:
                    # ─── SIN TOOL CALL: Emitir los chunks retenidos al frontend ───
                    for held_chunk in held_chunks:
                        yield held_chunk
                    
                    # Guardar primera respuesta en base de datos
                    if first_reply.strip():
                        reply_node = await db.insert_node(
                            content=first_reply,
                            session_id=session_id,
                            parent_id=current_parent,
                            node_type="CONOCIMIENTO"
                        )
                        await ws_broadcast({"event": "node_created", "node": reply_node})
                        edge = await db.insert_edge(current_parent, reply_node["id"], 1.0)
                        await ws_broadcast({"event": "edge_created", "edge": edge})
                        current_parent = reply_node["id"]
                        
                        # Detectar comandos CMD:
                        commands = extract_commands(first_reply)
                        if commands:
                            logger.info("[Proxy Stream /v1/chat/completions] Comandos detectados: %s", commands)
                            
                            info_msg = "\n\n*(Cerebro: Ejecutando comandos en consola...)*\n\n"
                            chunk_info = {
                                "choices": [{"index": 0, "delta": {"content": info_msg}, "finish_reason": None}]
                            }
                            yield f"data: {json.dumps(chunk_info)}\n\n".encode("utf-8")
                            
                            # Ejecutar comandos secuencialmente
                            cmd_outputs = []
                            for cmd in commands:
                                cmd_str = cmd.strip().replace("`", "").strip()
                                if not cmd_str:
                                    continue
                                output = await execute_system_command(cmd_str)
                                cmd_outputs.append(f"[Terminal] $ {cmd_str}\n{output}")
                                
                                # Registrar nodo de consola
                                node_content = f"[CONSOLA BASH] Comando: {cmd_str}\n\nResultado:\n{output}"
                                embedding = None
                                try:
                                    embedding = await embeddings_client.get_embedding(node_content)
                                except Exception:
                                    pass
                                cmd_node = await db.insert_node(
                                    content=node_content,
                                    session_id=session_id,
                                    parent_id=current_parent,
                                    node_type="CONOCIMIENTO",
                                    embedding=embedding
                                )
                                await ws_broadcast({"event": "node_created", "node": cmd_node})
                                edge = await db.insert_edge(current_parent, cmd_node["id"], 1.0)
                                await ws_broadcast({"event": "edge_created", "edge": edge})
                                current_parent = cmd_node["id"]
                                
                            # Segundo turno de streaming con la interpretación
                            combined_outputs = "\n\n".join(cmd_outputs)
                            
                            local_messages = list(messages)
                            local_messages.append({"role": "assistant", "content": first_reply})
                            local_messages.append({
                                "role": "system",
                                "content": (
                                    f"[SYSTEM: RESULTADO DE EJECUCIÓN]\n{combined_outputs}\n\n"
                                    f"Analiza este resultado y responde al usuario de forma final en español."
                                )
                            })
                            
                            second_body = dict(body)
                            second_body["messages"] = local_messages
                            second_body["stream"] = True
                            
                            logger.info("[Proxy Stream /v1/chat/completions] Iniciando segundo stream de interpretación...")
                            
                            second_llm_reply_chunks = []
                            async with httpx.AsyncClient(timeout=60.0) as second_client:
                                async with second_client.stream("POST", f"{LLM_URL_BASE}/v1/chat/completions", json=second_body) as r2:
                                    buffer2 = ""
                                    async for chunk in r2.aiter_bytes():
                                        buffer2 += chunk.decode("utf-8", errors="ignore")
                                        while "\n" in buffer2:
                                            line, buffer2 = buffer2.split("\n", 1)
                                            line = line.strip()
                                            if line.startswith("data:"):
                                                data_str = line[5:].strip()
                                                if data_str == "[DONE]":
                                                    continue
                                                try:
                                                    data_json = json.loads(data_str)
                                                    choices = data_json.get("choices", [])
                                                    if choices:
                                                        content = choices[0].get("delta", {}).get("content", "")
                                                        if content:
                                                            second_llm_reply_chunks.append(content)
                                                except Exception:
                                                    pass
                                        yield chunk
                                        
                            # Guardar respuesta final en base
                            second_reply = "".join(second_llm_reply_chunks)
                            if second_reply.strip():
                                final_reply_node = await db.insert_node(
                                    content=second_reply,
                                    session_id=session_id,
                                    parent_id=current_parent,
                                    node_type="CONOCIMIENTO"
                                )
                                await ws_broadcast({"event": "node_created", "node": final_reply_node})
                                edge = await db.insert_edge(current_parent, final_reply_node["id"], 1.0)
                                await ws_broadcast({"event": "edge_created", "edge": edge})
            
            except Exception as exc:
                logger.error("[Proxy] Error en streaming /v1/chat/completions: %s", exc)
            finally:
                await client.aclose()
                yield b"data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")


# ─── TERMINAL TOOL (LLM-accessible bash execution) ────────────────────────────

@app.get("/api/terminal/info")
async def terminal_info():
    """Returns OS information so the frontend can inject it into the tool description."""
    import platform
    uname = platform.uname()
    return {
        "system": uname.system,
        "node": uname.node,
        "release": uname.release,
        "machine": uname.machine,
        "distro": f"{uname.system} {uname.release}"
    }


@app.post("/api/terminal/run")
async def terminal_run(payload: dict):
    """Execute a bash command on the local machine via the LLM terminal tool.
    [DESHABILITADO] Retorna error indicando deshabilitación.
    """
    command = payload.get("command", "").strip()
    logger.warning("[Terminal Tool] Petición de ejecución bloqueada para comando: '%s'", command)
    return {
        "ok": False,
        "exitCode": 1,
        "output": "[Error] La ejecución de comandos de terminal está estrictamente deshabilitada en este servidor.",
        "executionMs": 0,
        "command": command
    }


@app.post("/api/code/run")
async def run_code(payload: dict):
    """Ejecuta un script de Python de forma local en la máquina y devuelve la salida (stdout + stderr)."""
    script = payload.get("script", "")
    if not script.strip():
        return {"ok": False, "message": "Script vacío"}
        
    logger.info("[Sandbox Python] Petición para ejecutar script Python de %d caracteres", len(script))
    
    import tempfile
    import os
    import time
    
    # Crear directorio tmp si no existe
    tmp_dir = BASE_DIR / "storage" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    with tempfile.NamedTemporaryFile(suffix=".py", dir=tmp_dir, delete=False) as f:
        f.write(script.encode("utf-8"))
        temp_file_path = f.name
        
    t0 = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            "python", temp_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            execution_ms = int((time.time() - t0) * 1000)
            stdout_str = stdout.decode("utf-8", errors="ignore")
            stderr_str = stderr.decode("utf-8", errors="ignore")
            ok = (proc.returncode == 0)
            
            return {
                "ok": True,
                "exitCode": proc.returncode,
                "output": stdout_str,
                "error": stderr_str if not ok else "",
                "executionMs": execution_ms
            }
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return {"ok": False, "message": "Timeout de ejecución (límite 10s)"}
    except Exception as e:
        return {"ok": False, "message": f"Error al iniciar subproceso: {e}"}
    finally:
        # Limpiar archivo temporal
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


# ─── Servidor y Ruteador Inteligente para la Interfaz (llama-ui + claude-mem) ───
STATIC_UI_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
VIEWER_UI_DIR = Path(__file__).resolve().parent.parent.parent / "references" / "claude-mem" / "plugin" / "ui"

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def catch_all_router(request: Request, path_name: str):
    """Ruteador inteligente y unificado.
    
    1. Si la ruta está vacía (raíz `/`), sirve el chat index.html.
    2. Si la ruta es exactamente 'viewer' o 'viewer.html', sirve el visualizador.
    3. Si el recurso solicitado existe físicamente en el visualizador, lo sirve localmente.
    4. Si el recurso solicitado existe físicamente en el chat web, lo sirve localmente.
    5. De lo contrario, hace proxy reverso transparente hacia http://127.0.0.1:8080.
    """
    # Si es la raíz, servir index.html del chat de Svelte
    if not path_name:
        index_path = STATIC_UI_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
            
    # Si es 'viewer' o 'viewer.html', servir viewer.html del visualizador
    if path_name in ("viewer", "viewer.html"):
        viewer_path = VIEWER_UI_DIR / "viewer.html"
        if viewer_path.exists():
            return FileResponse(viewer_path)

    # Comprobar si el archivo existe físicamente en la carpeta del visualizador (viewer-bundle.js, logos, etc.)
    viewer_file = VIEWER_UI_DIR / path_name
    if viewer_file.exists() and viewer_file.is_file():
        return FileResponse(viewer_file)

    # Comprobar si el archivo existe físicamente en la carpeta del chat
    chat_file = STATIC_UI_DIR / path_name
    if chat_file.exists() and chat_file.is_file():
        return FileResponse(chat_file)
        
    # De lo contrario, hacer proxy reverso a http://127.0.0.1:8080 (llama-server)
    logger.debug("[Router Comodín] Haciendo proxy reverso a :8080 para: %s %s", request.method, path_name)
    
    method = request.method
    params = dict(request.query_params)
    headers = dict(request.headers)
    
    # Quitar cabeceras conflictivas de Starlette
    if "host" in headers:
        headers.pop("host")
    for h in ["content-length", "content-encoding", "transfer-encoding"]:
        headers.pop(h, None)
        
    body = await request.body()
    
    client = httpx.AsyncClient(timeout=15.0)
    try:
        resp = await client.request(
            method,
            f"{LLM_URL_BASE}/{path_name}",
            params=params,
            headers=headers,
            content=body,
            follow_redirects=True
        )
        await client.aclose()
        
        # Limpiar cabeceras de respuesta
        resp_headers = dict(resp.headers)
        for h in ["content-length", "content-encoding", "transfer-encoding"]:
            resp_headers.pop(h, None)
            
        return Response(content=resp.content, status_code=resp.status_code, headers=resp_headers)
    except Exception as exc:
        await client.aclose()
        logger.error("[Router Comodín] Error en reenvío de recurso %s a :8080: %s", path_name, exc)
        return Response(content=f"Proxy Error: {str(exc)}", status_code=502)


# ─── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _config = load_config()
    host = _config["core"]["host"]
    port = _config["core"]["port"]

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )

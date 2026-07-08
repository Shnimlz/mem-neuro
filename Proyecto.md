# 🧠 Proyecto.md — Cerebro Autónomo Unificado (mem-neuro)

> **Especificación Oficial de Arquitectura**
> Versión 3.0 (Living Document)

---

# 📖 PRÓLOGO

## ¿Qué es este proyecto?

**Cerebro Autónomo Unificado** no es un chatbot. No es un sistema RAG convencional. No es un wrapper para un LLM.

Es un **Motor Cognitivo Persistente** cuyo propósito es situarse entre un Modelo de Lenguaje y el conocimiento disponible, actuando como una capa de razonamiento, memoria y recuperación de información.

El LLM deja de ser el centro del sistema. El centro del sistema pasa a ser el **Motor Cognitivo**. El modelo de lenguaje se convierte únicamente en un componente especializado en comprensión y generación de lenguaje natural.

Toda la adquisición, organización, recuperación y priorización del conocimiento pertenece al Cerebro Autónomo.

---

# 🎯 OBJETIVOS

El proyecto persigue cinco objetivos fundamentales:

### 1. Persistencia
El conocimiento no desaparece cuando termina una conversación. Cada interacción genera conocimiento persistente dentro del Grafo Cognitivo.

### 2. Memoria
El sistema debe recordar. No únicamente almacenar texto; debe recordar relaciones, contexto, errores, correcciones, patrones y experiencias. La memoria constituye una fuente de conocimiento tan importante como Internet.

### 3. Recuperación Inteligente
Cuando el sistema necesita información, no debe preguntar inmediatamente al LLM. Debe responder primero: *¿Ya conozco esto?*. Si la memoria contiene suficiente evidencia, la búsqueda web puede omitirse. Si la memoria no basta, se planifica una estrategia de recuperación de conocimiento.

### 4. Razonamiento
La búsqueda nunca debe ejecutarse de forma automática. Cada recuperación de información debe ser consecuencia de una planificación. El sistema debe decidir si necesita buscar, dónde buscar, cuánto buscar, cuándo detenerse, qué fuentes priorizar y qué evidencia descartar.

### 5. Construcción de Conocimiento
El objetivo del sistema no es recuperar documentos, sino construir una representación coherente del conocimiento que posteriormente utilizará el Modelo de Lenguaje para generar la respuesta final.

---

# 💡 FILOSOFÍA Y PRINCIPIO FUNDAMENTAL

> [!IMPORTANT]
> **El LLM nunca debe ser considerado la fuente principal del conocimiento.**
> El conocimiento proviene de múltiples orígenes. El LLM únicamente razona sobre dicho conocimiento y lo expresa en lenguaje natural.

Las fuentes de conocimiento incluyen, entre otras:
* Memoria persistente y Grafo Cognitivo.
* SQLite + `sqlite-vec`.
* Browserless.
* Documentación oficial y APIs.
* GitHub.
* Sistemas MCP.
* Archivos locales, bases de datos y servicios externos.

Todas estas fuentes son equivalentes desde el punto de vista arquitectónico. Ninguna tiene prioridad absoluta. Será responsabilidad del Motor Cognitivo determinar cuáles consultar y cómo combinar su evidencia.

> [!TIP]
> **El sistema no busca información. El sistema construye conocimiento.**

---

# 🏛️ ESPECIFICACIÓN TÉCNICA Y SECCIONES DE ARQUITECTURA

## 1. Arquitectura del Sistema e IPC

El sistema opera como un único hilo cognitivo local a través de una arquitectura de microservicios interconectados mediante un canal de comunicación de baja latencia. El núcleo central (`brain_core`) actúa como el orquestador del conocimiento.

```
[llama-vscode-chat] (Extensión)
       │  (HTTP / Unix Socket)
       ▼
 [brain_core] (FastAPI) ◄──────► [storage/brain.db] (SQLite + sqlite-vec)
       │  (WebSockets)
       ▼
  [claude-mem] (Visualizador)
```

### Mecanismo de Comunicación (IPC)
El componente `brain_core/main.py` levanta un servidor **FastAPI / Uvicorn** expuesto únicamente en entorno local. La comunicación se realiza mediante peticiones HTTP asíncronas para el procesamiento de texto y **WebSockets** para la actualización del grafo visual en tiempo real.

#### Endpoints Principales del Core:
* `POST /process`: Recibe el mensaje del usuario, el `session_id` y el ID del nodo anterior. Devuelve el prompt enriquecido.
* `GET /graph`: Devuelve el estado actual de la red neuronal (nodos y aristas) en formato JSON para el renderizado.
* `POST /scrape`: Ingesta manual/sincrónica de una URL en el almacén de caché.

---

## 2. Base de Datos Unificada y Persistencia (0% RAM Permanente)

Toda la persistencia (vectores, texto, relaciones y metadatos) se centraliza en **SQLite**, aprovechando la extensión **`sqlite-vec`** para búsquedas vectoriales nativas mediante mapeo de memoria virtual (`mmap`), garantizando un consumo de memoria RAM cercano a cero.

### Esquema de Base de Datos (`storage/brain.db`)

```sql
-- Tabla principal de neuronas (Nodos cognitivos)
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    parent_id TEXT,              -- Mantiene la estructura del árbol de conversación
    session_id TEXT,             -- Identifica el hilo/ventana de origen
    content TEXT,                -- Contenido limpio del prompt + respuesta
    type TEXT,                   -- 'CONOCIMIENTO', 'ERROR_APRENDIDO', 'BIFURCACION_FIX'
    created_at INTEGER,          -- Timestamp epoch
    FOREIGN KEY(parent_id) REFERENCES nodes(id)
);

-- Tabla de sinapsis (Aristas/Conexiones semánticas)
CREATE TABLE edges (
    source_id TEXT,
    target_id TEXT,
    weight REAL DEFAULT 1.0,     -- Fuerza de la relación semántica
    PRIMARY KEY (source_id, target_id),
    FOREIGN KEY(source_id) REFERENCES nodes(id),
    FOREIGN KEY(target_id) REFERENCES nodes(id)
);

-- Tabla virtual para indexación y búsqueda vectorial
CREATE VIRTUAL TABLE vec_embeddings USING vec0(
    embedding float[1024]        -- Dimensión del modelo bge-m3
);
```

---

## 3. Manejo del Hilo de Conversación y Mecanismo de *Split*

El flujo de datos se comporta como un **árbol de conversación dinámico** capaz de gestionar múltiples ramificaciones si el usuario reabre un debate pasado. Cada hilo queda delimitado por `session_id`.

* **Trazabilidad Temporal:** El campo `parent_id` en la tabla de nodos preserva la jerarquía exacta de la sesión actual.
* **Asociaciones Semánticas:** La tabla `edges` conecta nodos que comparten alta similitud semántica.

### El Mecanismo de Bifurcación ante Errores
Cuando el sistema detecta que una solución previa falló, ejecuta una cirugía en caliente sobre la base de datos:
1. El nodo original que contiene la instrucción errónea muta su estado a `type = 'ERROR_APRENDIDO'`.
2. Se genera un nuevo nodo hijo de tipo `BIFURCACION_FIX` con la corrección.
3. Se crea una arista (`edge`) entre ambos con un peso prioritario. La próxima vez que la búsqueda apunte al nodo erróneo, el core redirigirá el contexto directamente hacia la solución válida.

---

## 4. Metacognición y Clasificación de Intenciones

El sistema utiliza **DeepSeek-R1** en un modo de inferencia rápido y de bajo consumo de tokens para clasificar la intención del usuario.

Antes de procesar la búsqueda, el core realiza una llamada ligera al LLM:
```
Clasifica el siguiente mensaje del usuario en una de estas categorías exclusivas:
['consulta', 'corrección_de_error', 'ingesta_web'].
Responde únicamente con la palabra de la categoría.
```

Si el mensaje se clasifica como `corrección_de_error`, el sistema activa de forma automatizada el **Mecanismo de Split** sobre el último ID registrado en el hilo de la conversación actual.

---

## 5. Estrategia de Scraping e Ingesta Web Inteligente

El módulo `web_scraper.py` implementa una estrategia modular para expandir el conocimiento cuando los recuerdos locales no ofrecen suficiente confianza semántica.

* **Configuración por Orígenes:** Un archivo `sources.json` mapea las reglas de extracción, selectores CSS/XPath y cabeceras para portales críticos.
* **Caché de Ingesta:** Las URLs raspadas se almacenan en una tabla de caché local dentro de SQLite con un tiempo de vida (TTL) de 7 días.
* **Anti-Saturación:** El texto extraído de la web se limpia de elementos innecesarios (scripts, navs, footers), se convierte a markdown y se trunca a 2000 caracteres antes de insertarse.

---

## 6. Configuración Centralizada (`config.yaml`)

Todos los parámetros operativos del sistema se gestionan desde un único archivo de configuración:

```yaml
llm:
  server_url: "http://127.0.0.1:8080"        # DeepSeek-R1 (chat)
  max_output_tokens: 4096

embeddings:
  server_url: "http://127.0.0.1:8081"        # Instancia dedicada
  model: "bge-m3"
  dimension: 1024

database:
  path: "./storage/brain.db"
  similarity_threshold: 0.40

scraping:
  enabled: true
  cache_ttl: 604800  # 7 días
  max_content_length: 2000

search:
  provider: "bing"                           # bing, duckduckgo, searxng
  browserless_url: "http://127.0.0.1:3000"
  max_queries: 2
  max_results_per_query: 5

frontend:
  refresh_interval: 2000

backup:
  enabled: true
  path: "./storage/backups/"
  keep_last: 10
```

---

## 7. Resiliencia y Gestión de Fallos

* **Timeouts Estrictos:** Conexiones al servidor local de inferencia y peticiones de red externa con límites de tiempo.
* **Fallback Semántico:** Si el servidor de embeddings local no responde, el sistema conmuta automáticamente a una búsqueda clásica por palabras clave (TF-IDF sobre SQLite FTS5).
* **Trazabilidad de Errores:** Archivo persistente `storage/cerebro.log` que registra de forma detallada excepciones y fallos de comunicación.

---

## 8. Estructura de Archivos del Monorepositorio

```text
cerebro-unico-ia/
├── config.yaml                      # Configuración global del sistema
├── Proyecto.md                      # Especificación arquitectónica (este archivo)
├── storage/                         # Archivos persistentes
│   ├── brain.db                     # SQLite unificado (Nodos, Aristas, Vectores)
│   ├── backups/                     # Copias periódicas de brain.db
│   └── cerebro.log                  # Registro de depuración
│
├── cerebro_unificado/
│   ├── backend/                     # Motor Cognitivo (Python)
│   │   ├── main.py                  # API y orquestador del ciclo de pensamiento
│   │   ├── search_orchestrator.py   # Orquestación de Fuentes de Conocimiento
│   │   ├── knowledge_planner.py     # Planificación Cognitiva
│   │   ├── database.py              # Operaciones de persistencia WAL
│   │   └── web_scraper.py           # Ingesta, limpieza y caché
│   │
│   └── frontend/                    # Visualizador Premium (Svelte 5 Kit)
```

---

## 9. Aislamiento de Instancias de Inferencia (Chat vs. Embeddings)

Para garantizar un rendimiento y precisión óptimos, se configuran dos instancias independientes del backend de inferencia:

| Instancia | Puerto | Modelo | Flags relevantes |
|---|---|---|---|
| Chat / Razonamiento | `8080` | DeepSeek-R1 (el actual) | — |
| Embeddings | `8081` | Modelo dedicado y liviano | `--embeddings --pooling mean` |

* **Elección de modelo:** Se prioriza un modelo multilingüe (`bge-m3`, `multilingual-e5`) para cubrir la mezcla de lenguajes técnico y conversacional.
* **Costo en VRAM:** El modelo de embeddings liviano consume menos de 1GB de VRAM, permitiendo la convivencia en hardware común.
* **`similarity_threshold`:** Se calibra empíricamente una vez elegido el modelo de embeddings.

---

## 10. Concurrencia y Manejo de Sesiones

SQLite con múltiples escritores concurrentes requiere modo **WAL** explícito para evitar errores de "database is locked":

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
```

### Identificador de Sesión (`session_id`)
Un UUID generado al abrir cada panel del visualizador viaja con cada petición para evitar la superposición de jerarquías de conversación entre ventanas concurrentes.

---

## 11. Ciclo de Vida de los Datos: Poda y Respaldo

### Consolidación y Olvido
El sistema ejecuta periódicamente una tarea en segundo plano que:
1. Identifica nodos `CONOCIMIENTO` antiguos con baja centralidad (sin conexiones entrantes) y baja recurrencia de acceso.
2. Los consolida en un único nodo superior en lugar de eliminarlos, preservando la trazabilidad.
3. **Nunca poda** nodos `ERROR_APRENDIDO` o `BIFURCACION_FIX`, al ser el conocimiento de mayor valor adaptativo del sistema.

### Respaldo
Copia periódica en caliente (`storage/backups/brain-YYYYMMDD.db`), rotando las últimas `keep_last` copias antes de cada sesión de poda.

---

## 12. Robustez del Clasificador de Intención

### Manejo de Fallos de Clasificación
Si la llamada al clasificador hace timeout o el LLM responde con datos corruptos, el core asume por defecto la categoría `consulta` para no bloquear el chat.

### Pre-filtro Híbrido (Latencia)
Se antepone un filtro rápido por palabras clave (ej. "error", "rompió", "fallo", "no funcionó") antes de delegar la clasificación al modelo grande, reduciendo significativamente la latencia percibida.

---

## 13. Capa Visual: Actualización y Edición Manual

### Mecanismo de Actualización
La sincronización es reactiva (push, no poll): `brain_core` emite un evento WebSocket inmediatamente después de escribir en `nodes` o `edges`, y el frontend repinta solo ante ese evento.

### Edición y Corrección Manual
* `PATCH /graph/node/{id}`: Permite modificar el `type` de un nodo o fusionarlo.
* `DELETE /graph/edge/{source_id}/{target_id}`: Permite eliminar conexiones erróneas.

---

## 14. Instalación, Servicio Persistente y Seguridad de Red

### Instalación de `sqlite-vec`
Carga del módulo dinámico compiled `vec0` usando `sqlite3.enable_load_extension` en Python.

### Servicio Persistente (`systemd --user`)
Para garantizar la persistencia del backend al arrancar el entorno:
```ini
# ~/.config/systemd/user/cerebro-brain-core.service
[Unit]
Description=Cerebro Autónomo Unificado - Brain Core
After=network.target

[Service]
WorkingDirectory=%h/mem-neuro/cerebro_unificado/backend
ExecStart=/usr/bin/python3 main.py
Restart=on-failure

[Install]
WantedBy=default.target
```
Activación: `systemctl --user enable --now cerebro-brain-core.service`

### Seguridad de Red
El core y las instancias de inferencia se enlazan explícitamente a `127.0.0.1` para evitar su exposición a la red externa.

---

## 15. Orden de Implementación Sugerido

### Decisión Previa: ¿Backend propio o fork del worker de `claude-mem`?
Se optó por el desarrollo del backend propio en Python para proteger la flexibilidad del esquema SQLite, el aislamiento de procesos y el orquestador unificado de scraping y embeddings.

### Fases de Construcción
1. **`brain_core` + SQLite base**: Estructura CRUD inicial de nodos y aristas con FTS5.
2. **Embeddings**: Integración de la instancia dedicada de embeddings y la extensión `sqlite-vec`.
3. **Extensión de VS Code**: Interceptor del chat del desarrollador en el proxy HTTP.
4. **Capa visual**: Comunicación reactiva vía WebSockets con el frontend.
5. **Scraping e Ingesta Avanzada**: Pipeline modular de adquisición cognitiva de conocimiento.

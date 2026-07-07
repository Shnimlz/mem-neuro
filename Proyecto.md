# 🧠 Proyecto.md: Cerebro Autónomo Unificado

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

*(Ver Sección 9 para el servidor de embeddings dedicado, que corre en paralelo al servidor de chat.)*

### Mecanismo de Comunicación (IPC)

El componente `brain_core/main.py` levanta un servidor **FastAPI / Uvicorn** expuesto únicamente en entorno local. La comunicación se realiza mediante peticiones HTTP asíncronas para el procesamiento de texto y **WebSockets** para la actualización del grafo visual en tiempo real sin saturar el disco con lecturas repetitivas.

#### Endpoints Principales del Core:

* `POST /process`: Recibe el mensaje del usuario, el `session_id` y el ID del nodo anterior. Devuelve el prompt enriquecido con contexto histórico y el nuevo ID de tarea.
* `GET /graph`: Devuelve el estado actual de la red neuronal (nodos y aristas) en formato JSON para el renderizado.
* `POST /scrape`: Endpoint manual u opcional para forzar la indexación de una URL específica.
* Ver Sección 13 para los endpoints de corrección manual del grafo.

---

## 2. Base de Datos Unificada y Persistencia (0% RAM Permanente)

Se elimina el uso de archivos JSON redundantes para el almacenamiento del grafo. Toda la persistencia (vectores, texto, relaciones y metadatos) se centraliza en **SQLite**, aprovechando la extensión **`sqlite-vec`** para búsquedas vectoriales nativas mediante mapeo de memoria virtual (`mmap`), garantizando un consumo de memoria RAM cercano a cero.

> `sqlite-vec` reemplaza a `sqlite-vss` en este diseño: su propio creador dejó de desarrollarlo activamente en favor de `sqlite-vec`, que además está escrito en C puro sin dependencias (a diferencia de `sqlite-vss`, que depende de Faiss), por lo que compila sin complicaciones en CachyOS.

### Esquema de Base de Datos (`storage/brain.db`)

```sql
-- Tabla principal de neuronas (Nodos cognitivos)
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    parent_id TEXT,              -- Mantiene la estructura del árbol de conversación
    session_id TEXT,             -- Identifica el hilo/ventana de origen (Sección 10)
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
    embedding float[1024]         -- Ejemplo con bge-m3; ajustar a la dimensión real del modelo elegido (Sección 9)
);
```

Ver Sección 10 para la configuración de concurrencia (modo WAL) necesaria dado que `brain_core` lee y escribe esta base de forma asíncrona.

---

## 3. Manejo del Hilo de Conversación y Mecanismo de *Split*

El flujo de datos no es lineal; se comporta como un **árbol de conversación dinámico** capaz de gestionar múltiples ramificaciones si el usuario reabre un debate pasado. Cada hilo queda delimitado por `session_id` (Sección 10) para que ventanas o paneles concurrentes no se crucen entre sí.

* **Trazabilidad Temporal:** El campo `parent_id` en la tabla de nodos preserva la jerarquía exacta de la sesión actual del desarrollador.
* **Asociaciones Semánticas:** La tabla `edges` se utiliza para conectar nodos que, aunque pertenezcan a chats o momentos distintos, comparten una alta similitud vectorial.

### El Mecanismo de Bifurcación ante Errores

Cuando el sistema detecta que una solución previa falló, ejecuta una cirugía en caliente sobre el disco duro:

1. El nodo original que contiene el código o la instrucción errónea muta su estado a `type = 'ERROR_APRENDIDO'`.
2. Se genera un nuevo nodo hijo de tipo `BIFURCACION_FIX` con la corrección.
3. Se crea una arista (`edge`) entre ambos con un peso (`weight`) prioritario. La próxima vez que el buscador vectorial apunte al nodo erróneo, el core interceptará la lectura y redirigirá el contexto directamente hacia la solución válida.

Si esta bifurcación se dispara por una clasificación incorrecta, puede corregirse manualmente (Sección 13).

---

## 4. Metacognición y Clasificación de Intenciones

Para evitar la fragilidad del filtrado por palabras clave rígidas, el sistema utiliza el propio **DeepSeek-R1** en un modo de inferencia rápido y de bajo consumo de tokens para clasificar la intención del usuario. Ver Sección 12 para el manejo de fallos de esta clasificación y una optimización de latencia mediante un pre-filtro híbrido.

Antes de procesar la búsqueda, el core realiza una llamada ligera al LLM con un prompt del sistema estructurado:

```
Clasifica el siguiente mensaje del usuario en una de estas categorías exclusivas:
['consulta', 'corrección_de_error', 'ingesta_web'].
Responde únicamente con la palabra de la categoría.
```

Si el mensaje se clasifica como `corrección_de_error`, el sistema activa de forma automatizada el **Mecanismo de Split** sobre el último ID registrado en el hilo de la conversación actual (dentro de la misma `session_id`).

---

## 5. Estrategia de Scraping e Ingesta Web Inteligente

El módulo `web_scraper.py` implementa una estrategia modular y resiliente para expandir el conocimiento de la IA cuando los recuerdos locales no ofrecen una solución con suficiente confianza semántica.

* **Configuración por Orígenes:** Un archivo `sources.json` mapea las reglas de extracción, selectores CSS/XPath y cabeceras para portales críticos como Arch Wiki o documentaciones oficiales.
* **Caché de Ingesta:** Para proteger el ancho de banda y evitar penalizaciones de red, las URLs raspadas se almacenan en una tabla de caché local dentro de SQLite con un tiempo de vida (TTL) predeterminado de 7 días.
* **Optimización de Espacio (Anti-Saturación):** El contenido de texto plano extraído de la web se trunca a un máximo de 2000 caracteres o se pre-resume utilizando el LLM antes de ser vectorizado e insertado en el SSD, evitando el crecimiento desmedido de la base de datos.

---

## 6. Configuración Centralizada (`config.yaml`)

Todos los parámetros operativos del sistema se gestionan desde un único archivo de configuración en la raíz del espacio de trabajo. Tanto el núcleo de Python como los subproyectos de Node.js se alinean bajo estas variables:

```yaml
llm:
  server_url: "http://127.0.0.1:8080"        # DeepSeek-R1 (chat)
  max_output_tokens: 4096

embeddings:                                   # Sección 9
  server_url: "http://127.0.0.1:8081"        # Instancia dedicada, modelo liviano
  model: "bge-m3"                             # Ajustar según el modelo elegido
  dimension: 1024                             # Debe coincidir con vec_embeddings (Sección 2)

database:
  path: "./storage/brain.db"
  similarity_threshold: 0.40                  # Recalibrar empíricamente según el modelo de embeddings (Sección 9)

scraping:
  enabled: true
  cache_ttl: 604800  # 7 días en segundos
  max_content_length: 2000

frontend:
  refresh_interval: 2000  # Poll de respaldo — la actualización primaria es vía push por WebSocket (Sección 13)

backup:                                       # Sección 11
  enabled: true
  path: "./storage/backups/"
  keep_last: 10
```

---

## 7. Resiliencia y Gestión de Fallos

El sistema está diseñado para fallar de manera elegante sin degradar por completo la experiencia de desarrollo en VS Code:

* **Timeouts Estrictos:** Todas las conexiones con el servidor local de inferencia y las peticiones de red externa cuentan con límites de tiempo dedicados.
* **Fallback Semántico:** Si el servidor de embeddings local (Sección 9) no responde o queda inaccesible, el sistema desactiva temporalmente la búsqueda vectorial en el SSD y conmuta automáticamente a un algoritmo de búsqueda de texto clásico (TF-IDF sobre SQLite FTS5).
* **Trazabilidad de Errores:** Se habilita un archivo persistente `storage/cerebro.log` que registra de forma detallada cualquier fallo de comunicación o excepción del sistema de archivos para su depuración técnica.
* **Continuidad de Datos:** Ver Sección 11 para la política de poda y respaldo de `storage/brain.db`.

---

## 8. Estructura de Archivos del Monorepositorio

```text
cerebro-unico-ia/
├── config.yaml                      # Configuración global del sistema
├── storage/                         # Archivos persistentes en el SSD
│   ├── brain.db                     # SQLite unificado (Nodos, Aristas, Vectores)
│   ├── backups/                     # Copias periódicas de brain.db (Sección 11)
│   └── cerebro.log                  # Registro de depuración del sistema
│
├── brain_core/                      # El núcleo cognitivo (Motor en Python)
│   ├── main.py                      # API FastAPI y orquestador del ciclo de pensamiento
│   ├── database.py                  # Consultas SQL, inserciones y lógica de sqlite-vec
│   ├── web_scraper.py               # Ingesta, limpieza y caché de fuentes web
│   ├── sources.json                 # Reglas de extracción por origen (Sección 5)
│   └── requirements.txt             # Dependencias de Python (fastapi, uvicorn, requests, bs4)
│
├── claude-mem/                      # Capa visual — basada en thedotmack/claude-mem (Apache 2.0)
│   ├── package.json                 # Ver Sección 15: decisión sobre forkear solo el frontend o también el worker
│   └── src/
│       └── index.ts                 # Renderizador alimentado por el WebSocket del core
│
└── llama-vscode-chat/                # Receptor nativo — confirmar si la base es mbeps/llama-vscode-chat
    ├── package.json                  # o la extensión completa ggml-org/llama.vscode (alcance muy distinto)
    └── src/
        └── llama-provider.ts        # Interceptor del prompt que conecta con FastAPI (/process)
```

---

## 9. Aislamiento de Instancias de Inferencia (Chat vs. Embeddings)

DeepSeek-R1 es un modelo conversacional/de razonamiento, no un modelo de embeddings: los vectores obtenidos por pooling sobre un modelo de chat rinden peor en búsqueda semántica que los de un modelo entrenado específicamente para ese fin. Además, `llama-server` solo expone el endpoint de embeddings si se levanta explícitamente con `--embeddings` y un `--pooling` definido — no alcanza con pegarle al endpoint del servidor de chat existente.

### Arquitectura de Dos Servidores

| Instancia | Puerto | Modelo | Flags relevantes |
|---|---|---|---|
| Chat | `8080` | DeepSeek-R1 (el actual) | — |
| Embeddings | `8081` | Modelo dedicado y liviano | `--embeddings --pooling mean` |

* **Elección de modelo:** dado que el contenido mezcla español (mensajes del usuario) e inglés (logs, errores, documentación técnica), se prioriza un modelo **multilingüe** (ej. `bge-m3`, `multilingual-e5`) sobre uno centrado solo en inglés.
* **Costo en VRAM:** los modelos de embeddings decentes pesan entre 100MB y 1GB — conviven sin problema junto a DeepSeek-R1 en una GPU de 8GB.
* **Dimensión del vector:** `vec_embeddings` (Sección 2) debe declarar la dimensión exacta de salida del modelo elegido, no un número arbitrario.
* **`similarity_threshold`:** el valor de `config.yaml` (Sección 6) depende enteramente del modelo — se recalibra empíricamente una vez elegido, no se asume en 0.40.

---

## 10. Concurrencia y Manejo de Sesiones

SQLite con múltiples escritores concurrentes (chat, scraping y lecturas del WebSocket ocurriendo a la vez sobre `brain_core`) requiere modo **WAL** explícito para evitar errores de "database is locked":

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
```

### Identificador de Sesión (`session_id`)

El diseño original asumía un único hilo de conversación lineal. Si se abren varias ventanas de VS Code (o varios paneles de chat) al mismo tiempo, sus respectivos `idNodoAnterior` pueden cruzarse entre sí. Se agrega un `session_id` (UUID generado por `llama-vscode-chat` al abrir cada panel) que viaja junto con cada llamada a `POST /process`, de forma que cada hilo mantenga su propia cadena de `parent_id` sin interferir con las demás.

---

## 11. Ciclo de Vida de los Datos: Poda y Respaldo

### Consolidación y Olvido

Sin un mecanismo de poda, `brain.db` crece sin límite. En línea con la metáfora del sistema, se incorpora una tarea periódica (semanal, vía cron o al arranque de `main.py`) que:

1. Identifica nodos `CONOCIMIENTO` antiguos con baja centralidad (pocas o ninguna arista entrante) y baja recurrencia de acceso.
2. Los consolida en un único nodo de nivel superior en lugar de eliminarlos, preservando la trazabilidad sin dejar crecer la base indefinidamente.
3. Nunca poda nodos `ERROR_APRENDIDO` ni `BIFURCACION_FIX`, dado que son el conocimiento de mayor valor del sistema.

### Respaldo

`storage/brain.db` es un punto único de fallo para meses de conocimiento acumulado. Se agrega una copia periódica (`storage/backups/brain-YYYYMMDD.db`, rotando las últimas `keep_last` copias definidas en `config.yaml`) antes de cada sesión de poda.

---

## 12. Robustez del Clasificador de Intención

### Manejo de Fallos de Clasificación

Si la llamada de clasificación (Sección 4) hace timeout o el LLM responde algo fuera de `['consulta', 'corrección_de_error', 'ingesta_web']`, el sistema asume por defecto `consulta` — nunca bloquea la respuesta al usuario esperando una clasificación válida.

### Pre-filtro Híbrido (Latencia)

Clasificar con DeepSeek-R1 en **cada mensaje** agrega una llamada extra al LLM grande antes de poder responder, costosa en hardware local. Se antepone un filtro rápido por palabras clave ("error", "no funcionó", "rompió", "fallo", etc.) como primera pasada; solo cuando el resultado es ambiguo se escala la clasificación al LLM. Esto reduce la latencia percibida en el caso común sin perder la robustez semántica en los casos difíciles.

---

## 13. Capa Visual: Actualización y Edición Manual

### Mecanismo de Actualización

La actualización del grafo es **push, no poll**: `brain_core` emite un evento por WebSocket inmediatamente después de cada escritura en `nodes`/`edges`, y `claude-mem` repinta solo ante ese evento. El `refresh_interval` de `config.yaml` (Sección 6) queda como mecanismo de respaldo (reconexión/resincronización), no como disparador principal.

### Edición y Corrección Manual

Dado que el Mecanismo de Split (Sección 3) puede dispararse por una clasificación incorrecta, se agrega un endpoint mínimo de corrección:

* `PATCH /graph/node/{id}`: permite cambiar el `type` de un nodo o fusionarlo con otro manualmente.
* `DELETE /graph/edge/{source_id}/{target_id}`: permite eliminar una arista creada por error.

Sin esto, un error del clasificador queda grabado permanentemente en la estructura del grafo sin forma de corregirlo.

---

## 14. Instalación, Servicio Persistente y Seguridad de Red

### Instalación de `sqlite-vec`

Al estar escrito en C puro sin dependencias, compila directamente en CachyOS sin la complejidad de build de Faiss que tenía `sqlite-vss`. Se descarga o compila el binario `vec0` y se carga vía `.load ./vec0` (o su equivalente en `database.py` mediante `sqlite3.enable_load_extension`).

### Servicio Persistente (`systemd --user`)

Para que `brain_core` esté siempre disponible cuando se abre VS Code (y no falle silenciosamente si no se arrancó a mano), se define como servicio de usuario:

```ini
# ~/.config/systemd/user/cerebro-brain-core.service
[Unit]
Description=Cerebro Autónomo Unificado - Brain Core
After=network.target

[Service]
WorkingDirectory=%h/cerebro-unico-ia/brain_core
ExecStart=/usr/bin/python3 main.py
Restart=on-failure

[Install]
WantedBy=default.target
```

Activación: `systemctl --user enable --now cerebro-brain-core.service`

### Seguridad de Red

Tanto `brain_core` (FastAPI/Uvicorn) como ambas instancias de `llama-server` (Sección 9) deben enlazar explícitamente a `127.0.0.1`, nunca a `0.0.0.0`, para evitar exponer el entorno de desarrollo local a la red LAN sin querer.

---

## 15. Orden de Implementación Sugerido

### Decisión Previa: ¿Backend propio o fork del worker de `claude-mem`?

Antes de escribir `brain_core` desde cero, vale la pena evaluar si conviene forkear también el *worker* real de `claude-mem` (no solo su frontend visual) y agregarle un proveedor de IA tipo "openai-compatible" apuntando al `llama-server` de chat — hoy `claude-mem` solo soporta Claude, Gemini y OpenRouter como proveedores nativamente, así que esto requeriría un parche propio, pero ahorraría reimplementar el sistema de tres niveles, el esquema SQLite y la interfaz web que ese proyecto ya trae resueltos. Si se opta por seguir con el backend propio en Python (Secciones 1-8), esta decisión queda documentada aquí como descartada intencionalmente, no por omisión.

### Fases de Construcción

Con cinco piezas moviéndose en paralelo (core, base de datos, scraper, fork de `claude-mem`, fork de `llama-vscode-chat`), se recomienda un despliegue incremental:

1. **`brain_core` + SQLite base:** nodos y aristas, búsqueda por palabras clave (FTS5), sin vectores todavía. Probado manualmente vía `curl`, sin tocar la extensión de VS Code ni la capa visual.
2. **Embeddings:** sumar la segunda instancia de `llama-server` (Sección 9) y `sqlite-vec` una vez que el paso 1 esté estable.
3. **Extensión de VS Code:** conectar `llama-vscode-chat` (confirmar primero cuál es la base exacta — Sección 8) una vez que `POST /process` responde de forma confiable.
4. **Capa visual:** conectar el fork de `claude-mem` al WebSocket.
5. **Scraping web:** se suma al final — es la pieza menos crítica y la que más puede esperar.

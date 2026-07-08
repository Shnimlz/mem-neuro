# 🧠 mem-neuro: Motor Cognitivo Persistente

> **Conecta modelos de lenguaje de gran tamaño con la recuperación persistente de conocimiento multi-fuente.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Svelte 5](https://img.shields.io/badge/Svelte-v5.0-FF3E00?logo=svelte&logoColor=white)](https://svelte.dev)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind_CSS-v4.0-38B2AC?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![SQLite](https://img.shields.io/badge/SQLite-sqlite--vec-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

🌎 **Languages / Idiomas:** [English](README.md) | [Español](README.es.md)

---

## 📸 Interfaz Visual

![mem-neuro Premium UI mockup](assets/ui_mockup.png)

---

## 🎯 ¿Qué es mem-neuro?

`mem-neuro` **no es un chatbot**, ni es un RAG simple y genérico. Es un **Motor Cognitivo Persistente** que gestiona, organiza y sintetiza el conocimiento antes de enviarlo al modelo de lenguaje.

Al separar el **razonamiento sobre qué conocimiento se necesita** (Planificación Cognitiva) de **cómo se recupera** (Orquestación Multi-Fuente), `mem-neuro` actúa menos como un buscador web simple y más como un agente de navegación autónomo (similar a Claude Search o Perplexity).

---

## 🏛️ Pipeline Cognitivo del Core

```
Pregunta de Usuario + Historial
              │
              ▼
     [KnowledgePlanner] ◄─────── (Consulta de inmediato recuerdos en SQLite)
              │
              ├──► [¿Memoria Suficiente?] ──► Usa únicamente el RAG local
              │
              └──► [Requiere Ingesta Externa]
                            │
                    [KnowledgeSources] ── (Memoria, Docs, GitHub, WebSearch, News)
                            │
                 [Browserless Headless] ── (Scrapea el HTML renderizado en paralelo)
                            │
                 [Source Authority Re-Rank] ─ (Boost a dominios oficiales, github, docs)
                            │
                 [Semantic Re-Ranking] ─── (EmbeddingsClient cosine similarity)
                            │
                   [CitationBuilder] ───── (Construye bibliografía y citas [N])
                            │
                       LLM Context
```

### 🧠 1. Planificación de Conocimiento (`KnowledgePlanner`)
Antes de realizar peticiones externas, el `KnowledgePlanner` consulta la base de datos semántica vectorial local de SQLite. Evalúa mediante el LLM (o heurísticas de respaldo) si la información de memoria es suficiente y está actualizada. De ser así, omite las consultas externas ahorrando recursos y reduciendo tiempos.

### 🔌 2. Fuentes de Conocimiento Abstractas (`KnowledgeSources`)
El sistema abstrae las integraciones de datos en interfaces `KnowledgeSource` reutilizables:
* **`MemorySource`**: Búsquedas semánticas sobre SQLite.
* **`WebSearchSource`**: Búsquedas web en Bing, SearXNG o DuckDuckGo mediante Browserless.
* **`GitHubSource`**: Extracción y análisis de código en repositorios.
* **`OfficialDocsSource`**: Acceso directo y priorizado a documentaciones oficiales.

### 🛡️ 3. Source Authority Ranking y Diversificación
* **Diversidad de Dominios**: Excluye duplicados y limita a un máximo de 2 enlaces por dominio para evitar sesgos informativos.
* **Boost de Autoridad**: Re-ordena resultados asignando boosts según el plan del planificador (ej. GitHub `+2.0`, Docs Oficiales `+2.0`, dominios `.gov`/`.edu` `+1.5`, Wikipedia `+1.0`) y descarta dominios clasificados en listas de spam.

### 📚 4. Citation Builder y Bibliografía (`CitationBuilder`)
Todos los fragmentos seleccionados (locales y externos) se fusionan, se rerankean semánticamente contra la query original, y se les asigna un marcador bibliográfico único (ej. `[1]`, `[2]`). Una sección detallada de referencias se adjunta al final para obligar al LLM a fundamentar rigurosamente sus afirmaciones.

---

## 🛠️ Estructura del Proyecto

```text
mem-neuro/
├── config.yaml                      # Configuración global centralizada
├── Proyecto.md                      # Especificación técnica del sistema
├── assets/                          # Recursos visuales
│   └── ui_mockup.png                # Mockup de la interfaz del chat
│
├── cerebro_unificado/
│   ├── backend/                     # Motor Cognitivo en Python (FastAPI)
│   │   ├── main.py                  # Endpoints y lifespan
│   │   ├── search_orchestrator.py   # Orquestador Multi-Fuente
│   │   ├── knowledge_planner.py     # Módulo de planificación cognitiva
│   │   └── database.py              # Capa de datos en SQLite WAL
│   │
│   └── frontend/                    # Interfaz en Svelte 5 + Tailwind CSS v4
```

---

## 🚀 Instalación y Puesta en Marcha

### 1. Requisitos Previos
- Docker (corriendo Browserless en el puerto `3000`):
  ```bash
  docker run -p 3000:3000 browserless/chrome:latest
  ```
- Servidores locales de LLM y Embeddings (corriendo en puertos `8080` y `8081`).

### 2. Configuración del Backend
1. Navega al directorio del backend:
   ```bash
   cd cerebro_unificado/backend
   ```
2. Instala las dependencias de Python:
   ```bash
   pip install -r requirements.txt
   ```
3. Inicia el servidor de FastAPI:
   ```bash
   python main.py
   ```

### 3. Configuración del Frontend
1. Navega al directorio del frontend:
   ```bash
   cd cerebro_unificado/frontend
   ```
2. Instala las dependencias de Node:
   ```bash
   npm install
   ```
3. Inicia el servidor de desarrollo:
   ```bash
   npm run dev
   ```

---

## 📄 Licencia
Licencia Apache 2.0. Consulta [LICENSE](LICENSE) para más detalles.

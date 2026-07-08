# 🧠 mem-neuro: Persistent Cognitive Engine

> **Bridges the gap between Large Language Models and persistent, multi-source knowledge retrieval.**

[![Python](https://img.shields.io/badge/Python-v3.14.6-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.139.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Svelte 5](https://img.shields.io/badge/Svelte-v5.56.1-FF3E00?logo=svelte&logoColor=white)](https://svelte.dev)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind_CSS-v4.3.0-38B2AC?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![SQLite](https://img.shields.io/badge/SQLite-v3.53.3-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

🌎 **Languages / Idiomas:** [English](README.md) | [Español](README.es.md)

---

## 📸 Visual Interface

### 💬 Chat Interface
![mem-neuro Chat Interface](assets/chat_interface.png)

### 🌐 Neuronal Cognitive Graph Viewer
![mem-neuro Neuronal Viewer](assets/neuronal_viewer.png)

---

## 🎯 What is mem-neuro?

`mem-neuro` is **not a chatbot**, nor is it a simple RAG wrapper. It is a **Persistent Cognitive Engine** that manages, structures, and synthesizes knowledge before it reaches the LLM. 

By separating the **reasoning about what knowledge is needed** (Cognitive Planning) from **how that knowledge is retrieved** (Multi-Source Orchestration), `mem-neuro` behaves less like a keyword-search tool and more like an agentic browser/reasoning system (analogous to Claude Search or Perplexity).

---

## 🏛️ Core Cognitive Pipeline

```
User Query + Chat History
           │
           ▼
   [KnowledgePlanner] ◄─────── (Instantly queries SQLite Semantics)
           │
           ├──► [Sufficient in Memory?] ──► Use local RAG context only
           │
           └──► [Requires External Ingestion]
                        │
                [KnowledgeSources] ── (Memory, Docs, GitHub, WebSearch, News)
                        │
             [Browserless Headless] ── (Scrapes rendered HTML in parallel)
                        │
             [Source Authority Re-Rank] ─ (Boosts official domains, github, docs)
                        │
             [Semantic Re-Ranking] ─── (EmbeddingsClient cosine similarity)
                        │
               [CitationBuilder] ───── (Builds bibliography and strict [N] markers)
                        │
                   LLM Context
```

### 🧠 1. Cognitive Planning (`KnowledgePlanner`)
Before performing any web request, the `KnowledgePlanner` queries the local SQLite semantic vector database. It then evaluates (via a quick LLM call or fallback heuristics) if the local memories are sufficient and up-to-date. If they are, it avoids making external web requests, protecting bandwidth and reducing latency.

### 🔌 2. Abstract Knowledge Sources (`KnowledgeSources`)
The system defines a modular `KnowledgeSource` abstraction, making it easy to plug in new knowledge providers:
* **`MemorySource`**: Vector search over SQLite nodes.
* **`WebSearchSource`**: Web search queries using Bing, SearXNG, or DuckDuckGo via Browserless.
* **`GitHubSource`**: Scraping and searching code repositories.
* **`OfficialDocsSource`**: Direct target of developer documentation.

### 🛡️ 3. Source Authority Ranking & Domain Diversity
* **Diversification**: Excludes duplicates and limits to a maximum of 2 links per domain to avoid bias.
* **Authority Boosts**: Re-ranks search results by boosting GitHub repositories (`+2.0`), official docs (`+2.0`), academic/official domains (`.gov`, `.edu` `+1.5`), and Wikipedia (`+1.0`), while filtering out spam domains.

### 📚 4. Citation Builder & Bibliography (`CitationBuilder`)
All selected text segments (both from local memory and scraped pages) are merged, semantically re-ranked against the query, and assigned a strict bibliographical marker (e.g. `[1]`, `[2]`). A detailed bibliography is attached at the end of the context, instructing the LLM to strictly base its claims on these sources.

---

## 🛠️ Project Structure

```text
mem-neuro/
├── config.yaml                      # Centralized configuration
├── Proyecto.md                      # Detailed architectural specification
├── assets/                          # Images and visual assets
│   └── ui_mockup.png                # Chat visual interface preview
│
├── cerebro_unificado/
│   ├── backend/                     # Python Cognitive Engine (FastAPI)
│   │   ├── main.py                  # API endpoints and lifespans
│   │   ├── search_orchestrator.py   # Multi-Source Orchestrator
│   │   ├── knowledge_planner.py     # Cognitive planner module
│   │   └── database.py              # WAL SQLite persistence layer
│   │
│   └── frontend/                    # Svelte 5 + Tailwind CSS v4 Chat Interface
```

## 🚀 Getting Started

Follow this step-by-step guide to configure the complete infrastructure locally.

---

### 1. Docker Infrastructure (Browserless & SearXNG)

Run both services exclusively inside Docker containers:

* **Browserless** (Headless navigation):
  ```bash
  docker run -d \
    --name browserless \
    -p 127.0.0.1:3000:3000 \
    --restart always \
    browserless/chrome:latest
  ```

* **SearXNG** (Search engine aggregation):
  ```bash
  docker run -d \
    --name searxng \
    -p 127.0.0.1:8888:8080 \
    --restart always \
    searxng/searxng:latest
  ```

> [!NOTE]
> Bounding ports to `127.0.0.1` ensures that services are only accessible locally, keeping the development environment safe.

---

### 2. Firewall Settings (`ufw`)

Manage access to the different ports of the cognitive engine. Bind rules to `127.0.0.1` whenever possible to prevent unauthorized network entry:

```bash
# Allow local connections to core & LLM ports
sudo ufw allow from 127.0.0.1 to any port 8000 proto tcp comment 'FastAPI Backend'
sudo ufw allow from 127.0.0.1 to any port 8080 proto tcp comment 'llama.cpp Chat'
sudo ufw allow from 127.0.0.1 to any port 8081 proto tcp comment 'llama.cpp Embeddings'
sudo ufw allow from 127.0.0.1 to any port 3000 proto tcp comment 'Browserless Docker'
sudo ufw allow from 127.0.0.1 to any port 8888 proto tcp comment 'SearXNG Docker'

# Enable firewall
sudo ufw enable
```

---

### 3. Local Model Downloader (`hf` CLI)

Use the Hugging Face CLI (`hf`) to download GGUF models directly:

```bash
# 1. Download Qwen 14B Chat model weights
hf download Bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf --local-dir ./models

# 2. Download mxbai embeddings model weights
hf download mixedbread-ai/mxbai-embed-large-v1 mxbai-embed-large-v1-f16.gguf --local-dir ./models
```

---

### 4. Compiling `llama.cpp` Locally

Avoid package managers. Clone the repository directly and compile it:

```bash
# Clone the repository
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Compile (CPU support only)
make

# Or compile with NVIDIA CUDA support (GPU accelerated)
make GGML_CUDA=1
```

---

### 5. API Keys (Google YouTube v3)

To fetch YouTube video results, obtain an API Key from the Google Cloud Console, enable the YouTube Data API v3, and set it in your environment:

```bash
# Temporary export
export YOUTUBE_API_KEY="your-google-youtube-api-key"

# Persistent setting
echo 'export YOUTUBE_API_KEY="your-google-youtube-api-key"' >> ~/.bashrc
source ~/.bashrc
```

---

### 6. Systemd User Services Configuration

To run the whole core automatically, create 3 independent systemd user service files in `~/.config/systemd/user/`:

#### A. `cerebro-llama-chat.service` (Reasoning LLM on Port 8080)
```ini
[Unit]
Description=Cerebro llama.cpp Chat Server
After=network.target

[Service]
ExecStart=/path/to/llama.cpp/llama-server -m /path/to/models/DeepSeek-R1-Distill-Qwen-14B-Q4_K_M.gguf -c 4096 --port 8080 --host 127.0.0.1
Restart=on-failure

[Install]
WantedBy=default.target
```

#### B. `cerebro-llama-embeddings.service` (Embeddings Server on Port 8081)
```ini
[Unit]
Description=Cerebro llama.cpp Embeddings Server
After=network.target

[Service]
ExecStart=/path/to/llama.cpp/llama-server -m /path/to/models/mxbai-embed-large-v1-f16.gguf --port 8081 --host 127.0.0.1 --embeddings --pooling mean
Restart=on-failure

[Install]
WantedBy=default.target
```

#### C. `cerebro-brain-core.service` (FastAPI Core Backend)
```ini
[Unit]
Description=Cerebro Autonomous Core Backend
After=network.target

[Service]
WorkingDirectory=%h/mem-neuro/cerebro_unificado/backend
ExecStart=/usr/bin/python3 main.py
Restart=on-failure

[Install]
WantedBy=default.target
```

To enable and run all services:
```bash
systemctl --user daemon-reload
systemctl --user enable --now cerebro-llama-chat.service
systemctl --user enable --now cerebro-llama-embeddings.service
systemctl --user enable --now cerebro-brain-core.service
```

---

### 7. Frontend Deployment

1. Navigate to the Svelte frontend directory:
   ```bash
   cd cerebro_unificado/frontend
   ```
2. Install Svelte and Node packages:
   ```bash
   npm install
   ```
3. Boot the development client:
   ```bash
   npm run dev
   ```

---

## 📄 License
Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

#!/bin/bash

# --- Script de Arranque de Producción (Cerebro Autónomo) ---
set -e

# Guardar la raíz de cerebro_unificado
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=== Iniciando Cerebro Autónomo Unificado (Producción) ==="

# Manejo de señales para apagado limpio (SIGINT / Ctrl+C)
cleanup() {
    echo -e "\n=== Apagando servicios y liberando puertos..."
    if [ ! -z "$UVICORN_PID" ]; then
        kill "$UVICORN_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

# 1. Verificar/Compilar el frontend (llama-ui)
if [ ! -d "frontend/dist" ]; then
    echo "Falta el directorio frontend/dist. Compilando interfaz..."
    cd "$DIR/frontend"
    npm install
    npm run build
    cd "$DIR"
fi

# 2. Levantar el backend (backend/)
cd "$DIR/backend"

# Activar entorno virtual
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Falta el entorno virtual .venv en backend. Creándolo..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
fi

echo "Iniciando servidor de producción uvicorn en 127.0.0.1:8000..."
uvicorn main:app --host 127.0.0.1 --port 8000 --log-level info &
UVICORN_PID=$!

# Esperar al subproceso uvicorn
wait "$UVICORN_PID"

#!/usr/bin/env bash
# Script to control the mem-neuro cognitive services (systemd user units)

SERVICES=(
  "cerebro-llama-chat.service"
  "cerebro-llama-embeddings.service"
  "cerebro-brain-core.service"
)

usage() {
    echo "Usage: $0 {start|stop|restart|status|enable|disable}"
    exit 1
}

if [ -z "$1" ]; then
    usage
fi

ACTION="$1"

case "$ACTION" in
    start)
        echo "Starting mem-neuro services..."
        systemctl --user start "${SERVICES[@]}"
        ;;
    stop)
        echo "Stopping mem-neuro services..."
        systemctl --user stop "${SERVICES[@]}"
        ;;
    restart)
        echo "Restarting mem-neuro services..."
        systemctl --user restart "${SERVICES[@]}"
        ;;
    status)
        echo "Checking mem-neuro services status..."
        systemctl --user status "${SERVICES[@]}"
        ;;
    enable)
        echo "Enabling mem-neuro services (start automatically on boot)..."
        systemctl --user enable "${SERVICES[@]}"
        ;;
    disable)
        echo "Disabling/Stopping mem-neuro services permanently (removes from boot)..."
        systemctl --user disable "${SERVICES[@]}"
        systemctl --user stop "${SERVICES[@]}"
        ;;
    *)
        usage
        ;;
esac

echo "Done!"

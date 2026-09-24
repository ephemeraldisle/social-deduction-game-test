#!/bin/sh
# Run from any terminal; the restarted server stays in that terminal.
set -eu
cd "$(dirname "$0")"

server_pids=$(lsof -tiTCP:8765 -sTCP:LISTEN || true)
for server_pid in $server_pids; do
    server_command=$(ps -p "$server_pid" -o command=)
    case "$server_command" in
        *"-m mission_game.cli web"*) ;;
        *) echo "Port 8765 is occupied by another program; leaving it running." >&2; exit 1 ;;
    esac
done
for server_pid in $server_pids; do
    echo "Stopping game server $server_pid..."
    kill "$server_pid"
done

attempt=0
while lsof -tiTCP:8765 -sTCP:LISTEN >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 50 ]; then
        echo "The old server has not released port 8765. Try again shortly." >&2
        exit 1
    fi
    sleep 0.1
done

echo "Starting http://127.0.0.1:8765 — press Ctrl+C in this terminal to stop."
exec python3 -m mission_game.cli web --runs-dir runs --port 8765

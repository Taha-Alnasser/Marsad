#!/usr/bin/env bash
# Start everything for the media monitor:   ./start.sh
# Stop it again:                             ./start.sh stop
set -e
cd "$(dirname "$0")"
PID=data/server.pid

if [ "$1" = "stop" ]; then
  [ -f $PID ] && kill "$(cat $PID)" 2>/dev/null && rm -f $PID && echo "Python server stopped."
  docker compose stop && echo "n8n stopped."
  exit 0
fi

# 1. Settings
[ -f .env ] || { echo "Missing .env: copy .env.example to .env and add your OpenAI key."; exit 1; }

# 2. Python environment (first run only)
if [ ! -d .venv ]; then
  echo "Creating the Python environment (first run only)..."
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi

# 3. n8n, in Docker
docker compose up -d

# 4. The Python server, in the background (log: data/server.log)
mkdir -p data
if [ -f $PID ] && kill -0 "$(cat $PID)" 2>/dev/null; then
  echo "Python server already running."
else
  nohup .venv/bin/uvicorn monitor.api:app --host 127.0.0.1 --port 8000 > data/server.log 2>&1 &
  echo $! > $PID
fi

# 5. Wait until both answer
printf "Waiting for services"
until curl -sf http://127.0.0.1:8000/health >/dev/null && curl -sf http://localhost:5678/healthz >/dev/null; do
  printf "."; sleep 2
done

echo "

  Ready.
  Control room   http://127.0.0.1:8000/
  n8n            http://localhost:5678/
  API docs       http://127.0.0.1:8000/docs

  Showing the server's activity below (the page's own refreshes are hidden).
  Ctrl+C stops watching; everything keeps running. To stop it all: ./start.sh stop
"
tail -n 20 -f data/server.log | grep --line-buffered -v "/api/overview"

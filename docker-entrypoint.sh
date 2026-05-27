#!/bin/sh
set -e
# Railway mounts the /data volume as root after image layers run.
# Fix ownership before dropping to appuser so SQLite can write.
if [ -d /data ]; then
    chown -R appuser:appuser /data 2>/dev/null || true
fi
exec su-exec appuser gunicorn backend.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --bind "0.0.0.0:${PORT:-8080}" \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile -

#!/usr/bin/env bash
# Install the SRE AI nginx config, build the React app, and start nginx.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF_SRC="${ROOT}/nginx/sre-ai.conf"
CONF_LINK="/opt/homebrew/etc/nginx/servers/sre-ai.conf"
DIST="${ROOT}/frontend/dist"

_log() { echo "==> $*"; }

# 1. Inject the real project root into the nginx config
sed "s|PROJECT_ROOT|${ROOT}|g" "$CONF_SRC" > /tmp/sre-ai-nginx.conf
cp /tmp/sre-ai-nginx.conf "$CONF_SRC"
_log "nginx config: PROJECT_ROOT set to ${ROOT}"

# 2. Symlink into nginx servers/ directory
ln -sf "$CONF_SRC" "$CONF_LINK"
_log "Symlinked → ${CONF_LINK}"

# 3. Build the React app
_log "Building React app (npm run build)…"
cd "${ROOT}/frontend" && npm run build
_log "Build output: ${DIST}"

# 4. Test nginx config
nginx -t
_log "nginx config OK"

# 5. (Re)start nginx — prefer direct nginx (brew services often shows "stopped" while a standalone master runs)
if lsof -i :8090 -sTCP:LISTEN >/dev/null 2>&1; then
    nginx -s reload 2>/dev/null || true
    _log "nginx reloaded (already listening on :8090)"
else
    if brew services list 2>/dev/null | grep -q "^nginx.*started"; then
        brew services restart nginx
        _log "nginx restarted via brew services"
    else
        nginx
        _log "nginx started (direct)"
    fi
fi

echo ""
echo "✓ Setup complete."
echo "  App: http://localhost:8090"
echo "  Start backend: make serve-backend"
echo "  Nginx logs:    /tmp/sre-ai-nginx-*.log"

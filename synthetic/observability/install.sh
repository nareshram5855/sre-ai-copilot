#!/usr/bin/env bash
# Backward-compatible wrapper — canonical install is infrastructure/k8s/observability/.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/../../infrastructure/k8s/observability/install.sh"

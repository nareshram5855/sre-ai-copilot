#!/usr/bin/env bash
# Bootstrap a self-hosted GitHub Actions runner on macOS for Minikube CD.
#
# Usage:
#   ./scripts/setup-github-runner-mac.sh OWNER/REPO [RUNNER_NAME]
#
# Prerequisites:
#   - GitHub PAT or registration token from repo Settings → Actions → Runners → New self-hosted runner
#   - minikube, kubectl, docker on PATH (Homebrew)
#   - Repo cloned at a stable path (default target: /Users/shivapriya/Downloads/sre-ai)
set -euo pipefail

REPO="${1:?Usage: $0 OWNER/REPO [RUNNER_NAME]}"
RUNNER_NAME="${2:-macbook-minikube}"
RUNNER_VERSION="${RUNNER_VERSION:-2.323.0}"
RUNNER_LABELS="${RUNNER_LABELS:-self-hosted,macOS,minikube}"
INSTALL_DIR="${RUNNER_INSTALL_DIR:-$HOME/actions-runners/${RUNNER_NAME}}"
REPO_PATH="${REPO_PATH:-/Users/shivapriya/Downloads/sre-ai}"

echo "==> GitHub self-hosted runner setup"
echo "    Repository : $REPO"
echo "    Runner name: $RUNNER_NAME"
echo "    Labels     : $RUNNER_LABELS"
echo "    Install dir: $INSTALL_DIR"
echo ""

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI: brew install gh && gh auth login"
  exit 1
fi

gh auth status >/dev/null

for cmd in minikube kubectl docker; do
  command -v "$cmd" >/dev/null || { echo "Missing: $cmd (brew install $cmd)"; exit 1; }
done

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [[ ! -f ./config.sh ]]; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    arm64) RUNNER_ARCH="arm64" ;;
    x86_64) RUNNER_ARCH="x64" ;;
    *) echo "Unsupported arch: $ARCH"; exit 1 ;;
  esac
  TARBALL="actions-runner-osx-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
  URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${TARBALL}"
  echo "==> Downloading runner ${RUNNER_VERSION} (${RUNNER_ARCH})..."
  curl -fsSL -o "$TARBALL" "$URL"
  tar xzf "$TARBALL"
  rm -f "$TARBALL"
fi

echo "==> Fetching registration token..."
REG_TOKEN="$(gh api "repos/${REPO}/actions/runners/registration-token" -q .token)"

echo "==> Configuring runner (non-interactive)..."
./config.sh remove --unattended 2>/dev/null || true
./config.sh \
  --url "https://github.com/${REPO}" \
  --token "$REG_TOKEN" \
  --name "$RUNNER_NAME" \
  --labels "$RUNNER_LABELS" \
  --unattended \
  --replace

echo ""
echo "==> Installing launchd service (runs at login)..."
sudo ./svc.sh install
sudo ./svc.sh start

echo ""
echo "✓ Runner installed."
echo ""
echo "Ensure Minikube is usable by the runner user:"
echo "  minikube start --cpus=4 --memory=8192"
echo ""
echo "Repo path for local dev (optional fixed checkout):"
echo "  $REPO_PATH"
echo ""
echo "Trigger first deploy:"
echo "  gh workflow run cd-minikube-mac.yml --ref develop"
echo ""
echo "Logs:"
echo "  tail -f ${INSTALL_DIR}/_diag/Runner_*.log"

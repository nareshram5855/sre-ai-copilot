#!/usr/bin/env bash
# Create the GitHub repo and push all branches. Requires: gh auth login
set -euo pipefail

REPO_NAME="${1:-sre-ai-copilot}"
VISIBILITY="${2:-private}"

echo "→ Checking GitHub auth..."
gh auth status

echo "→ Creating repo ${REPO_NAME} (${VISIBILITY})..."
gh repo create "$REPO_NAME" \
  --"$VISIBILITY" \
  --source=. \
  --remote=origin \
  --description "Local LLM-powered SRE incident response platform"

echo "→ Pushing branches..."
git push -u origin main
git push -u origin develop
git push -u origin staging

echo "✓ Done. Repository: $(gh repo view --json url -q .url)"
echo ""
echo "Optional — enable branch protection on main:"
echo "  gh api repos/:owner/:repo/branches/main/protection ..."

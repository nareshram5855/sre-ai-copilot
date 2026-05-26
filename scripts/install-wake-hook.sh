#!/usr/bin/env bash
# Install a macOS launchd agent that restarts observability port-forwards
# automatically when the Mac wakes from sleep.
#
# Usage:
#   scripts/install-wake-hook.sh install   # install the launchd agent
#   scripts/install-wake-hook.sh uninstall # remove it
set -euo pipefail

LABEL="com.sre-ai.pf-wake"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
ENSURE="$(cd "$(dirname "$0")/.." && pwd)/scripts/ensure-port-forwards.sh"
LOGFILE="/tmp/sre-ai-wake-hook.log"

install() {
  chmod +x "$ENSURE"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <!-- Run once on wake-from-sleep -->
  <key>WatchPaths</key>
  <array>
    <string>/var/run/com.apple.backboardd.plist</string>
  </array>
  <!-- Also run on login -->
  <key>RunAtLoad</key>
  <true/>

  <key>ProgramArguments</key>
  <array>
    <string>${ENSURE}</string>
  </array>

  <key>StandardOutPath</key>
  <string>${LOGFILE}</string>
  <key>StandardErrorPath</key>
  <string>${LOGFILE}</string>

  <!-- Restart if it crashes -->
  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
EOF

  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "✓ Wake hook installed — port-forwards will auto-restart after Mac sleep"
  echo "  Log: $LOGFILE"
}

uninstall() {
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✓ Wake hook removed"
}

case "${1:-install}" in
  install)   install ;;
  uninstall) uninstall ;;
  *)
    echo "Usage: $0 {install|uninstall}"
    exit 1
    ;;
esac

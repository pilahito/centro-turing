#!/usr/bin/env bash
# Autostart Ubuntu/Linux: systemd user + sesion grafica.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HOME/.config/autostart" "$HOME/.config/systemd/user"
DESK="$HOME/.config/autostart/pantalla-turing.desktop"
UNIT="$HOME/.config/systemd/user/pantalla-turing.service"
cat > "$DESK" <<EOF
[Desktop Entry]
Type=Application
Name=Pantalla Turing
Comment=Minipantalla al iniciar sesion
Exec=$ROOT/iniciar.sh
Path=$ROOT
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
cat > "$UNIT" <<EOF
[Unit]
Description=Pantalla Turing
After=default.target

[Service]
Type=simple
ExecStart=$ROOT/iniciar.sh
WorkingDirectory=$ROOT
Restart=on-failure
RestartSec=8

[Install]
WantedBy=default.target
EOF
chmod +x "$ROOT/iniciar.sh" "$ROOT/tools/instalar-autostart.sh" || true
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload || true
  systemctl --user enable --now pantalla-turing.service || true
fi
echo "Autostart Ubuntu listo: $DESK"
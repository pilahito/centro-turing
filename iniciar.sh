#!/usr/bin/env bash
# Arranque Linux (Ubuntu / Arch) del monitor Turing 3.5".
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

THEME="${1:-}"

if [[ "${1:-}" == "--autostart" ]]; then
  bash "$ROOT/tools/instalar-autostart.sh"
  exit 0
fi

if [[ "${1:-}" == "--install" ]]; then
  echo "Instalando dependencias..."
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip python3-tk python3-dev \
      libhidapi-hidraw0 libusb-1.0-0 python3-pil fonts-dejavu-core
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --needed --noconfirm python python-pip python-virtualenv tk \
      hidapi libusb python-pillow
  else
    echo "Distro no reconocida. Instala: python3 python3-venv python3-pip python3-tk libhidapi python3-pillow"
    exit 1
  fi
  if [[ ! -d venv ]]; then
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091
  source venv/bin/activate
  pip install -U pip
  pip install -r requirements.txt
  echo "OK. Enchufa la pantalla USB y ejecuta: ./iniciar.sh ConilES"
  exit 0
fi

PY="$ROOT/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi
if [[ -n "$THEME" ]]; then
  exec "$PY" "$ROOT/tools/lanzar.py" "$THEME"
fi
exec "$PY" "$ROOT/tools/lanzar.py"

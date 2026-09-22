#!/usr/bin/env bash
# Centro Turing - panel grafico (Windows y Linux). La pantalla la lleva main.py.
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -x "$ROOT/venv/bin/python" ]]; then
  PY="$ROOT/venv/bin/python"
else
  PY="python3"
fi
exec "$PY" "$ROOT/tools/turing_center.py" "$@"
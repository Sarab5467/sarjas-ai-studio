#!/usr/bin/env bash
set -euo pipefail
ROOT=/workspace/sarjas
BACKEND="$ROOT/backend"
WAN="$ROOT/Wan2.1"
MODEL="$ROOT/models/Wan2.1-T2V-1.3B"
LOG="$ROOT/backend/backend.log"
mkdir -p "$BACKEND" "$ROOT/state" "$ROOT/outputs"
exec >>"$LOG" 2>&1
echo "=== SarJas 25.5 startup $(date -Is) ==="
test -d "$MODEL" || { echo "MODEL MISSING: $MODEL"; exit 20; }
if [ ! -f "$WAN/generate.py" ]; then
  rm -rf "$WAN.tmp"
  git clone --depth 1 https://github.com/Wan-Video/Wan2.1.git "$WAN.tmp"
  mv "$WAN.tmp" "$WAN"
fi
python - <<'PY'
import importlib.util, subprocess, sys
mods=["fastapi","uvicorn","runpod","flash_attn","transformers","diffusers","cv2","imageio"]
missing=[m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    print("Missing runtime modules:",missing)
    sys.exit(31)
print("Runtime imports present")
PY
test -n "${SARJAS_API_TOKEN:-}" || { echo "SARJAS_API_TOKEN missing"; exit 40; }
export SARJAS_ROOT="$ROOT"
export SARJAS_WAN_MODEL="$MODEL"
export SARJAS_WAN_REPO="$WAN"
export SARJAS_MODE=pod
export PORT=8000
exec python -u "$BACKEND/handler.py"

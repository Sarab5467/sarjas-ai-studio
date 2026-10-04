#!/usr/bin/env bash
set -euo pipefail

ROOT="${SARJAS_ROOT:-/workspace/sarjas}"
RUNTIME="$ROOT/runtime"
WAN="$RUNTIME/Wan2.1"
SITE="$RUNTIME/site-packages"
MODEL="${SARJAS_WAN_MODEL:-$ROOT/models/Wan2.1-T2V-1.3B}"
PORT="${PORT:-8000}"

mkdir -p "$RUNTIME" "$ROOT/outputs" "$ROOT/state" "$SITE"

if [ ! -f "$MODEL/config.json" ] && [ ! -d "$MODEL" ]; then
  echo "FATAL: Wan model not found at $MODEL" >&2
  exit 20
fi

if [ ! -f "$WAN/generate.py" ]; then
  rm -rf /tmp/Wan2.1
  git clone --depth 1 https://github.com/Wan-Video/Wan2.1.git /tmp/Wan2.1
  mkdir -p "$WAN"
  cp -a /tmp/Wan2.1/. "$WAN/"
  rm -rf "$WAN/.git" /tmp/Wan2.1
fi

REQ_HASH="sarjas-wan-cu128-torch280-flashattn283p1-v1"
if [ ! -f "$SITE/.$REQ_HASH" ]; then
  python -m pip install --upgrade --target "$SITE" \
    "packaging>=24" "transformers>=4.49,<5" "diffusers>=0.32,<1" "accelerate>=1.2,<2" \
    "einops>=0.8,<1" "ftfy>=6.3,<7" "imageio>=2.36,<3" "imageio-ffmpeg>=0.5,<1" \
    "opencv-python>=4.10,<5" "tqdm>=4.67,<5" "easydict>=1.13,<2" "dashscope>=1.20,<2" \
    "fastapi>=0.115,<1" "uvicorn[standard]>=0.30,<1"
  PYTHONPATH="$SITE" MAX_JOBS=4 python -m pip install --no-build-isolation --target "$SITE" "flash-attn==2.8.3.post1"
  touch "$SITE/.$REQ_HASH"
fi

export PYTHONPATH="$SITE${PYTHONPATH:+:$PYTHONPATH}"
export SARJAS_MODE=pod
export SARJAS_ROOT="$ROOT"
export SARJAS_WAN_MODEL="$MODEL"
export SARJAS_WAN_REPO="$WAN"

if [ -z "${SARJAS_API_TOKEN:-}" ]; then
  echo "FATAL: SARJAS_API_TOKEN is not configured" >&2
  exit 21
fi
if [ ! -f "$RUNTIME/handler.py" ]; then
  echo "FATAL: $RUNTIME/handler.py missing. Lifecycle deployment must install backend payload first." >&2
  exit 22
fi

exec python -u "$RUNTIME/handler.py"

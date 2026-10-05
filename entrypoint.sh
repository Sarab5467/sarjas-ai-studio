#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${SARJAS_ROOT:-/workspace/sarjas}"
MODEL="${SARJAS_WAN_MODEL:-$ROOT/models/Wan2.1-T2V-1.3B}"
REPO="${HF_MODEL_REPO:-SarabBagyana/sarjas-wan-runtime}"

stage() { echo "[SARJAS_BOOT] $1"; }
fail() { code=$?; echo "[SARJAS_BOOT] FAILED exit=$code line=${BASH_LINENO[0]:-unknown}" >&2; exit "$code"; }
trap fail ERR

: "${SARJAS_API_TOKEN:?SARJAS_API_TOKEN missing}"
: "${HF_TOKEN:?HF_TOKEN missing}"

mkdir -p "$ROOT/models" "$ROOT/state" "$ROOT/outputs"

stage "VERIFYING_MODEL"
if [ ! -f "$MODEL/diffusion_pytorch_model.safetensors" ] || \
   [ ! -f "$MODEL/models_t5_umt5-xxl-enc-bf16.pth" ] || \
   [ ! -f "$MODEL/Wan2.1_VAE.pth" ] || \
   [ ! -f "$MODEL/config.json" ]; then
  stage "DOWNLOADING_MODEL"
  python - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id=os.environ.get("HF_MODEL_REPO","SarabBagyana/sarjas-wan-runtime"),
    repo_type="model",
    token=os.environ["HF_TOKEN"],
    local_dir=os.environ.get("SARJAS_WAN_MODEL","/workspace/sarjas/models/Wan2.1-T2V-1.3B"),
)
PY
fi

stage "VERIFYING_RUNTIME"
python - <<'PY'
import torch, flash_attn
assert torch.cuda.is_available(), "CUDA unavailable"
print("[SARJAS_BOOT] GPU="+torch.cuda.get_device_name(0), flush=True)
print("[SARJAS_BOOT] FLASH_ATTN=READY", flush=True)
PY

stage "STARTING_API"
exec python -u /app/handler.py

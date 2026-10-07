#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${SARJAS_ROOT:-/workspace/sarjas}"
MODEL="${SARJAS_WAN_MODEL:-$ROOT/models/Wan2.1-T2V-1.3B}"
BOOT="$ROOT/state/boot.json"
API_PID=""

write_boot() {
  local stage="$1" failed="${2:-false}" error="${3:-}"
  mkdir -p "$ROOT/state"
  python - "$BOOT" "$stage" "$failed" "$error" <<'PY'
import json,sys,time
path,stage,failed,error=sys.argv[1:]
with open(path,"w",encoding="utf-8") as f:
    json.dump({"stage":stage,"failed":failed.lower()=="true","error":error or None,"updated":time.time()},f)
PY
}
stage() { echo "[SARJAS_BOOT] $1"; write_boot "$1" false ""; }
fail() {
  code=$?
  msg="bootstrap failed exit=$code line=${BASH_LINENO[0]:-unknown}"
  echo "[SARJAS_BOOT] FAILED $msg" >&2
  write_boot "FAILED" true "$msg" || true
  if [ -n "$API_PID" ]; then kill "$API_PID" 2>/dev/null || true; fi
  exit "$code"
}
trap fail ERR

: "${SARJAS_API_TOKEN:?SARJAS_API_TOKEN missing}"
: "${HF_TOKEN:?HF_TOKEN missing}"

mkdir -p "$ROOT/models" "$ROOT/state" "$ROOT/outputs"
write_boot "STARTING_API" false ""

python -u /app/handler.py &
API_PID=$!

python - <<'PY'
import os,time,urllib.request
url=f"http://127.0.0.1:{os.environ.get('PORT','8000')}/health"
for _ in range(60):
    try:
        with urllib.request.urlopen(url,timeout=2) as r:
            if r.status==200:
                print("[SARJAS_BOOT] API=ONLINE",flush=True)
                break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("API failed to bind port 8000")
PY

stage "VERIFYING_MODEL"
missing=0
for f in diffusion_pytorch_model.safetensors models_t5_umt5-xxl-enc-bf16.pth Wan2.1_VAE.pth config.json; do
  [ -f "$MODEL/$f" ] || { echo "[SARJAS_BOOT] MODEL_MISSING=$f" >&2; missing=1; }
done
if [ "$missing" -ne 0 ]; then
  if [ "${SARJAS_REQUIRE_PERSISTENT_MODEL:-1}" = "1" ]; then
    write_boot "FAILED" true "persistent Wan model missing" || true
    echo "[SARJAS_BOOT] FATAL: persistent Wan model missing; refusing paid re-download" >&2
    exit 42
  fi
  stage "DOWNLOADING_MODEL"
  python - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(repo_id=os.environ.get("HF_MODEL_REPO","SarabBagyana/sarjas-wan-runtime"),
                  repo_type="model",token=os.environ["HF_TOKEN"],
                  local_dir=os.environ.get("SARJAS_WAN_MODEL","/workspace/sarjas/models/Wan2.1-T2V-1.3B"))
PY
fi

stage "VERIFYING_RUNTIME"
python - <<'PY'
import torch,flash_attn
assert torch.cuda.is_available(),"CUDA unavailable"
print("[SARJAS_BOOT] GPU="+torch.cuda.get_device_name(0),flush=True)
print("[SARJAS_BOOT] FLASH_ATTN=READY",flush=True)
PY

stage "READY"
wait "$API_PID"

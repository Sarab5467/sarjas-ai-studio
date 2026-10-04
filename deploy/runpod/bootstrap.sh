#!/usr/bin/env bash
set -euo pipefail
# One-time bootstrap on a known-good RunPod PyTorch 2.8/CUDA image.
ROOT=/workspace/sarjas
mkdir -p "$ROOT/backend"
cp /root/sarjas_api.py "$ROOT/backend/handler.py"
cp /root/sarjas_start.sh "$ROOT/backend/start.sh"
chmod +x "$ROOT/backend/start.sh"
if [ ! -d "$ROOT/Wan2.1/.git" ]; then git clone --depth 1 https://github.com/Wan-Video/Wan2.1.git "$ROOT/Wan2.1"; fi
grep -v '^flash_attn' "$ROOT/Wan2.1/requirements.txt" > /tmp/wan_requirements.txt
python -m pip install --no-cache-dir -r /tmp/wan_requirements.txt
python -m pip install --no-cache-dir flash-attn --no-build-isolation
python -m pip install --no-cache-dir "runpod>=1.7,<2"
python -m py_compile "$ROOT/backend/handler.py"
echo "SARJAS PERSISTENT BACKEND READY"

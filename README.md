# SarJas AI Studio — Priority 25.5 Permanent Backend

## Target
SarJas Windows -> lifecycle controller -> Runpod GPU Pod -> authenticated SarJas API -> Wan2.1 -> persistent network volume -> MP4 -> automatic GPU stop.

Normal operation must require no SSH, web terminal, manual Python commands, or manual endpoint editing.

## 25.5 A-F implementation
- **A Runtime Lock:** `runtime/bootstrap.sh` pins the validated base assumptions (Torch 2.8/CUDA 12.8 image), Wan dependencies and `flash-attn==2.8.3.post1`. Runtime dependencies and Wan source are cached under the persistent network volume.
- **B Automatic Backend Boot:** lifecycle deployment writes the bootstrap/backend payload to `/workspace/sarjas/runtime`; bootstrap validates model/token and launches port 8000 automatically.
- **C Lifecycle Controller:** `runpod_lifecycle.py` creates/starts/stops/deletes Pods through the official `runpodctl pod` surface and derives the proxy endpoint from Pod ID.
- **D Persistent Infrastructure:** Pod creation requires the existing network volume ID and mounts it at `/workspace`; model, outputs, state DB and runtime cache live there.
- **E Windows Integration:** `managed_sarjas.py` performs create -> readiness -> authenticated submit -> poll -> download.
- **F Security/Cost Guard:** no secrets are committed; GPU create/start requires the exact approval phrase; Pod creation has `--stop-after`; managed generation attempts to stop the Pod in a `finally` block even on failure.

## Local configuration
Copy `.env.example` to your local environment/configuration and provide values privately. Never commit the Runpod API key or SarJas worker token.

The lifecycle controller expects the official `runpodctl` executable to be configured locally. The Runpod API credential remains in Runpod's local CLI credential store; SarJas does not pass it on command lines.

## Persistent paths
- Model: `/workspace/sarjas/models/Wan2.1-T2V-1.3B`
- Runtime cache: `/workspace/sarjas/runtime`
- Outputs: `/workspace/sarjas/outputs`
- Job DB: `/workspace/sarjas/state/jobs.sqlite3`

## Backend API
- `GET /health`
- `POST /v1/jobs` authenticated
- `GET /v1/jobs/{job_id}` authenticated
- `GET /v1/jobs/{job_id}/result` authenticated

## Remaining live pass gate (G-J)
25.5 is **not PASS yet**. A fresh paid GPU session must prove:
1. SarJas creates/redeploys the Pod without SSH.
2. Existing network volume attaches and model is found.
3. Bootstrap automatically reaches healthy port 8000.
4. Windows SarJas submits a real T2V job and downloads a valid MP4.
5. SarJas stops the GPU automatically.
6. A second start/redeploy proves persistence/recovery.

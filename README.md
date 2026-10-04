# SarJas AI Studio — Priority 25.5 Backend

Private backend/deployment repository.

## Architecture
SarJas Windows client -> authenticated HTTP API -> GPU Pod -> Wan2.1 -> persistent network volume -> MP4.

The same worker also supports RunPod Serverless mode. Pod mode is the validated deployment target for the existing `sarjas-ai-models` volume.

## Required runtime configuration
- Network volume mounted at `/workspace`
- Model: `/workspace/sarjas/models/Wan2.1-T2V-1.3B`
- `SARJAS_MODE=pod`
- `SARJAS_API_TOKEN=<random secret>`
- HTTP port: `8000`

No secret is committed to this repository.

## API
- `GET /health` — readiness/model/storage checks
- `POST /v1/jobs` — authenticated job submission
- `GET /v1/jobs/{job_id}` — authenticated status/result lookup

Authorization: `Bearer <SARJAS_API_TOKEN>`.

## Deployment rule
Do not develop interactively on a paid GPU. Build/configure first, then use one short paid validation session. Wan code and Python dependencies are baked into the image; the model/output data remain on the network volume.

## Priority 25.5 pass gate
25.5 is not complete until a fresh GPU deployment starts the API automatically and a SarJas client can submit a real T2V job, poll it, receive the MP4 result, and the GPU can be stopped without losing the persistent model.

# SarJas AI Studio

Private deployment repository for SarJas AI Studio.

## RunPod Serverless worker

The root Dockerfile launches `handler.py` with the RunPod Serverless SDK.

### 25.5 purpose

This deployment establishes the stable SarJas-to-RunPod endpoint before paid model validation.

Supported worker actions:
- `health`
- `t2v`
- `i2v`
- `generate_video`

The default backend is `mock`. Real Wan inference is enabled later through the model adapter after the permanent endpoint is verified.

### Persistent storage

When a RunPod network volume is attached, configure:

`SARJAS_ROOT=/runpod-volume/sarjas`

No API keys or secrets belong in this repository.

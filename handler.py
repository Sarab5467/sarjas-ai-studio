import os, json, subprocess, pathlib, time, sys
import runpod

ROOT = pathlib.Path(os.getenv("SARJAS_ROOT", "/runpod-volume/sarjas"))
MODEL = pathlib.Path(os.getenv("SARJAS_WAN_MODEL", str(ROOT / "models" / "Wan2.1-T2V-1.3B")))
WAN_REPO = pathlib.Path(os.getenv("SARJAS_WAN_REPO", "/app/Wan2.1"))
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

def health():
    return {
        "ok": True,
        "service": "sarjas-ai-studio",
        "version": "25.5",
        "storage_root": str(ROOT),
        "storage_mounted": ROOT.exists(),
        "model_path": str(MODEL),
        "model_present": MODEL.exists(),
        "wan_repo": str(WAN_REPO),
        "wan_present": WAN_REPO.exists(),
    }

def handler(job):
    started = time.time()
    payload = job.get("input") or {}
    action = payload.get("action", "health")
    if action == "health":
        return health()
    if action != "t2v":
        raise ValueError(f"Unsupported action: {action}")

    if not MODEL.exists():
        raise RuntimeError(f"Wan model not found at {MODEL}; attach sarjas-ai-models network volume")
    if not WAN_REPO.exists():
        raise RuntimeError(f"Wan repository not found at {WAN_REPO}")

    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("prompt is required")

    size = str(payload.get("size", "832*480"))
    frames = int(payload.get("frames", 17))
    steps = int(payload.get("steps", 10))
    sample_shift = float(payload.get("sample_shift", 8.0))
    guide_scale = float(payload.get("guide_scale", 6.0))
    seed = int(payload.get("seed", -1))
    job_id = str(job.get("id") or f"local-{int(started)}")
    output_path = OUT / f"{job_id}.mp4"

    cmd = [
        sys.executable, str(WAN_REPO / "generate.py"),
        "--task", "t2v-1.3B",
        "--size", size,
        "--ckpt_dir", str(MODEL),
        "--prompt", prompt,
        "--frame_num", str(frames),
        "--sample_steps", str(steps),
        "--sample_shift", str(sample_shift),
        "--sample_guide_scale", str(guide_scale),
        "--base_seed", str(seed),
        "--save_file", str(output_path),
    ]
    subprocess.run(cmd, check=True, cwd=str(WAN_REPO))
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Wan completed without a valid MP4")

    return {
        "ok": True,
        "action": "t2v",
        "output_path": str(output_path),
        "bytes": output_path.stat().st_size,
        "elapsed_seconds": round(time.time() - started, 3),
    }

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})

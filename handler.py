import os, json, subprocess, shlex, pathlib, time
import runpod

ROOT = pathlib.Path(os.getenv("SARJAS_ROOT", "/runpod-volume/sarjas"))
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
BACKEND = os.getenv("SARJAS_MODEL_BACKEND", "mock").strip().lower()
GEN_CMD = os.getenv("SARJAS_GENERATE_COMMAND", "").strip()

def _mock_video(path: pathlib.Path, width=832, height=480, duration=1):
    cmd = [
        "ffmpeg","-y","-f","lavfi","-i",
        f"color=c=black:s={width}x{height}:d={duration}",
        "-c:v","libx264","-pix_fmt","yuv420p",str(path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def handler(job):
    started = time.time()
    payload = job.get("input") or {}
    action = payload.get("action", "health")
    if action == "health":
        return {
            "ok": True,
            "service": "sarjas-ai-studio",
            "backend": BACKEND,
            "storage_root": str(ROOT),
            "version": "25.5"
        }
    job_id = str(job.get("id") or f"local-{int(started)}")
    output_path = OUT / f"{job_id}.mp4"
    if action in ("t2v", "i2v", "generate_video"):
        if BACKEND == "mock":
            width = int(payload.get("width", 832))
            height = int(payload.get("height", 480))
            _mock_video(output_path, width, height, 1)
        elif BACKEND == "command":
            if not GEN_CMD:
                raise RuntimeError("SARJAS_GENERATE_COMMAND is not configured")
            env = os.environ.copy()
            env["SARJAS_JOB_INPUT"] = json.dumps(payload)
            env["SARJAS_OUTPUT_PATH"] = str(output_path)
            subprocess.run(shlex.split(GEN_CMD), check=True, env=env)
            if not output_path.exists():
                raise RuntimeError("Generation command returned without an output file")
        else:
            raise RuntimeError(f"Unsupported backend: {BACKEND}")
        return {
            "ok": True,
            "action": action,
            "output_path": str(output_path),
            "elapsed_seconds": round(time.time() - started, 3)
        }
    raise ValueError(f"Unsupported action: {action}")

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})

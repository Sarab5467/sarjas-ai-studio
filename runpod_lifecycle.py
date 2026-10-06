"""Priority 25.5 RunPod lifecycle controller.

G launches the prebuilt SarJas worker image directly. Startup belongs to the
container image; SarJas does not inject bootstrap commands through docker args.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass

import requests

APPROVAL_TEXT = "APPROVE estimated RunPod charge"


@dataclass
class PodConfig:
    api_token: str
    hf_token: str
    gpu_id: str = "NVIDIA GeForce RTX 3090"
    image: str = "ghcr.io/sarab5467/sarjas-ai-studio:25.5"
    hf_model_repo: str = "SarabBagyana/sarjas-wan-runtime"
    container_disk_gb: int = 80
    port: int = 8000
    name: str = "sarjas-ai-25-5"


class RunpodLifecycle:
    def __init__(self, cfg: PodConfig, runpodctl: str | None = None):
        self.cfg = cfg
        self.exe = runpodctl or os.getenv("SARJAS_RUNPODCTL") or shutil.which("runpodctl")
        if not self.exe:
            raise RuntimeError("runpodctl is not installed/configured")
        if not cfg.api_token:
            raise ValueError("SarJas backend token is required")
        if not cfg.hf_token:
            raise ValueError("Hugging Face runtime token is required")

    def _run(self, *args: str, timeout: int = 120) -> str:
        env = os.environ.copy()
        p = subprocess.run(
            [self.exe, *args],
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        if p.returncode:
            raise RuntimeError((p.stderr or p.stdout or "runpodctl failed").strip())
        return p.stdout.strip()

    @staticmethod
    def endpoint(pod_id: str, port: int = 8000) -> str:
        return f"https://{pod_id}-{port}.proxy.runpod.net"

    def create(self, approval: str) -> str:
        if approval.strip() != APPROVAL_TEXT:
            raise PermissionError(
                "Explicit spending approval is required before starting paid GPU compute"
            )

        env_json = json.dumps(
            {
                "SARJAS_API_TOKEN": self.cfg.api_token,
                "HF_TOKEN": self.cfg.hf_token,
                "HF_MODEL_REPO": self.cfg.hf_model_repo,
                "SARJAS_ROOT": "/workspace/sarjas",
                "SARJAS_WAN_MODEL": "/workspace/sarjas/models/Wan2.1-T2V-1.3B",
                "SARJAS_MODE": "pod",
                "PORT": str(self.cfg.port),
            },
            separators=(",", ":"),
        )

        out = self._run(
            "pod", "create",
            "--name", self.cfg.name,
            "--image", self.cfg.image,
            "--gpu-id", self.cfg.gpu_id,
            "--gpu-count", "1",
            "--container-disk-in-gb", str(self.cfg.container_disk_gb),
            "--volume-mount-path", "/workspace",
            "--ports", f"{self.cfg.port}/http",
            "--env", env_json,
            timeout=180,
        )
        m = re.search(
            r"(?:pod\s*id|id)\s*[:=]?\s*([a-zA-Z0-9_-]{8,})",
            out,
            re.I,
        )
        if m:
            return m.group(1)
        raise RuntimeError(
            "Pod created but SarJas could not safely parse Pod ID; output: " + out[:500]
        )

    def start(self, pod_id: str, approval: str) -> None:
        if approval.strip() != APPROVAL_TEXT:
            raise PermissionError(
                "Explicit spending approval is required before starting paid GPU compute"
            )
        self._run("pod", "start", pod_id)

    def stop(self, pod_id: str) -> None:
        self._run("pod", "stop", pod_id)

    def delete(self, pod_id: str) -> None:
        self._run("pod", "delete", pod_id)

    def wait_ready(self, pod_id: str, timeout: int = 600, poll: int = 8) -> dict:
        url = self.endpoint(pod_id, self.cfg.port)
        end = time.time() + timeout
        last = ""
        while time.time() < end:
            try:
                r = requests.get(url + "/health", timeout=10)
                if r.ok:
                    health = r.json()
                    if (
                        health.get("ok")
                        and health.get("model_present")
                        and health.get("wan_present")
                        and health.get("cuda_ready")
                        and health.get("flash_attn_ready")
                    ):
                        return health
                    last = json.dumps(health)
                else:
                    last = f"HTTP {r.status_code}"
            except Exception as exc:
                last = str(exc)
            time.sleep(poll)
        raise TimeoutError("Backend did not become ready: " + last)

def start_for_g(explicit_approval: bool = False, estimated_usd: float = 0.0) -> dict:
    """One-command G startup gate used by the Windows SarJas app."""
    if not explicit_approval:
        raise PermissionError("Explicit spending approval is required before G")
    if estimated_usd <= 0 or estimated_usd > 0.25:
        raise PermissionError("G estimate must be greater than $0 and no more than the approved $0.25")

    api_token = os.getenv("SARJAS_WORKER_TOKEN") or os.getenv("SARJAS_API_TOKEN")
    hf_token = os.getenv("HF_TOKEN")
    hf_repo = os.getenv("HF_MODEL_REPO", "SarabBagyana/sarjas-wan-runtime")
    if not api_token or not hf_token:
        raise RuntimeError("SARJAS_WORKER_TOKEN/SARJAS_API_TOKEN and HF_TOKEN must be set")

    lifecycle = RunpodLifecycle(PodConfig(
        api_token=api_token,
        hf_token=hf_token,
        hf_model_repo=hf_repo,
    ))
    pod_id = ""
    try:
        pod_id = lifecycle.create(APPROVAL_TEXT)
        print(f"[SARJAS] Pod created: {pod_id}", flush=True)
        print("[SARJAS] Waiting for custom worker image and backend...", flush=True)
        health = lifecycle.wait_ready(pod_id)
        print("[SARJAS] G READY", flush=True)
        return {
            "ok": True,
            "pod_id": pod_id,
            "endpoint": lifecycle.endpoint(pod_id, lifecycle.cfg.port),
            "health": health,
            "estimated_usd": estimated_usd,
        }
    except Exception:
        if pod_id:
            print("[SARJAS] Startup failed. Stopping GPU...", flush=True)
            try:
                lifecycle.stop(pod_id)
            except Exception as stop_error:
                print(f"[SARJAS] WARNING: automatic stop failed: {stop_error}", flush=True)
        raise


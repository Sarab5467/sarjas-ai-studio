"""Priority 25.5 Runpod Pod lifecycle controller.

Normal operation is programmatic; the user never needs to open a terminal.
This adapter uses the official runpodctl Pod lifecycle surface so API details
remain owned by Runpod rather than duplicated in SarJas.
"""
from __future__ import annotations
import base64, json, os, pathlib, re, shutil, subprocess, time, urllib.request
from dataclasses import dataclass
import requests

APPROVAL_TEXT = "APPROVE estimated RunPod charge"

@dataclass
class PodConfig:
    network_volume_id: str
    api_token: str
    gpu_id: str = "NVIDIA GeForce RTX 3090"
    image: str = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404"
    container_disk_gb: int = 80
    port: int = 8000
    stop_after: str = "1h"
    name: str = "sarjas-ai-25-5"

class RunpodLifecycle:
    def __init__(self, cfg: PodConfig, runpodctl: str | None = None):
        self.cfg = cfg
        self.exe = runpodctl or os.getenv("SARJAS_RUNPODCTL") or shutil.which("runpodctl")
        if not self.exe:
            raise RuntimeError("runpodctl is not installed/configured")
        if not cfg.network_volume_id:
            raise ValueError("network_volume_id is required")
        if not cfg.api_token:
            raise ValueError("SarJas backend token is required")

    def _run(self, *args: str, timeout: int = 120) -> str:
        env = os.environ.copy()
        # runpodctl reads its normal local credential configuration. Never put
        # the Runpod API key in command arguments or logs.
        p = subprocess.run([self.exe, *args], text=True, capture_output=True,
                           timeout=timeout, env=env)
        if p.returncode:
            raise RuntimeError((p.stderr or p.stdout or "runpodctl failed").strip())
        return p.stdout.strip()

    @staticmethod
    def endpoint(pod_id: str, port: int = 8000) -> str:
        return f"https://{pod_id}-{port}.proxy.runpod.net"

    def create(self, approval: str, bootstrap_path: str = "", handler_path: str = "") -> str:
        if approval.strip() != APPROVAL_TEXT:
            raise PermissionError("Explicit spending approval is required before starting paid GPU compute")
        env_json = json.dumps({
            "SARJAS_API_TOKEN": self.cfg.api_token,
            "SARJAS_ROOT": "/workspace/sarjas",
            "SARJAS_WAN_MODEL": "/workspace/sarjas/models/Wan2.1-T2V-1.3B",
            "SARJAS_MODE": "pod",
            "PORT": str(self.cfg.port),
        }, separators=(",", ":"))
        # First boot must not depend on unauthenticated raw GitHub: this repo is private.
        # Seed the two small runtime files from the trusted local checkout.
        repo_root = pathlib.Path(__file__).resolve().parent
        bpath = pathlib.Path(bootstrap_path) if bootstrap_path else repo_root / "runtime" / "bootstrap.sh"
        hpath = pathlib.Path(handler_path) if handler_path else repo_root / "handler.py"
        if not bpath.is_file() or not hpath.is_file():
            raise FileNotFoundError("SarJas bootstrap payload is missing; refusing to create paid compute")
        bootstrap_b64 = base64.b64encode(bpath.read_bytes()).decode("ascii")
        handler_b64 = base64.b64encode(hpath.read_bytes()).decode("ascii")
        env = json.loads(env_json)
        env["SARJAS_BOOTSTRAP_B64"] = bootstrap_b64
        env["SARJAS_HANDLER_B64"] = handler_b64
        env_json = json.dumps(env, separators=(",", ":"))
        launch = (
            "set -e; mkdir -p /workspace/sarjas/runtime; "
            "printf %s \"$SARJAS_BOOTSTRAP_B64\" | base64 -d > /workspace/sarjas/runtime/bootstrap.sh; "
            "printf %s \"$SARJAS_HANDLER_B64\" | base64 -d > /workspace/sarjas/runtime/handler.py; "
            "exec bash /workspace/sarjas/runtime/bootstrap.sh"
        )
        out = self._run(
            "pod","create","--name",self.cfg.name,
            "--image",self.cfg.image,
            "--gpu-id",self.cfg.gpu_id,
            "--gpu-count","1",
            "--container-disk-in-gb",str(self.cfg.container_disk_gb),
            "--volume-mount-path","/workspace",
            "--network-volume-id",self.cfg.network_volume_id,
            "--ports",f"{self.cfg.port}/http",
            "--env",env_json,
            "--docker-args",launch,
            timeout=180,
        )
        m = re.search(r"(?:pod\s*id|id)\s*[:=]?\s*([a-zA-Z0-9_-]{8,})", out, re.I)
        if m:
            return m.group(1)
        raise RuntimeError("Pod created but SarJas could not safely parse Pod ID; output: "+out[:500])

    def start(self, pod_id: str, approval: str) -> None:
        if approval.strip() != APPROVAL_TEXT:
            raise PermissionError("Explicit spending approval is required before starting paid GPU compute")
        self._run("pod","start",pod_id)

    def stop(self, pod_id: str) -> None:
        self._run("pod","stop",pod_id)

    def delete(self, pod_id: str) -> None:
        self._run("pod","delete",pod_id)

    def wait_ready(self, pod_id: str, timeout: int = 1200, poll: int = 10) -> dict:
        url=self.endpoint(pod_id,self.cfg.port)
        end=time.time()+timeout
        last=""
        while time.time()<end:
            try:
                r=requests.get(url+"/health",timeout=10)
                if r.ok:
                    h=r.json()
                    if h.get("ok") and h.get("model_present") and h.get("wan_present"):
                        return h
                    last=json.dumps(h)
                else:last=f"HTTP {r.status_code}"
            except Exception as e:last=str(e)
            time.sleep(poll)
        raise TimeoutError("Backend did not become ready: "+last)

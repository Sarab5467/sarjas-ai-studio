"""SarJas Priority 25.5 RunPod lifecycle controller."""
from __future__ import annotations
import json, os, re, shutil, subprocess, time
from dataclasses import dataclass
import requests

APPROVAL_TEXT = "APPROVE estimated RunPod charge"
_SECRET_KEYS = ("HF_TOKEN", "SARJAS_API_TOKEN", "SARJAS_WORKER_TOKEN", "RUNPOD_API_KEY")

def _load_project_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        return
    except ImportError:
        pass
    candidates = [os.path.join(os.getcwd(), ".env"),
                  os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return

def _redact(text: str) -> str:
    out = text or ""
    for key in _SECRET_KEYS:
        value = os.getenv(key)
        if value: out = out.replace(value, f"<{key}:REDACTED>")
    out = re.sub(r'hf_[A-Za-z0-9]{12,}', '<HF_TOKEN:REDACTED>', out)
    return out

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
    network_volume_id: str = ""

class RunpodLifecycle:
    def __init__(self, cfg: PodConfig, runpodctl: str | None = None):
        self.cfg = cfg
        self.exe = runpodctl or os.getenv("SARJAS_RUNPODCTL") or shutil.which("runpodctl")
        if not self.exe: raise RuntimeError("runpodctl is not installed/configured")
        if not cfg.api_token: raise ValueError("SarJas backend token is required")
        if not cfg.hf_token: raise ValueError("Hugging Face runtime token is required")
        if not cfg.network_volume_id: raise ValueError("Persistent RunPod network volume is required")

    def _run(self, *args: str, timeout: int = 120) -> str:
        p = subprocess.run([self.exe, *args], text=True, capture_output=True,
                           timeout=timeout, env=os.environ.copy())
        if p.returncode:
            raise RuntimeError(_redact((p.stderr or p.stdout or "runpodctl failed").strip()))
        return p.stdout.strip()

    @staticmethod
    def endpoint(pod_id: str, port: int = 8000) -> str:
        return f"https://{pod_id}-{port}.proxy.runpod.net"

    @staticmethod
    def _parse_pod_id(out: str) -> str:
        try:
            obj = json.loads(out)
            if isinstance(obj, dict):
                for key in ("id", "podId", "pod_id"):
                    value = obj.get(key)
                    if isinstance(value, str) and value.strip(): return value.strip()
        except json.JSONDecodeError:
            pass
        m = re.search(r'(?:pod\s*id|podId|"id"|id)\s*[:=]\s*"?([a-zA-Z0-9_-]{8,})', out, re.I)
        if m: return m.group(1)
        raise RuntimeError("RunPod reported pod creation, but no Pod ID could be parsed (output redacted).")

    def create(self, approval: str) -> str:
        if approval.strip() != APPROVAL_TEXT:
            raise PermissionError("Explicit spending approval is required before starting paid GPU compute")
        env_json = json.dumps({
            "SARJAS_API_TOKEN": self.cfg.api_token, "HF_TOKEN": self.cfg.hf_token,
            "HF_MODEL_REPO": self.cfg.hf_model_repo, "SARJAS_ROOT": "/workspace/sarjas",
            "SARJAS_WAN_MODEL": "/workspace/sarjas/models/Wan2.1-T2V-1.3B",
            "SARJAS_MODE": "pod", "PORT": str(self.cfg.port),
            "SARJAS_REQUIRE_PERSISTENT_MODEL": "1"}, separators=(",", ":"))
        out = self._run("pod","create","--name",self.cfg.name,"--image",self.cfg.image,
                        "--gpu-id",self.cfg.gpu_id,"--gpu-count","1",
                        "--container-disk-in-gb",str(self.cfg.container_disk_gb),
                        "--network-volume-id",self.cfg.network_volume_id,
                        "--volume-mount-path","/workspace","--ports",f"{self.cfg.port}/http",
                        "--env",env_json,timeout=180)
        return self._parse_pod_id(out)

    def stop(self, pod_id: str) -> None: self._run("pod","stop",pod_id)
    def delete(self, pod_id: str) -> None: self._run("pod","delete",pod_id)

    def wait_ready(self, pod_id: str, timeout: int = 600, poll: int = 8) -> dict:
        url, end, last = self.endpoint(pod_id,self.cfg.port), time.time()+timeout, ""
        while time.time() < end:
            try:
                r=requests.get(url+"/health",timeout=10)
                if r.ok:
                    h=r.json()
                    if h.get("boot_failed"):
                        raise RuntimeError("Backend bootstrap failed: "+str(h.get("boot_error") or h.get("boot_stage") or "unknown"))
                    if all(h.get(k) for k in ("ok","model_present","wan_present","cuda_ready","flash_attn_ready")):
                        return h
                    last=json.dumps(h)
                else: last=f"HTTP {r.status_code}"
            except Exception as e: last=str(e)
            time.sleep(poll)
        raise TimeoutError("Backend did not become ready: "+_redact(last))

def start_for_g(explicit_approval: bool=False, estimated_usd: float=0.0) -> dict:
    _load_project_env()
    if not explicit_approval: raise PermissionError("Explicit spending approval is required before G")
    if estimated_usd <= 0 or estimated_usd > 0.25:
        raise PermissionError("G estimate must be greater than $0 and no more than $0.25")
    api_token=os.getenv("SARJAS_WORKER_TOKEN") or os.getenv("SARJAS_API_TOKEN")
    hf_token=os.getenv("HF_TOKEN")
    if not api_token or not hf_token:
        raise RuntimeError("SARJAS_WORKER_TOKEN/SARJAS_API_TOKEN and HF_TOKEN must be set")
    volume_id=os.getenv("SARJAS_NETWORK_VOLUME_ID","").strip()
    if not volume_id:
        raise RuntimeError("SARJAS_NETWORK_VOLUME_ID must be set before paid G testing")
    life=RunpodLifecycle(PodConfig(api_token=api_token,hf_token=hf_token,network_volume_id=volume_id,
        hf_model_repo=os.getenv("HF_MODEL_REPO","SarabBagyana/sarjas-wan-runtime")))
    pod_id=""
    try:
        pod_id=life.create(APPROVAL_TEXT)
        print(f"[SARJAS] Pod created: {pod_id}",flush=True)
        health=life.wait_ready(pod_id)
        print("[SARJAS] G READY",flush=True)
        return {"ok":True,"pod_id":pod_id,"endpoint":life.endpoint(pod_id,life.cfg.port),
                "health":health,"estimated_usd":estimated_usd}
    except Exception:
        if pod_id:
            print("[SARJAS] Startup failed; stopping GPU.",flush=True)
            try: life.stop(pod_id)
            except Exception as e: print("[SARJAS] WARNING: automatic stop failed: "+_redact(str(e)),flush=True)
        raise

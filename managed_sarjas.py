"""Managed Priority 25.5 flow: GPU off -> ready -> job -> MP4 -> GPU off."""
from __future__ import annotations
import os, pathlib
from runpod_lifecycle import RunpodLifecycle, PodConfig, APPROVAL_TEXT
from sarjas_client import SarJasBackend

class ManagedSarJas:
    def __init__(self, lifecycle: RunpodLifecycle, bootstrap_path="runtime/bootstrap.sh", handler_path="handler.py"):
        self.life=lifecycle
        self.bootstrap_path=bootstrap_path
        self.handler_path=handler_path
        self.pod_id=None

    def generate_t2v(self, prompt: str, destination: str, approval: str, **opts):
        if approval.strip()!=APPROVAL_TEXT:
            raise PermissionError("Explicit spending approval is required")
        pod_id=None
        try:
            pod_id=self.life.create(approval,self.bootstrap_path,self.handler_path)
            self.pod_id=pod_id
            self.life.wait_ready(pod_id)
            backend=SarJasBackend(self.life.endpoint(pod_id),self.life.cfg.api_token)
            job=backend.submit_t2v(prompt,**opts)
            jid=job["job_id"]
            status=backend.wait(jid)
            path=backend.download(jid,destination)
            return {"pod_id":pod_id,"job_id":jid,"status":status,"path":str(path)}
        finally:
            # Fail-safe billing protection: any Pod we created is stopped even
            # when readiness, generation, polling or download fails.
            if pod_id:
                try:self.life.stop(pod_id)
                except Exception:pass

def from_env():
    token=os.getenv("SARJAS_WORKER_TOKEN","")
    volume=os.getenv("SARJAS_NETWORK_VOLUME_ID","")
    cfg=PodConfig(
        network_volume_id=volume,
        api_token=token,
        gpu_id=os.getenv("SARJAS_GPU_ID","NVIDIA GeForce RTX 3090"),
        stop_after=os.getenv("SARJAS_STOP_AFTER","1h"),
    )
    return ManagedSarJas(RunpodLifecycle(cfg))

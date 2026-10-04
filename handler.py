import os, pathlib, subprocess, sys, time, uuid, threading
from typing import Any
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import runpod

VERSION="25.5"
ROOT=pathlib.Path(os.getenv("SARJAS_ROOT","/workspace/sarjas"))
MODEL=pathlib.Path(os.getenv("SARJAS_WAN_MODEL",str(ROOT/"models"/"Wan2.1-T2V-1.3B")))
WAN_REPO=pathlib.Path(os.getenv("SARJAS_WAN_REPO","/app/Wan2.1"))
OUT=ROOT/"outputs"
API_TOKEN=os.getenv("SARJAS_API_TOKEN","")
MODE=os.getenv("SARJAS_MODE","serverless").lower()
JOBS: dict[str,dict[str,Any]]={}
LOCK=threading.Lock()

def ensure_dirs():
    OUT.mkdir(parents=True,exist_ok=True)

def health():
    return {"ok":True,"service":"sarjas-ai-studio","version":VERSION,
      "mode":MODE,"storage_root":str(ROOT),"storage_mounted":ROOT.exists(),
      "model_path":str(MODEL),"model_present":MODEL.exists(),
      "wan_repo":str(WAN_REPO),"wan_present":(WAN_REPO/"generate.py").exists()}

def validate(payload):
    action=str(payload.get("action","health"))
    if action=="health": return
    if action!="t2v": raise ValueError("unsupported action")
    if not str(payload.get("prompt","")).strip(): raise ValueError("prompt is required")
    frames=int(payload.get("frames",17)); steps=int(payload.get("steps",10))
    if frames<1 or frames>401: raise ValueError("frames out of range")
    if steps<1 or steps>100: raise ValueError("steps out of range")
    if not MODEL.exists(): raise RuntimeError(f"Wan model missing: {MODEL}")
    if not (WAN_REPO/"generate.py").exists(): raise RuntimeError(f"Wan code missing: {WAN_REPO}")

def generate(payload,job_id):
    ensure_dirs(); validate(payload)
    started=time.time()
    output=OUT/f"{job_id}.mp4"
    cmd=[sys.executable,str(WAN_REPO/"generate.py"),"--task","t2v-1.3B",
      "--size",str(payload.get("size","832*480")),"--ckpt_dir",str(MODEL),
      "--prompt",str(payload["prompt"]),"--frame_num",str(int(payload.get("frames",17))),
      "--sample_steps",str(int(payload.get("steps",10))),"--sample_shift",str(float(payload.get("sample_shift",8))),
      "--sample_guide_scale",str(float(payload.get("guide_scale",6))),"--base_seed",str(int(payload.get("seed",-1))),
      "--save_file",str(output)]
    timeout=int(payload.get("timeout_seconds",1800))
    subprocess.run(cmd,check=True,cwd=str(WAN_REPO),timeout=timeout)
    if not output.exists() or output.stat().st_size==0: raise RuntimeError("Wan returned no valid MP4")
    return {"ok":True,"job_id":job_id,"status":"COMPLETED","output_path":str(output),
      "bytes":output.stat().st_size,"elapsed_seconds":round(time.time()-started,2)}

def serverless_handler(job):
    payload=job.get("input") or {}
    if payload.get("action","health")=="health": return health()
    return generate(payload,str(job.get("id") or uuid.uuid4()))

app=FastAPI(title="SarJas Backend",version=VERSION)
class JobRequest(BaseModel):
    action:str="t2v"; prompt:str=""; size:str="832*480"; frames:int=17; steps:int=10
    sample_shift:float=8; guide_scale:float=6; seed:int=-1; timeout_seconds:int=1800

def auth(authorization:str|None):
    if not API_TOKEN: raise HTTPException(503,"SARJAS_API_TOKEN is not configured")
    if authorization!=f"Bearer {API_TOKEN}": raise HTTPException(401,"Unauthorized")

@app.get("/health")
def http_health(): return health()

@app.post("/v1/jobs")
def submit(req:JobRequest,authorization:str|None=Header(default=None)):
    auth(authorization); payload=req.model_dump(); validate(payload)
    jid=str(uuid.uuid4())
    with LOCK: JOBS[jid]={"job_id":jid,"status":"QUEUED","created":time.time()}
    def work():
        with LOCK: JOBS[jid]["status"]="RUNNING"
        try:
            result=generate(payload,jid)
            with LOCK: JOBS[jid].update(result)
        except Exception as e:
            with LOCK: JOBS[jid].update({"status":"FAILED","error":str(e)})
    threading.Thread(target=work,daemon=True).start()
    return JOBS[jid]

@app.get("/v1/jobs/{job_id}")
def status(job_id:str,authorization:str|None=Header(default=None)):
    auth(authorization)
    with LOCK: item=JOBS.get(job_id)
    if not item: raise HTTPException(404,"Job not found")
    return item

if __name__=="__main__":
    if MODE=="pod":
        import uvicorn
        uvicorn.run(app,host="0.0.0.0",port=int(os.getenv("PORT","8000")))
    else:
        runpod.serverless.start({"handler":serverless_handler})

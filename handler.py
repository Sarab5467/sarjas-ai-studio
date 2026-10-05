import os, pathlib, sqlite3, subprocess, sys, time, uuid, threading, json
from typing import Any
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


VERSION="25.5"
ROOT=pathlib.Path(os.getenv("SARJAS_ROOT","/workspace/sarjas"))
MODEL=pathlib.Path(os.getenv("SARJAS_WAN_MODEL",str(ROOT/"models"/"Wan2.1-T2V-1.3B")))
WAN_REPO=pathlib.Path(os.getenv("SARJAS_WAN_REPO","/app/Wan2.1"))
OUT=ROOT/"outputs"; STATE=ROOT/"state"; DB=STATE/"jobs.sqlite3"
API_TOKEN=os.getenv("SARJAS_API_TOKEN","")
MODE=os.getenv("SARJAS_MODE","serverless").lower()
LOCK=threading.Lock()

def ensure_dirs():
    OUT.mkdir(parents=True,exist_ok=True); STATE.mkdir(parents=True,exist_ok=True)

def db_init():
    ensure_dirs()
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY,status TEXT NOT NULL,created REAL,updated REAL,
          request TEXT,result TEXT,error TEXT)""")
        c.execute("UPDATE jobs SET status='FAILED',error='worker restarted before completion',updated=? WHERE status IN ('QUEUED','RUNNING')",(time.time(),))

def db_put(jid,status,request=None,result=None,error=None):
    ensure_dirs(); now=time.time()
    with LOCK, sqlite3.connect(DB) as c:
        row=c.execute("SELECT id,created,request,result,error FROM jobs WHERE id=?",(jid,)).fetchone()
        if row:
            c.execute("UPDATE jobs SET status=?,updated=?,result=COALESCE(?,result),error=COALESCE(?,error) WHERE id=?",
                      (status,now,json.dumps(result) if result is not None else None,error,jid))
        else:
            c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",
                      (jid,status,now,now,json.dumps(request or {}),json.dumps(result) if result else None,error))

def db_get(jid):
    ensure_dirs()
    with sqlite3.connect(DB) as c:
        r=c.execute("SELECT id,status,created,updated,request,result,error FROM jobs WHERE id=?",(jid,)).fetchone()
    if not r:return None
    x={"job_id":r[0],"status":r[1],"created":r[2],"updated":r[3]}
    if r[5]: x.update(json.loads(r[5]))
    if r[6]: x["error"]=r[6]
    return x

def health():
    critical=[
      MODEL/"diffusion_pytorch_model.safetensors",
      MODEL/"models_t5_umt5-xxl-enc-bf16.pth",
      MODEL/"Wan2.1_VAE.pth",
      MODEL/"config.json",
    ]
    model_present=all(p.is_file() for p in critical)
    cuda_ready=False; gpu_name=None; flash_ready=False
    try:
        import torch
        cuda_ready=bool(torch.cuda.is_available())
        if cuda_ready: gpu_name=torch.cuda.get_device_name(0)
    except Exception:
        pass
    try:
        import flash_attn
        flash_ready=True
    except Exception:
        pass
    wan_present=(WAN_REPO/"generate.py").is_file()
    ready=model_present and wan_present and cuda_ready and flash_ready
    return {"ok":ready,"service":"sarjas-ai-studio","version":VERSION,"mode":MODE,
      "storage_root":str(ROOT),"storage_mounted":ROOT.exists(),"db_path":str(DB),
      "model_path":str(MODEL),"model_present":model_present,
      "wan_repo":str(WAN_REPO),"wan_present":wan_present,
      "cuda_ready":cuda_ready,"gpu_name":gpu_name,"flash_attn_ready":flash_ready}

def validate(p):
    action=str(p.get("action","health"))
    if action=="health":return
    if action!="t2v":raise ValueError("unsupported action")
    if not str(p.get("prompt","")).strip():raise ValueError("prompt is required")
    frames=int(p.get("frames",17));steps=int(p.get("steps",10))
    if not 1<=frames<=401:raise ValueError("frames out of range")
    if not 1<=steps<=100:raise ValueError("steps out of range")
    if not MODEL.exists():raise RuntimeError(f"Wan model missing: {MODEL}")
    if not (WAN_REPO/"generate.py").exists():raise RuntimeError(f"Wan code missing: {WAN_REPO}")

def generate(p,jid):
    ensure_dirs();validate(p);started=time.time();output=OUT/f"{jid}.mp4"
    cmd=[sys.executable,str(WAN_REPO/"generate.py"),"--task","t2v-1.3B","--size",str(p.get("size","832*480")),
      "--ckpt_dir",str(MODEL),"--prompt",str(p["prompt"]),"--frame_num",str(int(p.get("frames",17))),
      "--sample_steps",str(int(p.get("steps",10))),"--sample_shift",str(float(p.get("sample_shift",8))),
      "--sample_guide_scale",str(float(p.get("guide_scale",6))),"--base_seed",str(int(p.get("seed",-1))),
      "--save_file",str(output)]
    subprocess.run(cmd,check=True,cwd=str(WAN_REPO),timeout=int(p.get("timeout_seconds",1800)))
    if not output.exists() or output.stat().st_size==0:raise RuntimeError("Wan returned no valid MP4")
    return {"ok":True,"job_id":jid,"status":"COMPLETED","bytes":output.stat().st_size,
      "elapsed_seconds":round(time.time()-started,2),"result_url":f"/v1/jobs/{jid}/result"}

def serverless_handler(job):
    p=job.get("input") or {}
    if p.get("action","health")=="health":return health()
    return generate(p,str(job.get("id") or uuid.uuid4()))

app=FastAPI(title="SarJas Backend",version=VERSION)
class JobRequest(BaseModel):
    action:str="t2v";prompt:str="";size:str="832*480";frames:int=17;steps:int=10
    sample_shift:float=8;guide_scale:float=6;seed:int=-1;timeout_seconds:int=1800

def auth(a):
    if not API_TOKEN:raise HTTPException(503,"SARJAS_API_TOKEN is not configured")
    if a!=f"Bearer {API_TOKEN}":raise HTTPException(401,"Unauthorized")

@app.get("/health")
def http_health():return health()

@app.post("/v1/jobs")
def submit(req:JobRequest,authorization:str|None=Header(default=None)):
    auth(authorization);p=req.model_dump()
    try: validate(p)
    except ValueError as e: raise HTTPException(400,str(e))
    except RuntimeError as e: raise HTTPException(503,str(e))
    jid=str(uuid.uuid4());db_put(jid,"QUEUED",request=p)
    def work():
        db_put(jid,"RUNNING")
        try: db_put(jid,"COMPLETED",result=generate(p,jid))
        except Exception as e: db_put(jid,"FAILED",error=str(e))
    threading.Thread(target=work,daemon=True).start()
    return db_get(jid)

@app.get("/v1/jobs/{job_id}")
def status(job_id:str,authorization:str|None=Header(default=None)):
    auth(authorization);x=db_get(job_id)
    if not x:raise HTTPException(404,"Job not found")
    return x

@app.get("/v1/jobs/{job_id}/result")
def result(job_id:str,authorization:str|None=Header(default=None)):
    auth(authorization);x=db_get(job_id)
    if not x:raise HTTPException(404,"Job not found")
    if x["status"]!="COMPLETED":raise HTTPException(409,"Job not complete")
    p=OUT/f"{job_id}.mp4"
    if not p.exists():raise HTTPException(410,"Result file missing")
    return FileResponse(p,media_type="video/mp4",filename=f"sarjas-{job_id}.mp4")

if __name__=="__main__":
    db_init()
    if MODE=="pod":
        import uvicorn;uvicorn.run(app,host="0.0.0.0",port=int(os.getenv("PORT","8000")))
    else:
        try:
            import runpod
        except ImportError as e:
            raise RuntimeError("runpod package is required only for serverless mode; use SARJAS_MODE=pod for regular GPU Pods") from e
        runpod.serverless.start({"handler":serverless_handler})

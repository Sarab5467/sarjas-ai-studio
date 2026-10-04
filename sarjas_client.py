"""SarJas Windows-side backend client. No RunPod secret is stored here."""
import os,time,requests,pathlib
class SarJasBackend:
    def __init__(self,base_url=None,token=None,timeout=30):
        self.base=(base_url or os.getenv("SARJAS_BACKEND_URL","")).rstrip("/")
        self.token=token or os.getenv("SARJAS_API_TOKEN","")
        self.timeout=timeout
        if not self.base: raise ValueError("SARJAS_BACKEND_URL is required")
    @property
    def headers(self): return {"Authorization":f"Bearer {self.token}"}
    def health(self):
        r=requests.get(self.base+"/health",timeout=self.timeout);r.raise_for_status();return r.json()
    def submit_t2v(self,prompt,**opts):
        body={"action":"t2v","prompt":prompt,**opts}
        r=requests.post(self.base+"/v1/jobs",json=body,headers=self.headers,timeout=self.timeout);r.raise_for_status();return r.json()
    def status(self,jid):
        r=requests.get(f"{self.base}/v1/jobs/{jid}",headers=self.headers,timeout=self.timeout);r.raise_for_status();return r.json()
    def wait(self,jid,poll=5,max_wait=2400):
        end=time.time()+max_wait
        while time.time()<end:
            x=self.status(jid)
            if x["status"]=="COMPLETED": return x
            if x["status"]=="FAILED": raise RuntimeError(x.get("error","generation failed"))
            time.sleep(poll)
        raise TimeoutError("SarJas backend job timed out")
    def download(self,jid,destination):
        p=pathlib.Path(destination);p.parent.mkdir(parents=True,exist_ok=True)
        with requests.get(f"{self.base}/v1/jobs/{jid}/result",headers=self.headers,timeout=300,stream=True) as r:
            r.raise_for_status()
            with p.open("wb") as f:
                for chunk in r.iter_content(1024*1024):
                    if chunk:f.write(chunk)
        return p

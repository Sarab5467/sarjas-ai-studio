import os,tempfile,pathlib,importlib
os.environ["SARJAS_MODE"]="pod"
os.environ["SARJAS_API_TOKEN"]="test-secret"
root=pathlib.Path(tempfile.mkdtemp())/"sarjas"
model=root/"models"/"Wan2.1-T2V-1.3B";model.mkdir(parents=True)
wan=pathlib.Path(tempfile.mkdtemp())/"Wan2.1";wan.mkdir();(wan/"generate.py").write_text("# mock")
os.environ["SARJAS_ROOT"]=str(root);os.environ["SARJAS_WAN_MODEL"]=str(model);os.environ["SARJAS_WAN_REPO"]=str(wan)
import handler
from fastapi.testclient import TestClient
handler.db_init(); c=TestClient(handler.app); H={"Authorization":"Bearer test-secret"}

def test_health(): assert c.get("/health").json()["model_present"] is True
def test_auth_rejected(): assert c.get("/v1/jobs/nope").status_code==401
def test_bad_prompt(): assert c.post("/v1/jobs",headers=H,json={"prompt":""}).status_code==400
def test_persistent_db_roundtrip():
    handler.db_put("abc","QUEUED",request={"prompt":"x"});handler.db_put("abc","RUNNING")
    assert handler.db_get("abc")["status"]=="RUNNING"
def test_missing_job(): assert c.get("/v1/jobs/missing",headers=H).status_code==404
def test_result_not_ready():
    handler.db_put("pending","QUEUED",request={"prompt":"x"})
    assert c.get("/v1/jobs/pending/result",headers=H).status_code==409

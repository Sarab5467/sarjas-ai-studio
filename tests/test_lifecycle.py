import pytest
from runpod_lifecycle import RunpodLifecycle, PodConfig, APPROVAL_TEXT

def cfg(**kw):
    base=dict(network_volume_id="vol123",api_token="backend-secret",hf_token="hf-secret")
    base.update(kw)
    return PodConfig(**base)

def test_endpoint():
    assert RunpodLifecycle.endpoint("abc12345")=="https://abc12345-8000.proxy.runpod.net"

def test_requires_volume():
    with pytest.raises(ValueError):
        RunpodLifecycle(cfg(network_volume_id=""),runpodctl="runpodctl")

def test_requires_backend_token():
    with pytest.raises(ValueError):
        RunpodLifecycle(cfg(api_token=""),runpodctl="runpodctl")

def test_requires_hf_token():
    with pytest.raises(ValueError):
        RunpodLifecycle(cfg(hf_token=""),runpodctl="runpodctl")

def test_spend_approval_blocks_create():
    x=RunpodLifecycle(cfg(),runpodctl="runpodctl")
    with pytest.raises(PermissionError):
        x.create("NO")

def test_create_requires_persistent_volume_and_blocks_redownload(monkeypatch):
    x=RunpodLifecycle(cfg(),runpodctl="runpodctl")
    seen={}
    def fake_run(*args,**kwargs):
        seen["args"]=args
        return "Pod ID: abcdefgh1234"
    monkeypatch.setattr(x,"_run",fake_run)
    assert x.create(APPROVAL_TEXT)=="abcdefgh1234"
    args=seen["args"]
    assert args[args.index("--network-volume-id")+1]=="vol123"
    assert args[args.index("--volume-mount-path")+1]=="/workspace"
    assert args[args.index("--ports")+1]=="8000/http"
    env_arg=args[args.index("--env")+1]
    assert '"SARJAS_REQUIRE_PERSISTENT_MODEL":"1"' in env_arg

def test_parse_json_pod_id():
    assert RunpodLifecycle._parse_pod_id('{"id":"freshpod999"}')=="freshpod999"

def test_boot_failure_aborts_immediately(monkeypatch):
    x=RunpodLifecycle(cfg(),runpodctl="runpodctl")
    class R:
        ok=True
        def json(self):
            return {"boot_failed":True,"boot_error":"persistent Wan model missing"}
    monkeypatch.setattr("runpod_lifecycle.requests.get",lambda *a,**k:R())
    with pytest.raises(RuntimeError,match="persistent Wan model missing"):
        x.wait_ready("freshpod999",timeout=30,poll=0)

import pathlib, tempfile, pytest
from runpod_lifecycle import RunpodLifecycle, PodConfig, APPROVAL_TEXT

def test_endpoint():
    assert RunpodLifecycle.endpoint("abc12345")=="https://abc12345-8000.proxy.runpod.net"

def test_requires_volume():
    with pytest.raises(ValueError):
        RunpodLifecycle(PodConfig(network_volume_id="",api_token="x"),runpodctl="runpodctl")

def test_requires_backend_token():
    with pytest.raises(ValueError):
        RunpodLifecycle(PodConfig(network_volume_id="vol",api_token=""),runpodctl="runpodctl")

def test_spend_approval_blocks_create(tmp_path):
    b=tmp_path/"b"; h=tmp_path/"h"; b.write_text("x"); h.write_text("x")
    x=RunpodLifecycle(PodConfig(network_volume_id="vol",api_token="secret"),runpodctl="runpodctl")
    with pytest.raises(PermissionError):
        x.create("NO",str(b),str(h))

def test_start_requires_approval():
    x=RunpodLifecycle(PodConfig(network_volume_id="vol",api_token="secret"),runpodctl="runpodctl")
    with pytest.raises(PermissionError):
        x.start("pod12345","")


def test_create_builds_persistent_bootstrap_command(tmp_path, monkeypatch):
    x=RunpodLifecycle(PodConfig(network_volume_id="vol123",api_token="secret"),runpodctl="runpodctl")
    seen={}
    def fake_run(*args,**kwargs):
        seen["args"]=args
        return "Pod ID: abcdefgh1234"
    monkeypatch.setattr(x,"_run",fake_run)
    assert x.create(APPROVAL_TEXT)== "abcdefgh1234"
    args=seen["args"]
    assert "--network-volume-id" in args
    assert "vol123" in args
    assert "--volume-mount-path" in args
    assert "/workspace" in args
    assert "--ports" in args
    assert "8000/http" in args
    joined=" ".join(args)
    assert "raw.githubusercontent.com" not in joined
    assert "exec bash /workspace/sarjas/runtime/bootstrap.sh" in joined
    env_arg=args[args.index("--env")+1]
    assert "SARJAS_BOOTSTRAP_B64" in env_arg
    assert "SARJAS_HANDLER_B64" in env_arg

def test_endpoint_uses_dynamic_pod_id():
    assert RunpodLifecycle.endpoint("freshpod999",8000)=="https://freshpod999-8000.proxy.runpod.net"

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

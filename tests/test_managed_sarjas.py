from managed_sarjas import ManagedSarJas
from runpod_lifecycle import APPROVAL_TEXT

class Life:
    class C: api_token="secret"
    cfg=C()
    stopped=[]
    def create(self,*a): return "pod123456"
    def wait_ready(self,*a): raise RuntimeError("boot failed")
    def stop(self,p): self.stopped.append(p)
    def endpoint(self,p): return "https://example.invalid"

def test_failure_always_stops_gpu():
    x=Life(); m=ManagedSarJas(x,"b","h")
    try:m.generate_t2v("x","out.mp4",APPROVAL_TEXT)
    except RuntimeError:pass
    assert x.stopped==["pod123456"]

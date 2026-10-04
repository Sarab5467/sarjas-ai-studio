"""Zero-cost Runpod v2 capability probe for Priority 25.5.
Fetches the public OpenAPI document and reports the exact Pod mount keys that
mention global volumes. It does not authenticate, create, start, stop, or mutate anything.
"""
import json, re, requests

URL="https://api.runpod.io/v2/openapi.json"

def walk(x,path="$"):
    if isinstance(x,dict):
        for k,v in x.items():
            p=f"{path}.{k}"
            if "global" in k.lower() or (isinstance(v,str) and "global volume" in v.lower()):
                yield p,v
            yield from walk(v,p)
    elif isinstance(x,list):
        for i,v in enumerate(x):
            yield from walk(v,f"{path}[{i}]")

def main():
    r=requests.get(URL,timeout=30)
    r.raise_for_status()
    doc=r.json()
    hits=list(walk(doc))
    print("OPENAPI_OK", doc.get("info",{}).get("version","unknown"))
    if not hits:
        print("GLOBAL_VOLUME_SCHEMA_NOT_EXPOSED")
        return 2
    for p,v in hits[:80]:
        s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
        print(p, s[:500])
    return 0

if __name__=="__main__":
    raise SystemExit(main())

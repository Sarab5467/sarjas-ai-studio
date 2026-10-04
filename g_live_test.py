"""Priority 25.5-G live gate: GPU off -> backend ready -> GPU off.

This runner performs NO generation. It always attempts to stop a Pod it created.
"""
from __future__ import annotations
import os, sys, time
from managed_sarjas import from_env
from runpod_lifecycle import APPROVAL_TEXT

MAX_TEST_SECONDS = 20 * 60

def main() -> int:
    managed = from_env()
    pod_id = None
    started = time.time()
    try:
        pod_id = managed.life.create(APPROVAL_TEXT)
        managed.pod_id = pod_id
        print(f"G: Pod created: {pod_id}", flush=True)
        health = managed.life.wait_ready(pod_id, timeout=MAX_TEST_SECONDS, poll=10)
        elapsed = time.time() - started
        print(f"G: READY in {elapsed:.1f}s", flush=True)
        print(f"G: model_present={health.get('model_present')} wan_present={health.get('wan_present')}", flush=True)
        print("G PASS", flush=True)
        return 0
    except Exception as exc:
        print(f"G FAIL: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        if pod_id:
            try:
                managed.life.stop(pod_id)
                print(f"G: Pod stopped: {pod_id}", flush=True)
            except Exception as stop_exc:
                print(f"CRITICAL: automatic stop failed for {pod_id}: {stop_exc}", file=sys.stderr, flush=True)
                print("STOP THIS POD IN RUNPOD IMMEDIATELY.", file=sys.stderr, flush=True)

if __name__ == "__main__":
    raise SystemExit(main())

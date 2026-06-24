import sys, subprocess, time
print("start", flush=True)
t0 = time.time()
try:
    p = subprocess.run(
        [r"C:\Users\Admin\AppData\Roaming\npm\openclaw.cmd", "health", "--json"],
        capture_output=True, timeout=30, shell=True, text=False
    )
    print(f"rc={p.returncode} dt={time.time()-t0:.1f}s", flush=True)
    print("stdout[:300]=", p.stdout[:300], flush=True)
    print("stderr[:300]=", p.stderr[:300], flush=True)
except subprocess.TimeoutExpired as e:
    print(f"TIMEOUT dt={time.time()-t0:.1f}s", flush=True)
except Exception as e:
    print("EXC:", type(e).__name__, e, flush=True)

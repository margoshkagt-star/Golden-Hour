import subprocess, time
CMDS = [
    ["health", "--json"],
    ["agents", "list", "--json"],
    ["cron", "list", "--json"],
    ["cron", "list", "--all", "--json"],
    ["tasks", "list", "--json"],
]
for c in CMDS:
    t = time.time()
    p = subprocess.run([r"C:\Users\Admin\AppData\Roaming\npm\openclaw.cmd"] + c, capture_output=True, timeout=30, shell=True)
    print(f"{c[0]} {c[1] if len(c)>1 else ''} -> rc={p.returncode} dt={time.time()-t:.1f}s bytes={len(p.stdout)}", flush=True)

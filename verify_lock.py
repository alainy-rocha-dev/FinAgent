import sys


def parse_lock(p):
    deps = {}
    with open(p) as f:
        for l in f:
            l = l.strip()
            if "==" in l and not l.startswith("#"):
                k, v = l.split("==", 1)
                deps[k.lower().replace("_", "-")] = v
    return deps


def parse_lock_from_text(text):
    deps = {}
    for l in text.splitlines():
        l = l.strip()
        if "==" in l and not l.startswith("#"):
            k, v = l.split("==", 1)
            deps[k.lower().replace("_", "-")] = v
    return deps


committed = parse_lock("requirements.lock")

import subprocess
result = subprocess.run(["pip", "freeze"], capture_output=True, text=True)
generated = parse_lock_from_text(result.stdout)

diff = []
for k in set(committed) | set(generated):
    c = committed.get(k)
    g = generated.get(k)
    if c != g:
        diff.append(f"{k}: commit={c} != gerado={g}")
if diff:
    print("FALHA: requirements.lock diverge do pip freeze no Linux:")
    for d in sorted(diff):
        print(f"  {d}")
    sys.exit(1)
print("OK: requirements.lock commitado eh 100% identico ao pip freeze no Linux.")
import subprocess

# Step 1: pip freeze > /tmp/current_freeze.lock
result1 = subprocess.run(['pip', 'freeze'], capture_output=True, text=True)
with open('tmp_current_freeze.lock', 'w') as f:
    f.write(result1.stdout)

# Step 2: parse both lock files
def parse_lock(p):
    deps = {}
    with open(p) as f:
        for l in f:
            l = l.strip()
            if "==" in l and not l.startswith("#"):
                k, v = l.split("==", 1)
                deps[k.lower().replace("_", "-")] = v
    return deps

# Read the committed requirements.lock (current file on disk)
with open('requirements.lock', 'rb') as f:
    raw = f.read()
    # Remove BOM if present
    if raw.startswith(b'\xff\xfe'):
        raw = raw[2:]
    with open('requirements.lock', 'w') as f:
        f.write(raw.decode('utf-8'))

committed = parse_lock('requirements.lock')
generated = parse_lock('tmp_current_freeze.lock')

diff = []
for k in sorted(set(committed) | set(generated)):
    c = committed.get(k)
    g = generated.get(k)
    if c != g:
        diff.append(f"{k}: commit={c} != gerado={g}")

if diff:
    print("FALHA: requirements.lock diverge do pip freeze no Linux:")
    for d in diff[:30]:  # Show first 30 differences
        print(f"  {d}")
    if len(diff) > 30:
        print(f"  ... and {len(diff) - 30} more differences")
    print(f"\nTotal differences: {len(diff)}")
else:
    print("OK: requirements.lock commitado eh 100% identico ao pip freeze no Linux.")
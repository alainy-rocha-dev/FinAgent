def parse_lock(filepath):
    deps = {}
    with open(filepath) as f:
        for l in f:
            l = l.strip()
            if '==' in l and not l.startswith('#'):
                k, v = l.split('==', 1)
                deps[k.lower().replace('_', '-')] = v
    return deps

generated = parse_lock('/tmp/freeze_output.txt')
committed = parse_lock('C:\\sisanalisefinanceira\\requirements.lock')

diff = []
for k in set(committed) | set(generated):
    c = committed.get(k)
    g = generated.get(k)
    if c != g:
        diff.append(f'{k}: commit={c} != gerado={g}')

if diff:
    print('DIFFERENCES:')
    for d in sorted(diff):
        print('  ', d)
else:
    print('OK: requirements.lock matches pip freeze exactly')
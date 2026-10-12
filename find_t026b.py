with open('C:\\sisanalisefinanceira\\_reversa_forward\\002-finagent-agentpulse\\actions.md', 'rb') as f:
    content = f.read()
lines_bytes = content.split(b'\n')
for i, line in enumerate(lines_bytes, 1):
    if b'T026b' in line:
        print(f'Line {i}: {line.decode("utf-8", errors="replace")}')
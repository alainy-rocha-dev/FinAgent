with open('C:\\sisanalisefinanceira\\_reversa_forward\\002-finagent-agentpulse\\actions.md', 'rb') as f:
    content = f.read()
lines = content.split(b'\n')
for i, line in enumerate(lines, 1):
    if b'T026b' in line:
        print(f'Line {i}: {line.decode(\"utf-8\", errors=\"replace\")}')
# Also print line 45 and 46 for context
for i in [45, 46]:
    if i <= len(lines):
        print(f'Line {i}: {lines[i-1].decode("utf-8", errors="replace")}')
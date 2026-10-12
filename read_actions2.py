#!/usr/bin/env python
with open('C:\\sisanalisefinanceira\\_reversa_forward\\002-finagent-agentpulse\\actions.md', 'rb') as f:
    content = f.read()
lines = content.split(b'\n')
for i, line in enumerate(lines, 1):
    if b'T026b' in line:
        decoded = line.decode('utf-8', errors='replace')
        print('Line ' + str(i) + ': ' + decoded)
# Also print line 45 and 46 for context
for i in [45, 46]:
    if i <= len(lines):
        decoded = lines[i-1].decode('utf-8', errors='replace')
        print('Line ' + str(i) + ': ' + decoded)
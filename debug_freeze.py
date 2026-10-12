with open('/tmp/current_freeze.lock') as f:
    for i, l in enumerate(f):
        l = l.strip()
        has_eq = "==" in l
        starts_comment = l.startswith("#")
        print(f'Line {i}: has ==: {has_eq}, starts with #: {starts_comment}, content: {l[:80]}')
        if i > 5:
            break
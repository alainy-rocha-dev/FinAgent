import re, sys, json, urllib.request
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

MIN_AGE = timedelta(days=14)
EXC_FILE = ".github/scripts/version_exceptions.txt"

def load_exceptions():
    out = set()
    try:
        for line in open(EXC_FILE, encoding="utf-8"):
            line = line.split("#")[0].strip().lower()
            if line:
                out.add(line)
    except FileNotFoundError:
        pass
    return out

def pins(path="requirements.lock"):
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", line.strip())
        if m:
            yield m.group(1).lower(), m.group(2)

def upload_age(item):
    pkg, ver = item
    url = f"https://pypi.org/pypi/{pkg}/{ver}/json"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.load(r)
    times = [datetime.fromisoformat(u["upload_time_iso_8601"].replace("Z", "+00:00"))
             for u in data["urls"]]
    newest = max(times)
    return pkg, ver, newest, datetime.now(timezone.utc) - newest

def main():
    exc = load_exceptions()
    items = list(pins())
    if not items:
        print("ERRO: lockfile vazio")
        sys.exit(1)
    bad = []
    with ThreadPoolExecutor(8) as ex:
        for pkg, ver, when, age in ex.map(upload_age, items):
            tag = "OK"
            if age < MIN_AGE:
                tag = "EXCECAO" if f"{pkg}=={ver}" in exc else "FALHA"
                if tag == "FALHA":
                    bad.append(f"{pkg}=={ver}")
            print(f"[{tag}] {pkg}=={ver} {when:%Y-%m-%d} {age.days}d")
    if bad:
        print("::error::pacotes com menos de 14 dias: " + ", ".join(bad))
        sys.exit(1)

if __name__ == "__main__":
    main()
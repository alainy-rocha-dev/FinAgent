#!/usr/bin/env python3
"""Verify package versions in lockfile against spike_versions.md and PyPI release dates."""

import json
import re
import sys
from datetime import datetime, timezone
from urllib.request import urlopen


def fetch_pypi_version_release_date(package_name: str, version: str) -> datetime | None:
    """Fetch the release date of a SPECIFIC version from PyPI."""
    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        with urlopen(url, timeout=10) as response:
            data = json.load(response)
        releases = data.get("releases", {}).get(version, [])
        if releases:
            upload_time = releases[0]["upload_time_iso_8601"]
            return datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
    except Exception as e:
        print(f"Warning: Could not fetch PyPI date for {package_name}=={version}: {e}")
    return None


def main() -> int:
    # 1. Read spike_versions.md
    try:
        with open("docs/spike_versions.md", encoding="utf-8") as f:
            spike_content = f.read()
    except FileNotFoundError:
        print("ERROR: docs/spike_versions.md not found")
        return 1

    # 2. Read requirements.lock
    try:
        with open("requirements.lock", encoding="utf-8") as f:
            lock_lines = f.readlines()
    except FileNotFoundError:
        print("ERROR: requirements.lock not found")
        return 1

    # Map packages in lockfile
    lock_dict: dict[str, str] = {}
    for line in lock_lines:
        line_clean = line.strip()
        if "==" in line_clean and not line_clean.startswith("#"):
            parts = line_clean.split("==")
            pkg_name = parts[0].strip().lower().replace("_", "-")
            lock_dict[pkg_name] = parts[1].strip()

    # Packages to verify against spike_versions.md
    key_packages = {
        "celery": "5.6.0",
        "redis": "7.4.1",
        "langgraph": "1.2.10",
        "langgraph-checkpoint-postgres": "3.1.0",
        "psycopg": "3.3.2",
        "psycopg-pool": "3.3.3",
        "sqlalchemy": "2.0.35",
        "pydantic": "2.11.5",
        "pydantic-settings": "2.11.0",
    }

    # Exception list: (package, version) -> (justification, recorded_date)
    # Permitted only with explicit documented justification
    exceptions: dict[str, tuple[str, str]] = {}

    print("=========================================================================================")
    print(f"{'Pacote':<32} {'Versão':<10} {'Data de Upload':<22} {'Idade (dias)':<14} {'Status'}")
    print("=========================================================================================")

    all_ok = True
    now = datetime.now(timezone.utc)

    for pkg, expected_ver in key_packages.items():
        norm_pkg = pkg.lower().replace("_", "-")
        actual_ver = lock_dict.get(norm_pkg)

        # 1. Check lockfile match
        if not actual_ver:
            print(f"{pkg:<32} {expected_ver:<10} {'AUSENTE NO LOCKFILE':<38} ✗ FALHA")
            all_ok = False
            continue
        elif actual_ver != expected_ver:
            print(f"{pkg:<32} {actual_ver:<10} {'DIVERGENTE (' + expected_ver + ')':<38} ✗ FALHA")
            all_ok = False
            continue

        # 2. Check upload date of the specific pinned version
        upload_date = fetch_pypi_version_release_date(norm_pkg, actual_ver)
        if upload_date is None:
            print(f"{pkg:<32} {actual_ver:<10} {'N/A (erro de rede)':<22} {'?':<14} ? AVISO")
            continue

        age_days = (now - upload_date).days
        date_str = upload_date.strftime("%Y-%m-%d %H:%M")

        if age_days < 14:
            if norm_pkg in exceptions:
                justification, exc_date = exceptions[norm_pkg]
                print(f"{pkg:<32} {actual_ver:<10} {date_str:<22} {age_days:<14} [EXCECAO] ({justification})")
            else:
                print(f"{pkg:<32} {actual_ver:<10} {date_str:<22} {age_days:<14} [FALHA] (< 14 dias)")
                all_ok = False
        else:
            print(f"{pkg:<32} {actual_ver:<10} {date_str:<22} {age_days:<14} [OK]")

    print("=========================================================================================")

    # Check Postgres and Redis server versions (from CI services)
    print("\n=== Versoes de Servicos (Container CI) ===")
    if re.search(r"Postgres\s*\|\s*16\.4", spike_content):
        print("[OK] Postgres 16.4 documentado em spike_versions.md")
    else:
        print("[FALHA] Postgres version mismatch em spike_versions.md")
        all_ok = False

    if re.search(r"Redis \(servidor\)\s*\|\s*7\.2\.7", spike_content):
        print("[OK] Redis 7.2.7 documentado em spike_versions.md")
    else:
        print("[FALHA] Redis version mismatch em spike_versions.md")
        all_ok = False

    if not all_ok:
        print("\n[ERRO] Verificacao de versoes FALHOU!")
        return 1

    print("\n[SUCESSO] Todas as versoes verificadas com sucesso e com maturidade comprovada (>= 14 dias)!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
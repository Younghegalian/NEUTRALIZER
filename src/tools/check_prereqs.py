from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from src import config
from src.collectors.kaggle_downloader import has_kaggle_credentials
from src.collectors.sec_delisting_collector import sec_user_agent
from src.secrets import load_local_env


REQUIRED_PACKAGES = ["pandas", "numpy", "duckdb", "pyarrow", "requests", "tqdm", "dateutil"]
OPTIONAL_PACKAGES = ["kaggle"]


def _package_status(name: str) -> str:
    return "OK" if importlib.util.find_spec(name) else "MISSING"


def _path_status(path: Path) -> str:
    return "OK" if path.exists() else "MISSING"


def check_prereqs() -> bool:
    load_local_env()
    config.ensure_directories()
    ok = True

    print("FONA prerequisite check")
    print()
    print("Python packages:")
    for package in REQUIRED_PACKAGES:
        status = _package_status(package)
        ok = ok and status == "OK"
        print(f"  {package}: {status}")
    for package in OPTIONAL_PACKAGES:
        print(f"  {package}: {_package_status(package)} (optional)")

    print()
    print("Local folders:")
    for path in [
        config.RAW_STOOQ_DIR,
        config.RAW_KAGGLE_DELISTED_DIR,
        config.RAW_FMP_DIR,
        config.RAW_YAHOO_DIR,
        config.STAGING_DIR,
        config.NORMALIZED_DIR,
        config.RESEARCH_DIR,
    ]:
        print(f"  {path}: {_path_status(path)}")

    print()
    print("Credentials:")
    kaggle_status = "OK" if has_kaggle_credentials() else "OPTIONAL / NOT SET"
    print(f"  Kaggle API: {kaggle_status}")
    print(f"  FMP_API_KEY: {'OK' if os.getenv('FMP_API_KEY') else 'OPTIONAL / NOT SET'}")
    configured_sec_user_agent = sec_user_agent()
    sec_user_agent_status = "OK" if os.getenv("FONA_SEC_USER_AGENT") and "@" in configured_sec_user_agent else "RECOMMENDED / NOT SET"
    print(f"  FONA_SEC_USER_AGENT: {sec_user_agent_status}")

    print()
    print("Raw data currently present:")
    print(f"  Stooq files: {sum(1 for _ in config.RAW_STOOQ_DIR.rglob('*') if _.is_file()):,}")
    print(f"  Kaggle delisted CSVs: {sum(1 for _ in config.RAW_KAGGLE_DELISTED_DIR.rglob('*.csv')):,}")

    if not ok:
        print()
        print("Install missing packages with: python -m pip install -r requirements.txt")

    if kaggle_status != "OK":
        print()
        print("Kaggle is optional and only needed for automatic delisted archive download.")
        print("Place the new token at ~/.kaggle/access_token or set KAGGLE_API_TOKEN.")
        print("Legacy ~/.kaggle/kaggle.json and KAGGLE_USERNAME/KAGGLE_KEY also work.")

    if sec_user_agent_status != "OK":
        print()
        print("Set FONA_SEC_USER_AGENT before SEC collection to identify your app and contact email.")

    return ok


if __name__ == "__main__":
    raise SystemExit(0 if check_prereqs() else 1)

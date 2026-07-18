from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from src import config
from src.secrets import load_local_env


KAGGLE_DATASET = "rodas86/arandkei-historical-delisted-assets-archive"


def has_kaggle_credentials() -> bool:
    load_local_env()
    if os.getenv("KAGGLE_API_TOKEN"):
        return True

    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        return True

    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    access_token = Path.home() / ".kaggle" / "access_token"
    return kaggle_json.exists() or access_token.exists()


def has_kaggle_package() -> bool:
    return importlib.util.find_spec("kaggle") is not None


def download_kaggle_delisted_dataset(
    raw_dir: Path = config.RAW_KAGGLE_DELISTED_DIR,
    dataset: str = KAGGLE_DATASET,
    unzip: bool = True,
    force: bool = False,
) -> bool:
    raw_dir.mkdir(parents=True, exist_ok=True)

    if any(raw_dir.rglob("*.csv")) and not force:
        print(f"[kaggle_download] Existing CSV files found in {raw_dir}; skipping download.")
        return True

    if not has_kaggle_credentials():
        print("[kaggle_download] Kaggle credentials not found; skipping download.")
        print("[kaggle_download] Add ~/.kaggle/access_token or set KAGGLE_API_TOKEN.")
        print("[kaggle_download] Legacy ~/.kaggle/kaggle.json and KAGGLE_USERNAME/KAGGLE_KEY also work.")
        return False

    if not has_kaggle_package():
        print("[kaggle_download] Python kaggle package not installed; skipping download.")
        print("[kaggle_download] Install dependencies with: python -m pip install -r requirements.txt")
        return False

    command = [
        sys.executable,
        "-m",
        "kaggle",
        "datasets",
        "download",
        "-d",
        dataset,
        "-p",
        str(raw_dir),
    ]
    if unzip:
        command.append("--unzip")
    if force:
        command.append("--force")

    print(f"[kaggle_download] Downloading {dataset} to {raw_dir}")
    subprocess.run(command, check=True)
    return any(raw_dir.rglob("*.csv"))


if __name__ == "__main__":
    config.ensure_directories()
    download_kaggle_delisted_dataset()

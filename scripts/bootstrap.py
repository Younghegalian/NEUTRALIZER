from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = PROJECT_ROOT / ".venv"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _run(args: list[str], cwd: Path = PROJECT_ROOT) -> None:
    print("$ " + " ".join(str(arg) for arg in args), flush=True)
    subprocess.run([str(arg) for arg in args], cwd=str(cwd), check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a local FONA development environment.")
    parser.add_argument("--skip-install", action="store_true", help="Skip requirements installation.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip the final unit test run.")
    parser.add_argument("--with-secrets", action="store_true", help="Prompt for optional Kaggle/FMP credentials.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if sys.version_info < (3, 10):
        raise RuntimeError("FONA requires Python 3.10+.")

    python = _venv_python()
    if not python.exists():
        _run([sys.executable, "-m", "venv", str(VENV_DIR)])

    if not args.skip_install:
        _run([python, "-m", "pip", "install", "--upgrade", "pip"])
        _run([python, "-m", "pip", "install", "-r", "requirements.txt"])

    if args.with_secrets:
        _run([python, "scripts/setup_secrets.py"])

    _run([python, "-m", "src.tools.check_prereqs"])

    if not args.skip_tests:
        _run([python, "-m", "unittest", "discover", "-s", "tests"])

    print()
    print("Bootstrap complete.")
    print("Next steps:")
    print("  python scripts/daily_maintenance.py --dry-run")
    print("  python scripts/daily_maintenance.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

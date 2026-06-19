from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_windows_store_alias(path: str) -> bool:
    return "Microsoft\\WindowsApps" in path or "Microsoft/WindowsApps" in path


def _is_python_candidate(candidate: str | Path) -> bool:
    try:
        result = subprocess.run(
            [
                str(candidate),
                "-c",
                "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def resolve_python() -> str:
    override = os.environ.get("FONA_PYTHON")
    if override:
        if _is_python_candidate(override):
            return override
        raise RuntimeError(f"FONA_PYTHON is not a usable Python 3.10+ executable: {override}")

    candidates: list[str] = []
    if sys.executable:
        candidates.append(sys.executable)

    candidates.extend(
        str(path)
        for path in [
            PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
            PROJECT_ROOT / ".venv" / "bin" / "python",
        ]
    )

    for command in ["python3", "python"]:
        found = shutil.which(command)
        if found and not _is_windows_store_alias(found):
            candidates.append(found)

    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        if Path(normalized).exists() or shutil.which(normalized):
            if _is_python_candidate(normalized):
                return normalized

    raise RuntimeError("No usable Python 3.10+ executable found. Set FONA_PYTHON.")


def run_checked(args: list[str], cwd: Path = PROJECT_ROOT) -> None:
    print("$ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=str(cwd), check=True)


def run_python_module(python: str, module: str, *args: object) -> None:
    run_checked([python, "-m", module, *[str(arg) for arg in args]])

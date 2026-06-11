from __future__ import annotations

import os
from pathlib import Path

from src import config


def load_local_env(path: Path | None = None) -> None:
    env_path = path or (config.PROJECT_ROOT / ".env.local")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

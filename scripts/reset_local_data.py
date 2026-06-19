from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from _operator_common import PROJECT_ROOT


DATA_ROOT = PROJECT_ROOT / "data"
RAW_DIRS = ["sec", "fmp", "kaggle_delisted", "stooq", "yahoo"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview or reset local FONA data artifacts.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--generated-only", action="store_true", help="Remove generated artifacts but keep raw caches. This is the default.")
    mode.add_argument("--all-local-data", action="store_true", help="Remove generated artifacts and raw source caches.")
    parser.add_argument("--force", action="store_true", help="Actually remove targets. Without this, the command only previews.")
    return parser.parse_args()


def _targets(all_local_data: bool) -> list[Path]:
    base = [DATA_ROOT / "pit_market.duckdb", DATA_ROOT / "staging", DATA_ROOT / "normalized", DATA_ROOT / "research"]
    if all_local_data:
        base.insert(1, DATA_ROOT / "raw")
    return base


def _resolve_existing_targets(targets: list[Path]) -> list[Path]:
    if not DATA_ROOT.exists():
        return []

    data_root = DATA_ROOT.resolve()
    existing: list[Path] = []
    for target in targets:
        if not target.exists():
            continue
        resolved = target.resolve()
        if resolved != data_root and data_root not in resolved.parents:
            raise RuntimeError(f"Refusing to remove path outside data root: {resolved}")
        existing.append(resolved)
    return existing


def _touch_gitkeep(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitkeep").touch()


def _recreate_layout() -> None:
    for name in ["raw", "staging", "normalized", "research"]:
        _touch_gitkeep(DATA_ROOT / name)
    for name in RAW_DIRS:
        _touch_gitkeep(DATA_ROOT / "raw" / name)


def main() -> int:
    args = parse_args()
    all_local_data = bool(args.all_local_data)
    existing_targets = _resolve_existing_targets(_targets(all_local_data))

    if not DATA_ROOT.exists():
        print("No data directory found.")
        return 0
    if not existing_targets:
        print("No local data artifacts found.")
        return 0

    print("FONA local data reset")
    print(f"Project: {PROJECT_ROOT}")
    print(f"Mode: {'all local data' if all_local_data else 'generated artifacts only'}")
    print("Targets:")
    for target in existing_targets:
        print(f"  {target}")

    if not args.force:
        print()
        print("Preview only. Re-run with --force to remove these paths.")
        return 0

    for target in existing_targets:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        print(f"Removed {target}")

    _recreate_layout()
    print("Local data state reset complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

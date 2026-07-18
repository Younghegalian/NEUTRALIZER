from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from _operator_common import PROJECT_ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Store local FONA credentials and provider settings.")
    parser.add_argument("--kaggle-token", default=None, help="Kaggle access token. Prefer the prompt over shell history.")
    parser.add_argument("--fmp-api-key", default=None, help="FMP API key. Prefer the prompt over shell history.")
    parser.add_argument(
        "--sec-user-agent",
        default=None,
        help="SEC fair-access User-Agent, for example 'YourApp/1.0 email@example.com'.",
    )
    parser.add_argument("--skip-kaggle", action="store_true", help="Do not prompt for or update the Kaggle token.")
    parser.add_argument("--skip-fmp", action="store_true", help="Do not prompt for or update FMP_API_KEY.")
    parser.add_argument("--skip-sec-user-agent", action="store_true", help="Do not prompt for or update FONA_SEC_USER_AGENT.")
    parser.add_argument("--clear-fmp-api-key", action="store_true", help="Remove FMP_API_KEY from .env.local.")
    parser.add_argument("--clear-sec-user-agent", action="store_true", help="Remove FONA_SEC_USER_AGENT from .env.local.")
    parser.add_argument("--non-interactive", action="store_true", help="Do not prompt; only use supplied arguments.")
    return parser.parse_args()


def _prompt_secret(label: str, non_interactive: bool) -> str:
    if non_interactive:
        return ""
    value = getpass.getpass(f"{label}: ")
    return value.strip()


def _prompt_value(label: str, non_interactive: bool) -> str:
    if non_interactive:
        return ""
    value = input(f"{label}: ")
    return value.strip()


def _save_kaggle_token(token: str) -> None:
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    token_path = kaggle_dir / "access_token"
    token_path.write_text(token, encoding="ascii")
    if os.name != "nt":
        token_path.chmod(0o600)
    print(f"Saved Kaggle token to {token_path}")


def _read_env_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _set_env_value(path: Path, key: str, value: str | None) -> None:
    lines = [line for line in _read_env_lines(path) if not line.strip().startswith(f"{key}=")]
    if value:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> int:
    args = parse_args()

    kaggle_token = None
    if not args.skip_kaggle:
        kaggle_token = args.kaggle_token if args.kaggle_token is not None else _prompt_secret("KAGGLE_API_TOKEN, press Enter to skip", args.non_interactive)

    fmp_key = None
    if not args.skip_fmp and not args.clear_fmp_api_key:
        fmp_key = args.fmp_api_key if args.fmp_api_key is not None else _prompt_secret("FMP_API_KEY, press Enter to skip", args.non_interactive)

    sec_user_agent = None
    if not args.skip_sec_user_agent and not args.clear_sec_user_agent:
        sec_user_agent = (
            args.sec_user_agent
            if args.sec_user_agent is not None
            else _prompt_value("FONA_SEC_USER_AGENT, press Enter to skip", args.non_interactive)
        )

    if kaggle_token:
        _save_kaggle_token(kaggle_token)
    elif not args.skip_kaggle:
        print("Skipped Kaggle token.")

    env_path = PROJECT_ROOT / ".env.local"
    if args.clear_fmp_api_key:
        _set_env_value(env_path, "FMP_API_KEY", None)
        print(f"Removed FMP_API_KEY from {env_path}")
    elif fmp_key:
        _set_env_value(env_path, "FMP_API_KEY", fmp_key)
        print(f"Saved FMP key to {env_path}")
    elif not args.skip_fmp:
        print("Skipped FMP key.")

    if args.clear_sec_user_agent:
        _set_env_value(env_path, "FONA_SEC_USER_AGENT", None)
        print(f"Removed FONA_SEC_USER_AGENT from {env_path}")
    elif sec_user_agent:
        _set_env_value(env_path, "FONA_SEC_USER_AGENT", sec_user_agent)
        print(f"Saved SEC User-Agent to {env_path}")
    elif not args.skip_sec_user_agent:
        print("Skipped SEC User-Agent.")

    print("Done. Run: python scripts/daily_maintenance.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

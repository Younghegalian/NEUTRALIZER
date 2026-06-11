from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


STOOQ_SUFFIX_RE = re.compile(r"\.(US|NYSE|NASDAQ|AMEX)$", re.IGNORECASE)


def normalize_symbol(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    symbol = str(value).strip()
    if not symbol:
        return None

    symbol = Path(symbol).stem if any(symbol.lower().endswith(ext) for ext in [".csv", ".txt"]) else symbol
    symbol = symbol.strip().upper()
    symbol = STOOQ_SUFFIX_RE.sub("", symbol)
    symbol = symbol.replace(" ", "")
    symbol = symbol.replace("-", ".")
    return symbol or None


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    if value is None or pd.isna(value):
        return pd.NaT

    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        parsed = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
        if pd.isna(parsed):
            return pd.NaT
        return pd.Timestamp(parsed).normalize()

    parsed = pd.to_datetime(value, errors="coerce", utc=False)
    if pd.isna(parsed):
        return pd.NaT
    return pd.Timestamp(parsed).normalize()


def parse_cli_date(value: str | None) -> date | None:
    if value is None:
        return None
    if str(value).lower() == "today":
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def read_parquet_if_exists(path: Path, columns: Iterable[str]) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame(columns=list(columns))


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def normalize_column_name(name: object) -> str:
    cleaned = str(name).strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    return cleaned.strip("_")


def first_present(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    available = set(columns)
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def empty_frame(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))

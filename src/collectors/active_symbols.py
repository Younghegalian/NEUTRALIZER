from __future__ import annotations

from io import StringIO

import pandas as pd

from src import config
from src.utils import normalize_symbol


NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


def _read_pipe_table(url: str) -> pd.DataFrame:
    import requests

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), sep="|")


def fetch_active_us_symbols(include_etfs: bool = True, liquid_equity_like: bool = True) -> pd.DataFrame:
    nasdaq = _read_pipe_table(NASDAQ_LISTED_URL)
    nasdaq = nasdaq[nasdaq["Symbol"].astype(str).str.startswith("File Creation Time:") == False].copy()
    nasdaq = nasdaq.rename(columns={"Symbol": "symbol"})
    nasdaq["exchange"] = "NASDAQ"

    other = _read_pipe_table(OTHER_LISTED_URL)
    other = other[other["ACT Symbol"].astype(str).str.startswith("File Creation Time:") == False].copy()
    other = other.rename(columns={"ACT Symbol": "symbol"})

    frames = [
        nasdaq[["symbol", "Security Name", "ETF", "Test Issue", "exchange"]],
        other[["symbol", "Security Name", "ETF", "Test Issue", "Exchange"]],
    ]
    frames[1] = frames[1].rename(columns={"Exchange": "exchange"})
    symbols = pd.concat(frames, ignore_index=True)
    symbols["symbol"] = symbols["symbol"].map(normalize_symbol)
    symbols = symbols[symbols["symbol"].notna()]
    symbols = symbols[symbols["Test Issue"].astype(str).str.upper().eq("N")]
    if not include_etfs:
        symbols = symbols[symbols["ETF"].astype(str).str.upper().ne("Y")]
    if liquid_equity_like:
        name = symbols["Security Name"].astype(str).str.lower()
        is_etf = symbols["ETF"].astype(str).str.upper().eq("Y")
        include_name = name.str.contains(
            r"common stock|ordinary share|ordinary shares|american depositary|depositary shares|\badr\b|\bads\b",
            regex=True,
        )
        exclude_name = name.str.contains(
            r"warrant|rights|\bunit\b|\bunits\b|preferred|preference|note|debenture|bond|baby bond",
            regex=True,
        )
        symbols = symbols[(is_etf | include_name) & ~exclude_name]

    symbols = symbols.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
    return symbols


def active_symbol_list(include_etfs: bool = True, liquid_equity_like: bool = True) -> list[str]:
    symbols = fetch_active_us_symbols(
        include_etfs=include_etfs,
        liquid_equity_like=liquid_equity_like,
    )["symbol"].tolist()
    if include_etfs:
        symbols.extend(config.BACKTEST_LABEL_ETF_SEED_SYMBOLS)
    return sorted({symbol for symbol in symbols if normalize_symbol(symbol)})

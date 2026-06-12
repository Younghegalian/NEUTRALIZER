from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, normalize_symbol, read_parquet_if_exists, write_parquet


TERMINAL_POLICY = "last_close_on_or_before_delisting_event_no_zero_fill"
LIFECYCLE_REASON = "base_universe; lifecycle_date<=delisting_event"


def _compact_symbol(value: object) -> str | None:
    symbol = normalize_symbol(value)
    if symbol is None:
        return None
    compact = "".join(ch for ch in symbol.upper() if ch.isalnum())
    return compact or None


def _prepare_symbol_master(symbol_master: pd.DataFrame) -> pd.DataFrame:
    if symbol_master.empty:
        return pd.DataFrame(columns=["symbol", "compact_symbol", "first_date", "has_delisted_source"])

    result = symbol_master[["symbol", "first_date", "has_delisted_source"]].copy()
    result["symbol"] = result["symbol"].map(normalize_symbol)
    result["compact_symbol"] = result["symbol"].map(_compact_symbol)
    result["first_date"] = pd.to_datetime(result["first_date"], errors="coerce").dt.normalize()
    result["has_delisted_source"] = result["has_delisted_source"].fillna(False).astype(bool)
    return result.dropna(subset=["symbol", "compact_symbol"])


def _events_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    if not rows:
        return empty_frame(config.SECURITY_EVENTS_COLUMNS)
    result = pd.DataFrame(rows)
    result["event_date"] = pd.to_datetime(result["event_date"], errors="coerce").dt.normalize()
    result = result.dropna(subset=["symbol", "event_type", "event_date"])
    result = result[config.SECURITY_EVENTS_COLUMNS]
    return result.sort_values(["symbol", "event_type", "event_date", "source"]).reset_index(drop=True)


def build_security_events_df(
    symbol_master: pd.DataFrame,
    fmp_delisted_metadata: pd.DataFrame,
    sec_delisted_candidates: pd.DataFrame,
) -> pd.DataFrame:
    symbols = _prepare_symbol_master(symbol_master)
    if symbols.empty:
        return empty_frame(config.SECURITY_EVENTS_COLUMNS)

    rows: list[dict[str, object]] = []

    for record in symbols.itertuples(index=False):
        if pd.notna(record.first_date):
            rows.append(
                {
                    "symbol": record.symbol,
                    "event_type": "listing",
                    "event_date": record.first_date,
                    "source": "price_first_date",
                    "source_event_id": "",
                    "source_symbol": record.symbol,
                    "confidence": "coverage_start",
                    "notes": "First canonical daily price date; not an exchange listing date.",
                }
            )

    delisted_symbols = symbols[symbols["has_delisted_source"]].copy()
    delisted_symbol_lookup = delisted_symbols[["symbol", "compact_symbol"]].drop_duplicates()

    if not fmp_delisted_metadata.empty:
        fmp = fmp_delisted_metadata.copy()
        fmp["source_symbol"] = fmp.get("symbol", pd.Series(dtype="object")).map(normalize_symbol)
        fmp["compact_symbol"] = fmp["source_symbol"].map(_compact_symbol)
        fmp["event_date"] = pd.to_datetime(fmp.get("delistedDate"), errors="coerce").dt.normalize()
        fmp["ipo_date"] = pd.to_datetime(fmp.get("ipoDate"), errors="coerce").dt.normalize()
        fmp = fmp.drop(columns=["symbol"], errors="ignore")
        fmp = fmp.merge(delisted_symbol_lookup, on="compact_symbol", how="inner")

        for record in fmp.dropna(subset=["event_date"]).itertuples(index=False):
            rows.append(
                {
                    "symbol": record.symbol,
                    "event_type": "delisting",
                    "event_date": record.event_date,
                    "source": "fmp_delisted_date",
                    "source_event_id": "",
                    "source_symbol": record.source_symbol,
                    "confidence": "high",
                    "notes": "FMP delistedDate applied only to symbols with delisted-source price coverage.",
                }
            )

        for record in fmp.dropna(subset=["ipo_date"]).itertuples(index=False):
            rows.append(
                {
                    "symbol": record.symbol,
                    "event_type": "listing",
                    "event_date": record.ipo_date,
                    "source": "fmp_ipo_date",
                    "source_event_id": "",
                    "source_symbol": record.source_symbol,
                    "confidence": "medium",
                    "notes": "FMP ipoDate for a delisted-source symbol.",
                }
            )

    if not sec_delisted_candidates.empty:
        sec = sec_delisted_candidates.copy()
        sec["source_symbol"] = sec.get("candidate_symbol", pd.Series(dtype="object")).map(normalize_symbol)
        sec["compact_symbol"] = sec["source_symbol"].map(_compact_symbol)
        sec["event_date"] = pd.to_datetime(sec.get("date_filed"), errors="coerce").dt.normalize()
        sec = sec.merge(delisted_symbol_lookup, on="compact_symbol", how="inner")
        sec = sec.dropna(subset=["event_date", "symbol"])

        if not sec.empty:
            grouped = (
                sec.groupby("symbol", as_index=False)
                .agg(
                    event_date=("event_date", "min"),
                    source_symbol=("source_symbol", "first"),
                    cik_count=("cik", "nunique"),
                    filing_count=("event_date", "size"),
                )
                .reset_index(drop=True)
            )
            for record in grouped.itertuples(index=False):
                rows.append(
                    {
                        "symbol": record.symbol,
                        "event_type": "delisting",
                        "event_date": record.event_date,
                        "source": "sec_form25_date_filed",
                        "source_event_id": f"ciks={record.cik_count};filings={record.filing_count}",
                        "source_symbol": record.source_symbol,
                        "confidence": "proxy",
                        "notes": "SEC Form 25/25-NSE filing date proxy; exact exchange delisting date may differ.",
                    }
                )

    return _events_frame(rows)


def select_delisting_events(security_events: pd.DataFrame) -> pd.DataFrame:
    if security_events.empty:
        return empty_frame(config.SECURITY_EVENTS_COLUMNS)

    delistings = security_events[security_events["event_type"] == "delisting"].copy()
    if delistings.empty:
        return empty_frame(config.SECURITY_EVENTS_COLUMNS)

    source_priority = {
        "fmp_delisted_date": 1,
        "sec_form25_date_filed": 2,
    }
    delistings["source_priority"] = delistings["source"].map(source_priority).fillna(99)
    delistings = delistings.sort_values(["symbol", "source_priority", "event_date"])
    selected = delistings.drop_duplicates("symbol", keep="first")
    return selected[config.SECURITY_EVENTS_COLUMNS].reset_index(drop=True)


def build_terminal_events_df(
    daily_prices: pd.DataFrame,
    selected_delisting_events: pd.DataFrame,
) -> pd.DataFrame:
    if selected_delisting_events.empty:
        return empty_frame(config.TERMINAL_EVENTS_COLUMNS)

    events = selected_delisting_events.copy()
    events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce").dt.normalize()

    prices = daily_prices.copy()
    if prices.empty:
        rows = []
        for record in events.itertuples(index=False):
            rows.append(_missing_terminal_row(record))
        return pd.DataFrame(rows, columns=config.TERMINAL_EVENTS_COLUMNS)

    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.dropna(subset=["symbol", "date"]).sort_values(["symbol", "date"])
    prices["previous_close"] = prices.groupby("symbol")["close"].shift(1)

    candidates = events[["symbol", "event_date", "source", "confidence"]].merge(
        prices[["symbol", "date", "close", "previous_close", "source"]],
        on="symbol",
        how="left",
        suffixes=("_event", "_price"),
    )
    candidates = candidates[candidates["date"] <= candidates["event_date"]]
    candidates = candidates.sort_values(["symbol", "event_date", "date"])
    terminal_prices = candidates.groupby(["symbol", "event_date"], as_index=False).tail(1)

    rows = []
    for record in events.itertuples(index=False):
        match = terminal_prices[
            (terminal_prices["symbol"] == record.symbol)
            & (terminal_prices["event_date"] == record.event_date)
        ]
        if match.empty:
            rows.append(_missing_terminal_row(record))
            continue

        terminal = match.iloc[0]
        previous_close = terminal["previous_close"]
        terminal_price = terminal["close"]
        terminal_return = pd.NA
        if pd.notna(previous_close) and previous_close > 0 and pd.notna(terminal_price):
            terminal_return = (terminal_price / previous_close) - 1.0

        rows.append(
            {
                "symbol": record.symbol,
                "event_date": record.event_date,
                "terminal_date": terminal["date"],
                "terminal_price": terminal_price,
                "previous_close": previous_close,
                "terminal_return": terminal_return,
                "has_terminal_price": pd.notna(terminal_price),
                "price_source": terminal["source_price"],
                "event_source": record.source,
                "event_confidence": record.confidence,
                "terminal_policy": TERMINAL_POLICY,
                "notes": "Terminal price is last available close on or before event_date; no zero fill applied.",
            }
        )

    result = pd.DataFrame(rows, columns=config.TERMINAL_EVENTS_COLUMNS)
    for column in ["event_date", "terminal_date"]:
        result[column] = pd.to_datetime(result[column], errors="coerce").dt.normalize()
    return result.sort_values(["event_date", "symbol"]).reset_index(drop=True)


def _missing_terminal_row(record) -> dict[str, object]:
    return {
        "symbol": record.symbol,
        "event_date": record.event_date,
        "terminal_date": pd.NaT,
        "terminal_price": pd.NA,
        "previous_close": pd.NA,
        "terminal_return": pd.NA,
        "has_terminal_price": False,
        "price_source": "",
        "event_source": record.source,
        "event_confidence": record.confidence,
        "terminal_policy": TERMINAL_POLICY,
        "notes": "No price found on or before event_date; no zero fill applied.",
    }


def build_backtest_universe_df(
    universe_membership: pd.DataFrame,
    selected_delisting_events: pd.DataFrame,
    universe_name: str = config.BACKTEST_UNIVERSE_NAME,
) -> pd.DataFrame:
    if universe_membership.empty:
        return empty_frame(config.BACKTEST_UNIVERSE_COLUMNS)

    membership = universe_membership.copy()
    membership["date"] = pd.to_datetime(membership["date"], errors="coerce").dt.normalize()

    if selected_delisting_events.empty:
        result = membership[["date", "symbol", "reason"]].copy()
        result["universe_name"] = universe_name
        return result[config.BACKTEST_UNIVERSE_COLUMNS].sort_values(["date", "symbol"]).reset_index(drop=True)

    delistings = selected_delisting_events[["symbol", "event_date"]].copy()
    delistings["event_date"] = pd.to_datetime(delistings["event_date"], errors="coerce").dt.normalize()
    merged = membership.merge(delistings, on="symbol", how="left")
    kept = merged[(merged["event_date"].isna()) | (merged["date"] <= merged["event_date"])].copy()
    has_event = kept["event_date"].notna()
    kept.loc[has_event, "reason"] = kept.loc[has_event, "reason"].astype(str) + "; lifecycle<=delisting_event"
    kept["universe_name"] = universe_name
    result = kept[config.BACKTEST_UNIVERSE_COLUMNS]
    return result.sort_values(["date", "symbol"]).reset_index(drop=True)


def build_backtest_universe(
    symbol_master_path: Path = config.SYMBOL_MASTER_PATH,
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    universe_membership_path: Path = config.UNIVERSE_MEMBERSHIP_PATH,
    fmp_delisted_metadata_path: Path = config.FMP_DELISTED_METADATA_PATH,
    sec_delisted_candidates_path: Path = config.SEC_DELISTED_CANDIDATES_PATH,
    security_events_path: Path = config.SECURITY_EVENTS_PATH,
    terminal_events_path: Path = config.TERMINAL_EVENTS_PATH,
    backtest_universe_path: Path = config.BACKTEST_UNIVERSE_MEMBERSHIP_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    symbol_master = read_parquet_if_exists(symbol_master_path, config.SYMBOL_MASTER_COLUMNS)
    daily_prices = read_parquet_if_exists(daily_prices_path, config.CANONICAL_PRICE_COLUMNS)
    universe_membership = read_parquet_if_exists(universe_membership_path, config.UNIVERSE_COLUMNS)
    fmp_delisted = read_parquet_if_exists(
        fmp_delisted_metadata_path,
        ["symbol", "companyName", "exchange", "ipoDate", "delistedDate", "source"],
    )
    sec_candidates = read_parquet_if_exists(
        sec_delisted_candidates_path,
        ["cik", "company_name", "form_type", "date_filed", "candidate_symbol"],
    )

    security_events = build_security_events_df(symbol_master, fmp_delisted, sec_candidates)
    selected_delistings = select_delisting_events(security_events)
    terminal_events = build_terminal_events_df(daily_prices, selected_delistings)
    backtest_universe = build_backtest_universe_df(universe_membership, selected_delistings)

    write_parquet(security_events, security_events_path)
    write_parquet(terminal_events, terminal_events_path)
    write_parquet(backtest_universe, backtest_universe_path)

    print(f"[backtest_universe] Wrote {len(security_events):,} security events to {security_events_path}")
    print(f"[backtest_universe] Wrote {len(terminal_events):,} terminal events to {terminal_events_path}")
    print(f"[backtest_universe] Wrote {len(backtest_universe):,} memberships to {backtest_universe_path}")
    return security_events, terminal_events, backtest_universe


if __name__ == "__main__":
    config.ensure_directories()
    build_backtest_universe()

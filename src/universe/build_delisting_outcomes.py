from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd

from src import config
from src.collectors.sec_delisting_collector import (
    SEC_ARCHIVES_ROOT,
    SEC_HEADERS,
    extract_delisting_doc_fields,
)
from src.utils import empty_frame, normalize_symbol, read_parquet_if_exists, write_parquet


OUTCOME_POLICY = "last_close_on_or_before_effective_or_event_date_no_zero_fill_v1"
CASH_PRICE_RATIO_MIN = 0.2
CASH_PRICE_RATIO_MAX = 5.0

OUTCOME_PATTERNS: list[tuple[str, str, str]] = [
    (
        "bankruptcy_or_liquidation",
        "high",
        r"\b(chapter\s+(?:7|11)|bankrupt|liquidat|receivership|winding\s+up)\b",
    ),
    (
        "merger_or_acquisition",
        "medium",
        r"\b(merger|merged|acquired\s+by|tender\s+offer|wholly\s+owned\s+subsidiary|merger\s+agreement)\b",
    ),
    (
        "fund_liquidation_or_termination",
        "medium",
        r"\b(etf|fund|trust)\b.{0,120}\b(liquidat|terminat|dissolut)\b",
    ),
    (
        "listing_standards_failure",
        "medium",
        r"\b(non[-\s]?compliance|deficien|listing\s+standard|staff\s+determination|minimum\s+bid|suspended)\b",
    ),
    (
        "exchange_transfer_or_market_change",
        "low",
        r"\b(otc|pink|transfer|another\s+national\s+securities\s+exchange|nasdaq\s+capital\s+market|nyse\s+american)\b",
    ),
    (
        "voluntary_withdrawal",
        "low",
        r"\b(issuer\s+request(?:ed|s)|company\s+request(?:ed|s)|at\s+the\s+request\s+of)\b.{0,100}\b(withdraw|delist|remove)\b",
    ),
]

CASH_CONSIDERATION_PATTERNS = [
    r"\$\s*(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)\s+in\s+cash(?:,?[^.;]{0,140})?\s+per\s+share",
    r"\$\s*(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)\s+per\s+share\s+in\s+cash",
    r"per\s+share(?:[^$.;]{0,140})\$\s*(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)\s+in\s+cash",
    r"(?:converted|exchanged)\s+for\s+\$\s*(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)(?:\s+per\s+share|\s+in\s+cash)",
    r"right\s+to\s+receive\s+\$\s*(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)(?:\s+per\s+share|\s+in\s+cash)",
]


def _compact_symbol(value: object) -> str | None:
    symbol = normalize_symbol(value)
    if symbol is None:
        return None
    compact = "".join(ch for ch in symbol.upper() if ch.isalnum())
    return compact or None


def _clean_text(text: object) -> str:
    if text is None or pd.isna(text):
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _document_body(text: str) -> str:
    text_blocks = re.findall(r"<TEXT>(.*?)</TEXT>", text, flags=re.I | re.S)
    body = " ".join(text_blocks) if text_blocks else text
    body = re.sub(r"<[^>]+>", " ", body)
    body = body.replace("&nbsp;", " ")
    body = body.replace("&#160;", " ")
    return _clean_text(body)


def _safe_text_snippet(text: str, start: int, end: int, width: int = 80) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    snippet = text[left:right]
    return _clean_text(snippet)[:260]


def _coerce_bool(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def classify_delisting_text(text: str, security_description: object = None) -> dict[str, object]:
    searchable = _clean_text(" ".join([_clean_text(security_description), _document_body(text)]))
    if not searchable:
        return {
            "outcome_type": "unknown",
            "outcome_confidence": "missing_text",
            "outcome_source": "",
            "evidence": "",
        }

    for outcome_type, confidence, pattern in OUTCOME_PATTERNS:
        match = re.search(pattern, searchable, flags=re.I)
        if match:
            return {
                "outcome_type": outcome_type,
                "outcome_confidence": confidence,
                "outcome_source": "sec_form25_text",
                "evidence": _safe_text_snippet(searchable, match.start(), match.end()),
            }

    return {
        "outcome_type": "unknown",
        "outcome_confidence": "low",
        "outcome_source": "sec_form25_text",
        "evidence": "",
    }


def extract_cash_consideration_per_share(text: str) -> dict[str, object]:
    body = _document_body(text)
    for pattern in CASH_CONSIDERATION_PATTERNS:
        match = re.search(pattern, body, flags=re.I)
        if not match:
            continue
        amount_text = match.group("amount").replace(",", "")
        amount = pd.to_numeric(amount_text, errors="coerce")
        if pd.notna(amount) and amount > 0:
            right_context = body[match.end() : match.end() + 180]
            is_partial = bool(
                re.search(
                    r"\band\s+\d+(?:\.\d+)?\s+(?:of\s+a\s+)?shares?\b|\band\s+\d+(?:\.\d+)?\s+of\s+a\s+share\b",
                    right_context,
                    flags=re.I,
                )
            )
            return {
                "cash_consideration_per_share": float(amount),
                "cash_consideration_source": "sec_form25_text",
                "cash_consideration_is_partial": is_partial,
            }

    return {
        "cash_consideration_per_share": pd.NA,
        "cash_consideration_source": "",
        "cash_consideration_is_partial": pd.NA,
    }


def _local_sec_doc_path(raw_dir: Path, filename: object) -> Path:
    safe_name = str(filename).replace("/", "_").replace("\\", "_")
    return raw_dir / "outcome-filings" / safe_name


def _request_sec_text(url: str, sleep_seconds: float = 0.12) -> str:
    import requests

    response = requests.get(url, headers=SEC_HEADERS, timeout=(5, 60))
    response.raise_for_status()
    time.sleep(sleep_seconds)
    return response.text


def _prepare_sec_candidates(sec_delisted_candidates: pd.DataFrame) -> pd.DataFrame:
    if sec_delisted_candidates.empty:
        return pd.DataFrame(columns=config.SEC_DELISTING_OUTCOME_DOC_COLUMNS)

    sec = sec_delisted_candidates.copy()
    sec["candidate_symbol"] = sec.get("candidate_symbol", pd.Series(dtype="object")).map(normalize_symbol)
    sec["compact_symbol"] = sec["candidate_symbol"].map(_compact_symbol)
    sec["date_filed"] = pd.to_datetime(
        sec.get("date_filed", pd.Series(dtype="object")),
        errors="coerce",
    ).dt.normalize()
    sec = sec.dropna(subset=["compact_symbol", "date_filed", "filename"])

    ticker_priority = {
        "sec_form25_text": 1,
        "sec_form345": 2,
        "sec_company_tickers_exchange": 3,
    }
    sec["ticker_priority"] = sec.get("ticker_source", pd.Series(dtype="object")).map(ticker_priority).fillna(99)
    sec["candidate_symbol_count_for_filing"] = pd.to_numeric(
        sec.get("candidate_symbol_count_for_filing", pd.Series(dtype="object")),
        errors="coerce",
    )
    sec["candidate_count_sort"] = sec["candidate_symbol_count_for_filing"].fillna(9999)
    sort_columns = ["compact_symbol", "date_filed", "candidate_count_sort", "ticker_priority", "filename"]
    return sec.sort_values(sort_columns).reset_index(drop=True)


def _match_selected_sec_filings(
    terminal_events: pd.DataFrame,
    sec_delisted_candidates: pd.DataFrame,
) -> pd.DataFrame:
    if terminal_events.empty or sec_delisted_candidates.empty:
        return empty_frame(config.SEC_DELISTING_OUTCOME_DOC_COLUMNS)

    events = terminal_events.copy()
    events = events[events.get("event_source") == "sec_form25_date_filed"].copy()
    if events.empty:
        return empty_frame(config.SEC_DELISTING_OUTCOME_DOC_COLUMNS)

    events["symbol"] = events["symbol"].map(normalize_symbol)
    events["compact_symbol"] = events["symbol"].map(_compact_symbol)
    events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce").dt.normalize()
    events = events.dropna(subset=["symbol", "compact_symbol", "event_date"])

    sec = _prepare_sec_candidates(sec_delisted_candidates)
    if sec.empty:
        return empty_frame(config.SEC_DELISTING_OUTCOME_DOC_COLUMNS)

    merged = events[["symbol", "event_date", "compact_symbol"]].merge(
        sec,
        left_on=["compact_symbol", "event_date"],
        right_on=["compact_symbol", "date_filed"],
        how="inner",
    )
    if merged.empty:
        return empty_frame(config.SEC_DELISTING_OUTCOME_DOC_COLUMNS)

    merged = merged.sort_values(
        ["symbol", "event_date", "candidate_count_sort", "ticker_priority", "filename"]
    ).drop_duplicates(["symbol", "event_date"], keep="first")

    for column in config.SEC_DELISTING_OUTCOME_DOC_COLUMNS:
        if column not in merged.columns:
            merged[column] = pd.NA

    return merged[config.SEC_DELISTING_OUTCOME_DOC_COLUMNS].reset_index(drop=True)


def build_sec_delisting_outcome_documents_df(
    terminal_events: pd.DataFrame,
    sec_delisted_candidates: pd.DataFrame,
    raw_dir: Path = config.RAW_SEC_DIR,
    fetch_missing: bool = True,
    limit: int | None = None,
) -> pd.DataFrame:
    matched = _match_selected_sec_filings(terminal_events, sec_delisted_candidates)
    if matched.empty:
        return empty_frame(config.SEC_DELISTING_OUTCOME_DOC_COLUMNS)

    docs_dir = raw_dir / "outcome-filings"
    docs_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    work = matched.head(limit) if limit else matched

    for idx, record in enumerate(work.itertuples(index=False), start=1):
        filename = record.filename
        local_path = _local_sec_doc_path(raw_dir, filename)
        text = ""
        if local_path.exists():
            text = local_path.read_text(encoding="utf-8", errors="ignore")
        elif fetch_missing:
            try:
                text = _request_sec_text(SEC_ARCHIVES_ROOT + str(filename))
            except Exception as exc:
                print(f"[delisting_outcomes] SEC filing fetch failed {filename}: {exc}")
                text = ""
            local_path.write_text(text, encoding="utf-8", errors="ignore")

        fields = extract_delisting_doc_fields(text) if text else {}
        security_description = fields.get("security_description", pd.NA)
        classification = classify_delisting_text(text, security_description)
        cash_consideration = extract_cash_consideration_per_share(text) if text else {
            "cash_consideration_per_share": pd.NA,
            "cash_consideration_source": "",
        }

        row = {column: getattr(record, column, pd.NA) for column in config.SEC_DELISTING_OUTCOME_DOC_COLUMNS}
        row.update(fields)
        row.update(classification)
        row.update(cash_consideration)
        row["text_available"] = bool(text)
        rows.append(row)

        if idx % 250 == 0 or idx == len(work):
            print(f"[delisting_outcomes] Enriched {idx:,}/{len(work):,} selected SEC filings")

    result = pd.DataFrame(rows, columns=config.SEC_DELISTING_OUTCOME_DOC_COLUMNS)
    for column in ["event_date", "date_filed", "signature_date", "effective_date"]:
        result[column] = pd.to_datetime(result[column], errors="coerce").dt.normalize()
    return result.sort_values(["event_date", "symbol"]).reset_index(drop=True)


def _prepare_outcome_docs(sec_outcome_documents: pd.DataFrame) -> pd.DataFrame:
    if sec_outcome_documents.empty:
        return empty_frame(config.SEC_DELISTING_OUTCOME_DOC_COLUMNS)

    docs = sec_outcome_documents.copy()
    docs["symbol"] = docs["symbol"].map(normalize_symbol)
    docs["event_date"] = pd.to_datetime(docs["event_date"], errors="coerce").dt.normalize()
    docs["effective_date"] = pd.to_datetime(docs.get("effective_date"), errors="coerce").dt.normalize()
    docs = docs.dropna(subset=["symbol", "event_date"])
    return docs.sort_values(["symbol", "event_date"]).drop_duplicates(["symbol", "event_date"], keep="first")


def _prepare_terminal_events(terminal_events: pd.DataFrame) -> pd.DataFrame:
    if terminal_events.empty:
        return empty_frame(config.TERMINAL_EVENTS_COLUMNS)
    result = terminal_events.copy()
    result["symbol"] = result["symbol"].map(normalize_symbol)
    result["event_date"] = pd.to_datetime(result["event_date"], errors="coerce").dt.normalize()
    return result.dropna(subset=["symbol", "event_date"])


def _prepare_prices(daily_prices: pd.DataFrame) -> pd.DataFrame:
    if daily_prices.empty:
        return pd.DataFrame(columns=["symbol", "date", "close", "previous_close", "source"])

    prices = daily_prices[["symbol", "date", "close", "source"]].copy()
    prices["symbol"] = prices["symbol"].map(normalize_symbol)
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.dropna(subset=["symbol", "date"]).sort_values(["symbol", "date"])
    prices["previous_close"] = prices.groupby("symbol")["close"].shift(1)
    return prices


def _exit_price_rows(prices: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    if prices.empty or outcomes.empty:
        return pd.DataFrame()

    candidates = outcomes[["symbol", "event_date", "exit_date"]].merge(
        prices,
        on="symbol",
        how="left",
    )
    candidates = candidates[candidates["date"] <= candidates["exit_date"]]
    candidates = candidates.sort_values(["symbol", "event_date", "date"])
    return candidates.groupby(["symbol", "event_date"], as_index=False).tail(1)


def build_delisting_outcomes_df(
    terminal_events: pd.DataFrame,
    daily_prices: pd.DataFrame,
    sec_outcome_documents: pd.DataFrame,
) -> pd.DataFrame:
    events = _prepare_terminal_events(terminal_events)
    if events.empty:
        return empty_frame(config.DELISTING_OUTCOMES_COLUMNS)

    docs = _prepare_outcome_docs(sec_outcome_documents)
    outcomes = events.merge(
        docs,
        on=["symbol", "event_date"],
        how="left",
        suffixes=("", "_doc"),
    )

    outcomes["effective_date"] = pd.to_datetime(
        outcomes.get("effective_date", pd.Series(dtype="object")),
        errors="coerce",
    ).dt.normalize()
    outcomes["exit_date"] = outcomes["effective_date"].where(outcomes["effective_date"].notna(), outcomes["event_date"])
    outcomes["exit_date_source"] = "sec_form25_effective_date"
    outcomes.loc[outcomes["effective_date"].isna(), "exit_date_source"] = "selected_delisting_event_date"

    prices = _prepare_prices(daily_prices)
    exit_prices = _exit_price_rows(prices, outcomes)

    rows: list[dict[str, object]] = []
    for record in outcomes.itertuples(index=False):
        match = exit_prices[
            (exit_prices["symbol"] == record.symbol)
            & (exit_prices["event_date"] == record.event_date)
        ]

        exit_price_date = pd.NaT
        exit_price = pd.NA
        previous_close = pd.NA
        exit_return = pd.NA
        price_source = ""
        if not match.empty:
            price_row = match.iloc[0]
            exit_price_date = price_row["date"]
            exit_price = price_row["close"]
            previous_close = price_row["previous_close"]
            price_source = price_row["source"]
            if pd.notna(previous_close) and previous_close > 0 and pd.notna(exit_price):
                exit_return = (exit_price / previous_close) - 1.0

        cash_consideration = getattr(record, "cash_consideration_per_share", pd.NA)
        cash_consideration_is_partial = getattr(record, "cash_consideration_is_partial", pd.NA)
        cash_consideration = pd.to_numeric(cash_consideration, errors="coerce")
        cash_consideration_is_partial_bool = _coerce_bool(cash_consideration_is_partial)
        comparison_price = previous_close if pd.notna(previous_close) and previous_close > 0 else exit_price
        cash_consideration_price_ratio = pd.NA
        cash_is_price_plausible = True
        if pd.notna(cash_consideration) and cash_consideration > 0 and pd.notna(comparison_price) and comparison_price > 0:
            cash_consideration_price_ratio = float(cash_consideration) / float(comparison_price)
            cash_is_price_plausible = (
                CASH_PRICE_RATIO_MIN <= cash_consideration_price_ratio <= CASH_PRICE_RATIO_MAX
            )
        exit_value = exit_price
        exit_value_source = "observed_exit_price" if pd.notna(exit_price) else ""
        if (
            pd.notna(cash_consideration)
            and cash_consideration > 0
            and not cash_consideration_is_partial_bool
            and cash_is_price_plausible
        ):
            exit_value = float(cash_consideration)
            exit_value_source = "sec_cash_consideration"

        exit_value_return = pd.NA
        if pd.notna(previous_close) and previous_close > 0 and pd.notna(exit_value):
            exit_value_return = (exit_value / previous_close) - 1.0

        outcome_type = getattr(record, "outcome_type", pd.NA)
        outcome_confidence = getattr(record, "outcome_confidence", pd.NA)
        outcome_source = getattr(record, "outcome_source", pd.NA)
        evidence = getattr(record, "evidence", pd.NA)

        if pd.isna(outcome_type) or not str(outcome_type).strip():
            outcome_type = "unknown"
            outcome_confidence = "not_enriched"
            outcome_source = ""
            evidence = ""

        notes = "Exit price is last available close on or before exit_date; no zero fill or CRSP-style delisting return."
        if pd.isna(exit_price):
            notes = "No exit price found on or before exit_date; no zero fill applied."
        elif pd.notna(cash_consideration) and not cash_is_price_plausible:
            notes = (
                "SEC cash consideration was not used as exit_value because it is not on a comparable "
                "scale with observed prices."
            )
        if exit_value_source == "sec_cash_consideration":
            notes = "Exit_value uses SEC cash consideration per share; no artificial zero fill applied."

        rows.append(
            {
                "symbol": record.symbol,
                "event_date": record.event_date,
                "effective_date": getattr(record, "effective_date", pd.NaT),
                "exit_date": record.exit_date,
                "exit_date_source": record.exit_date_source,
                "exit_price_date": exit_price_date,
                "exit_price": exit_price,
                "previous_close": previous_close,
                "exit_return": exit_return,
                "has_exit_price": pd.notna(exit_price),
                "cash_consideration_per_share": cash_consideration,
                "cash_consideration_is_partial": cash_consideration_is_partial,
                "cash_consideration_price_ratio": cash_consideration_price_ratio,
                "exit_value": exit_value,
                "exit_value_return": exit_value_return,
                "exit_value_source": exit_value_source,
                "has_exit_value": pd.notna(exit_value),
                "price_source": price_source,
                "event_source": record.event_source,
                "event_confidence": record.event_confidence,
                "outcome_type": outcome_type,
                "outcome_confidence": outcome_confidence,
                "outcome_source": outcome_source,
                "sec_filename": getattr(record, "filename", pd.NA),
                "sec_form_type": getattr(record, "form_type", pd.NA),
                "sec_company_name": getattr(record, "company_name", pd.NA),
                "sec_ticker_source": getattr(record, "ticker_source", pd.NA),
                "candidate_symbol_count": getattr(record, "candidate_symbol_count_for_filing", pd.NA),
                "policy": OUTCOME_POLICY,
                "evidence": evidence,
                "notes": notes,
            }
        )

    result = pd.DataFrame(rows, columns=config.DELISTING_OUTCOMES_COLUMNS)
    for column in ["event_date", "effective_date", "exit_date", "exit_price_date"]:
        result[column] = pd.to_datetime(result[column], errors="coerce").dt.normalize()
    return result.sort_values(["event_date", "symbol"]).reset_index(drop=True)


def build_delisting_outcomes(
    terminal_events_path: Path = config.TERMINAL_EVENTS_PATH,
    daily_prices_path: Path = config.DAILY_PRICES_PATH,
    sec_delisted_candidates_path: Path = config.SEC_DELISTED_CANDIDATES_PATH,
    sec_outcome_documents_path: Path = config.SEC_DELISTING_OUTCOME_DOCS_PATH,
    delisting_outcomes_path: Path = config.DELISTING_OUTCOMES_PATH,
    fetch_sec_docs: bool = True,
    sec_doc_limit: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    terminal_events = read_parquet_if_exists(terminal_events_path, config.TERMINAL_EVENTS_COLUMNS)
    daily_prices = read_parquet_if_exists(daily_prices_path, config.CANONICAL_PRICE_COLUMNS)
    sec_candidates = read_parquet_if_exists(
        sec_delisted_candidates_path,
        ["cik", "company_name", "form_type", "date_filed", "filename", "candidate_symbol"],
    )

    sec_docs = build_sec_delisting_outcome_documents_df(
        terminal_events=terminal_events,
        sec_delisted_candidates=sec_candidates,
        fetch_missing=fetch_sec_docs,
        limit=sec_doc_limit,
    )
    if sec_doc_limit is None:
        write_parquet(sec_docs, sec_outcome_documents_path)
    elif sec_outcome_documents_path.exists():
        existing_docs = read_parquet_if_exists(sec_outcome_documents_path, config.SEC_DELISTING_OUTCOME_DOC_COLUMNS)
        combined = pd.concat([existing_docs, sec_docs], ignore_index=True, sort=False)
        combined = combined.sort_values(["symbol", "event_date"]).drop_duplicates(
            ["symbol", "event_date"],
            keep="last",
        )
        sec_docs = combined[config.SEC_DELISTING_OUTCOME_DOC_COLUMNS]
        write_parquet(sec_docs, sec_outcome_documents_path)
    else:
        write_parquet(sec_docs, sec_outcome_documents_path)

    outcomes = build_delisting_outcomes_df(terminal_events, daily_prices, sec_docs)
    write_parquet(outcomes, delisting_outcomes_path)

    enriched_docs = int(sec_docs["text_available"].fillna(False).sum()) if "text_available" in sec_docs else 0
    priced = int(outcomes["has_exit_price"].fillna(False).sum()) if not outcomes.empty else 0
    print(f"[delisting_outcomes] Wrote {len(sec_docs):,} SEC outcome document rows to {sec_outcome_documents_path}")
    print(f"[delisting_outcomes] SEC text available for {enriched_docs:,} selected events")
    print(f"[delisting_outcomes] Wrote {len(outcomes):,} delisting outcomes to {delisting_outcomes_path}")
    print(f"[delisting_outcomes] Exit price available for {priced:,}/{len(outcomes):,} outcomes")
    return sec_docs, outcomes


if __name__ == "__main__":
    config.ensure_directories()
    build_delisting_outcomes()

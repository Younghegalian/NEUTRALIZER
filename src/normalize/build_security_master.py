from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src import config
from src.collectors.active_symbols import fetch_active_us_symbols
from src.utils import empty_frame, normalize_symbol, read_parquet_if_exists, write_parquet


def _clean_text(value: object) -> object:
    if value is None or pd.isna(value):
        return pd.NA
    text = str(value).strip()
    return text if text else pd.NA


def _upper_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper()


def _infer_asset_type(
    instrument_type: object,
    is_etf: object,
    is_fund: object,
    security_name: object,
) -> str:
    instrument = _upper_text(instrument_type)
    name = "" if security_name is None or pd.isna(security_name) else str(security_name).lower()

    if _truthy(is_etf) or instrument == "ETF" or " exchange traded fund" in name or name.endswith(" etf") or " etf " in name:
        return "etf"
    if _truthy(is_fund) or instrument == "MUTUALFUND":
        return "fund"
    if instrument == "EQUITY":
        return "stock"
    if "common stock" in name or "ordinary share" in name or "depositary" in name or " adr" in name:
        return "stock"
    return "unknown"


def _truthy(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "y", "yes"}
    return bool(value)


def _read_active_listing_metadata() -> pd.DataFrame:
    try:
        active = fetch_active_us_symbols(include_etfs=True, liquid_equity_like=False)
    except Exception as exc:
        print(f"[security_master] Active listing metadata unavailable: {exc}")
        return pd.DataFrame(columns=["symbol", "active_security_name", "active_exchange", "active_is_etf"])

    active = active.rename(
        columns={
            "Security Name": "active_security_name",
            "exchange": "active_exchange",
            "ETF": "active_is_etf",
        }
    )
    active["symbol"] = active["symbol"].map(normalize_symbol)
    active["active_is_etf"] = active["active_is_etf"].astype(str).str.upper().eq("Y")
    return active[["symbol", "active_security_name", "active_exchange", "active_is_etf"]].drop_duplicates("symbol")


def _read_yahoo_metadata() -> pd.DataFrame:
    rows: list[dict] = []
    paths: list[tuple[int, Path]] = []
    paths.extend((1, path) for path in config.RAW_YAHOO_DIR.glob("*.json"))
    delisted_dir = config.RAW_YAHOO_DIR / "delisted_probe"
    if delisted_dir.exists():
        paths.extend((2, path) for path in delisted_dir.glob("*.json"))

    for priority, path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            result = (payload.get("chart", {}).get("result") or [None])[0]
            if not result:
                continue
            meta = result.get("meta", {})
            rows.append(
                {
                    "symbol": normalize_symbol(meta.get("symbol") or path.stem),
                    "yahoo_instrument_type": _clean_text(meta.get("instrumentType")),
                    "yahoo_security_name": _clean_text(meta.get("longName") or meta.get("shortName")),
                    "yahoo_exchange": _clean_text(meta.get("fullExchangeName") or meta.get("exchangeName")),
                    "yahoo_currency": _clean_text(meta.get("currency")),
                    "yahoo_priority": priority,
                }
            )
        except Exception:
            continue

    if not rows:
        return pd.DataFrame(
            columns=[
                "symbol",
                "yahoo_instrument_type",
                "yahoo_security_name",
                "yahoo_exchange",
                "yahoo_currency",
            ]
        )

    df = pd.DataFrame(rows)
    df = df[df["symbol"].notna()].copy()
    valid = df["yahoo_instrument_type"].astype(str).str.upper().isin(["EQUITY", "ETF"]) & df[
        "yahoo_currency"
    ].astype(str).str.upper().eq("USD")
    df = df[valid].sort_values(["symbol", "yahoo_priority"]).drop_duplicates("symbol")
    return df.drop(columns=["yahoo_priority"])


def _read_fmp_delisted_metadata() -> pd.DataFrame:
    fmp = read_parquet_if_exists(config.FMP_DELISTED_METADATA_PATH, ["symbol", "companyName", "exchange"])
    if fmp.empty:
        return pd.DataFrame(columns=["symbol", "fmp_delisted_name", "fmp_delisted_exchange"])
    fmp["symbol"] = fmp["symbol"].map(normalize_symbol)
    fmp = fmp.rename(columns={"companyName": "fmp_delisted_name", "exchange": "fmp_delisted_exchange"})
    return fmp[["symbol", "fmp_delisted_name", "fmp_delisted_exchange"]].drop_duplicates("symbol")


def _read_fmp_profile_metadata() -> pd.DataFrame:
    fmp = read_parquet_if_exists(config.FMP_PROFILE_METADATA_PATH, ["symbol"])
    if fmp.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "fmp_profile_name",
                "fmp_profile_exchange",
                "fmp_profile_currency",
                "sector",
                "industry",
                "fmp_is_etf",
                "fmp_is_fund",
            ]
        )
    fmp["symbol"] = fmp["symbol"].map(normalize_symbol)
    fmp = fmp.rename(
        columns={
            "companyName": "fmp_profile_name",
            "exchange": "fmp_profile_exchange",
            "currency": "fmp_profile_currency",
            "isEtf": "fmp_is_etf",
            "isFund": "fmp_is_fund",
        }
    )
    columns = [
        "symbol",
        "fmp_profile_name",
        "fmp_profile_exchange",
        "fmp_profile_currency",
        "sector",
        "industry",
        "fmp_is_etf",
        "fmp_is_fund",
    ]
    for column in columns:
        if column not in fmp.columns:
            fmp[column] = pd.NA
    return fmp[columns].drop_duplicates("symbol")


def _read_sec_company_metadata() -> pd.DataFrame:
    sec = read_parquet_if_exists(config.SEC_COMPANY_METADATA_PATH, ["symbol"])
    if sec.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "sec_cik",
                "sec_company_name",
                "sec_exchange",
                "sic",
                "sic_description",
                "sic_sector",
            ]
        )
    sec["symbol"] = sec["symbol"].map(normalize_symbol)
    sec = sec.rename(columns={"cik": "sec_cik"})
    columns = [
        "symbol",
        "sec_cik",
        "sec_company_name",
        "sec_exchange",
        "sic",
        "sic_description",
        "sic_sector",
    ]
    for column in columns:
        if column not in sec.columns:
            sec[column] = pd.NA
    return sec[columns].drop_duplicates("symbol")


def _first_notna(*values: object) -> object:
    for value in values:
        if value is not None and not pd.isna(value):
            text = str(value).strip()
            if text:
                return value
    return pd.NA


def build_security_master_df(symbol_master: pd.DataFrame) -> pd.DataFrame:
    if symbol_master.empty:
        return empty_frame(config.SECURITY_MASTER_COLUMNS)

    result = symbol_master[["symbol"]].drop_duplicates().copy()
    result["symbol"] = result["symbol"].map(normalize_symbol)
    result = result[result["symbol"].notna()]

    for frame in [
        _read_active_listing_metadata(),
        _read_yahoo_metadata(),
        _read_fmp_delisted_metadata(),
        _read_fmp_profile_metadata(),
        _read_sec_company_metadata(),
    ]:
        if not frame.empty:
            result = result.merge(frame, on="symbol", how="left")

    optional_columns = [
        "active_security_name",
        "active_exchange",
        "active_is_etf",
        "yahoo_instrument_type",
        "yahoo_security_name",
        "yahoo_exchange",
        "yahoo_currency",
        "fmp_delisted_name",
        "fmp_delisted_exchange",
        "fmp_profile_name",
        "fmp_profile_exchange",
        "fmp_profile_currency",
        "fmp_is_etf",
        "fmp_is_fund",
        "sec_company_name",
        "sec_exchange",
        "sec_cik",
        "sic",
        "sic_description",
        "sic_sector",
        "sector",
        "industry",
    ]
    for column in optional_columns:
        if column not in result.columns:
            result[column] = pd.NA

    result["fmp_sector"] = result["sector"] if "sector" in result.columns else pd.NA
    result["fmp_industry"] = result["industry"] if "industry" in result.columns else pd.NA
    result["sector"] = result.apply(
        lambda row: _first_notna(row.get("sic_sector"), row.get("fmp_sector")),
        axis=1,
    )
    result["industry"] = result.apply(
        lambda row: _first_notna(row.get("sic_description"), row.get("fmp_industry")),
        axis=1,
    )
    result["security_name"] = result.apply(
        lambda row: _first_notna(
            row.get("fmp_profile_name"),
            row.get("yahoo_security_name"),
            row.get("active_security_name"),
            row.get("fmp_delisted_name"),
            row.get("sec_company_name"),
        ),
        axis=1,
    )
    result["exchange"] = result.apply(
        lambda row: _first_notna(
            row.get("fmp_profile_exchange"),
            row.get("yahoo_exchange"),
            row.get("active_exchange"),
            row.get("fmp_delisted_exchange"),
            row.get("sec_exchange"),
        ),
        axis=1,
    )
    result["cik"] = result.get("sec_cik")
    result["currency"] = result.apply(
        lambda row: _first_notna(row.get("fmp_profile_currency"), row.get("yahoo_currency")),
        axis=1,
    )
    result["instrument_type"] = result["yahoo_instrument_type"]
    result["is_etf"] = result.apply(
        lambda row: _truthy(row.get("fmp_is_etf"))
        or _truthy(row.get("active_is_etf"))
        or _upper_text(row.get("yahoo_instrument_type")) == "ETF",
        axis=1,
    )
    result["asset_type"] = result.apply(
        lambda row: _infer_asset_type(
            row.get("instrument_type"),
            row.get("is_etf"),
            row.get("fmp_is_fund"),
            row.get("security_name"),
        ),
        axis=1,
    )
    result["classification_source"] = result.apply(
        lambda row: "fmp_profile"
        if not pd.isna(row.get("fmp_profile_name"))
        else "yahoo_meta"
        if not pd.isna(row.get("yahoo_instrument_type"))
        else "nasdaq_trader"
        if not pd.isna(row.get("active_security_name"))
        else "fmp_delisted"
        if not pd.isna(row.get("fmp_delisted_name"))
        else "unknown",
        axis=1,
    )
    result["sector_source"] = result.apply(
        lambda row: "sec_sic"
        if not pd.isna(row.get("sic_sector")) or not pd.isna(row.get("sic_description"))
        else "fmp_profile"
        if not pd.isna(row.get("fmp_sector")) or not pd.isna(row.get("fmp_industry"))
        else pd.NA,
        axis=1,
    )

    return result[config.SECURITY_MASTER_COLUMNS].sort_values("symbol").reset_index(drop=True)


def build_security_master(
    symbol_master_path: Path = config.SYMBOL_MASTER_PATH,
    output_path: Path = config.SECURITY_MASTER_PATH,
) -> pd.DataFrame:
    symbol_master = read_parquet_if_exists(symbol_master_path, config.SYMBOL_MASTER_COLUMNS)
    result = build_security_master_df(symbol_master)
    write_parquet(result, output_path)
    print(f"[security_master] Wrote {len(result):,} rows to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    build_security_master()

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, read_parquet_if_exists, write_parquet


POLICY_VERSION = "fona_non_sic_classification_catalog_v1"
MIN_ETF_QUALITY_ADV20 = 25_000_000
MIN_ETF_AGE_YEARS = 5.0
MIN_ETF_TRADED_DAYS_20 = 15
MAX_ETF_STALE_DAYS = 10


SECTOR_SYMBOLS = {
    "XLB": ("Basic Materials", "Materials Select Sector ETF"),
    "XLC": ("Communication Services", "Communication Services Select Sector ETF"),
    "XLE": ("Energy", "Energy Select Sector ETF"),
    "XLF": ("Financial Services", "Financial Select Sector ETF"),
    "XLI": ("Industrials", "Industrial Select Sector ETF"),
    "XLK": ("Technology", "Technology Select Sector ETF"),
    "XLP": ("Consumer Defensive", "Consumer Staples Select Sector ETF"),
    "XLRE": ("Real Estate", "Real Estate Select Sector ETF"),
    "XLU": ("Utilities", "Utilities Select Sector ETF"),
    "XLV": ("Healthcare", "Health Care Select Sector ETF"),
    "XLY": ("Consumer Cyclical", "Consumer Discretionary Select Sector ETF"),
    "FTEC": ("Technology", "Technology ETF"),
    "IYW": ("Technology", "Technology ETF"),
    "VGT": ("Technology", "Technology ETF"),
    "SMH": ("Technology", "Semiconductor ETF"),
    "SOXX": ("Technology", "Semiconductor ETF"),
    "IGV": ("Technology", "Software ETF"),
    "FENY": ("Energy", "Energy ETF"),
    "IYE": ("Energy", "Energy ETF"),
    "VDE": ("Energy", "Energy ETF"),
    "FHLC": ("Healthcare", "Health Care ETF"),
    "IYH": ("Healthcare", "Health Care ETF"),
    "VHT": ("Healthcare", "Health Care ETF"),
    "XBI": ("Healthcare", "Biotech ETF"),
    "KRE": ("Financial Services", "Regional Banking ETF"),
    "KBE": ("Financial Services", "Bank ETF"),
    "FNCL": ("Financial Services", "Financials ETF"),
    "IYF": ("Financial Services", "Financials ETF"),
    "VFH": ("Financial Services", "Financials ETF"),
    "FIDU": ("Industrials", "Industrials ETF"),
    "IYJ": ("Industrials", "Industrials ETF"),
    "VIS": ("Industrials", "Industrials ETF"),
    "FDIS": ("Consumer Cyclical", "Consumer Discretionary ETF"),
    "IYC": ("Consumer Cyclical", "Consumer Discretionary ETF"),
    "VCR": ("Consumer Cyclical", "Consumer Discretionary ETF"),
    "FSTA": ("Consumer Defensive", "Consumer Staples ETF"),
    "IYK": ("Consumer Defensive", "Consumer Staples ETF"),
    "VDC": ("Consumer Defensive", "Consumer Staples ETF"),
    "FMAT": ("Basic Materials", "Materials ETF"),
    "IYM": ("Basic Materials", "Materials ETF"),
    "VAW": ("Basic Materials", "Materials ETF"),
    "FUTY": ("Utilities", "Utilities ETF"),
    "IDU": ("Utilities", "Utilities ETF"),
    "VPU": ("Utilities", "Utilities ETF"),
    "FCOM": ("Communication Services", "Communication Services ETF"),
    "IYZ": ("Communication Services", "Telecom ETF"),
    "VOX": ("Communication Services", "Communication Services ETF"),
    "IYR": ("Real Estate", "Real Estate ETF"),
    "SCHH": ("Real Estate", "Real Estate ETF"),
    "VNQ": ("Real Estate", "Real Estate ETF"),
    "GDX": ("Basic Materials", "Gold Miners ETF"),
    "GDXJ": ("Basic Materials", "Junior Gold Miners ETF"),
}

BROAD_CATEGORY_SYMBOLS = {
    "AGG": (None, "Aggregate Bond ETF", "bond_broad", "bond"),
    "BIL": (None, "Treasury Bill ETF", "bond_treasury", "bond"),
    "BND": (None, "Total Bond Market ETF", "bond_broad", "bond"),
    "DIA": (None, "Dow 30 ETF", "dow_30", "equity"),
    "EEM": (None, "Emerging Markets Equity ETF", "emerging_markets_equity", "equity"),
    "EFA": (None, "Developed ex-US Equity ETF", "developed_ex_us_equity", "equity"),
    "HYG": (None, "High Yield Corporate Bond ETF", "bond_high_yield", "bond"),
    "IEF": (None, "Intermediate Treasury Bond ETF", "bond_treasury", "bond"),
    "IEFA": (None, "Developed ex-US Equity ETF", "developed_ex_us_equity", "equity"),
    "IEMG": (None, "Emerging Markets Equity ETF", "emerging_markets_equity", "equity"),
    "IWM": (None, "US Small Cap Equity ETF", "small_cap_us_equity", "equity"),
    "IVV": (None, "S&P 500 ETF", "broad_us_equity", "equity"),
    "LQD": (None, "Investment Grade Corporate Bond ETF", "bond_investment_grade", "bond"),
    "QQQ": (None, "Nasdaq 100 ETF", "nasdaq_100", "equity"),
    "QQQM": (None, "Nasdaq 100 ETF", "nasdaq_100", "equity"),
    "SHY": (None, "Short Treasury Bond ETF", "bond_treasury", "bond"),
    "SPY": (None, "S&P 500 ETF", "broad_us_equity", "equity"),
    "SPLG": (None, "S&P 500 ETF", "broad_us_equity", "equity"),
    "SPYM": (None, "S&P 500 ETF", "broad_us_equity", "equity"),
    "TIP": (None, "Inflation-Protected Treasury Bond ETF", "bond_tips", "bond"),
    "TLT": (None, "Long Treasury Bond ETF", "bond_treasury", "bond"),
    "VTI": (None, "Total US Equity ETF", "total_us_equity", "equity"),
    "VOO": (None, "S&P 500 ETF", "broad_us_equity", "equity"),
}

SECTOR_PATTERNS = [
    (r"\b(technology|semiconductor|software|cyber|cloud|internet|ai|robotics)\b", "Technology", "Technology ETF"),
    (r"\b(financial|bank|insurance|broker|capital markets)\b", "Financial Services", "Financial Services ETF"),
    (r"\b(health|biotech|pharma|pharmaceutical|medical|genomic)\b", "Healthcare", "Healthcare ETF"),
    (r"\b(energy|oil|gas|uranium|solar|clean energy)\b", "Energy", "Energy ETF"),
    (r"\b(industrial|aerospace|defense|transportation|infrastructure)\b", "Industrials", "Industrials ETF"),
    (r"\b(consumer discretionary|retail|homebuilder|leisure|gaming)\b", "Consumer Cyclical", "Consumer Cyclical ETF"),
    (r"\b(consumer staples|food|beverage)\b", "Consumer Defensive", "Consumer Defensive ETF"),
    (r"\b(utilities|utility)\b", "Utilities", "Utilities ETF"),
    (r"\b(real estate|reit)\b", "Real Estate", "Real Estate ETF"),
    (r"\b(materials|gold miners|mining|metals|steel|copper|lithium)\b", "Basic Materials", "Basic Materials ETF"),
    (r"\b(communication|telecom|media)\b", "Communication Services", "Communication Services ETF"),
]

LEVERAGED_OR_INVERSE_RE = re.compile(
    r"(ultrapro|ultrashort|\bproshares ultra\b|\b2x\b|\b3x\b|\bbull\b|\bbear\b|"
    r"\binverse\b|\bleveraged\b|daily .*(2x|3x)|"
    r"\bshort\s+(s&p|qqq|russell|dow|nasdaq|msci|china|oil|gold|financial|treasury|20\+))",
    re.IGNORECASE,
)


def _coalesce_numeric(frame: pd.DataFrame, primary: str, fallback: str) -> pd.Series:
    primary_values = pd.to_numeric(frame[primary], errors="coerce") if primary in frame else pd.Series(pd.NA, index=frame.index)
    fallback_values = pd.to_numeric(frame[fallback], errors="coerce") if fallback in frame else pd.Series(pd.NA, index=frame.index)
    return primary_values.fillna(fallback_values)


def _coerce_string(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def classify_etf(symbol: object, security_name: object) -> dict[str, object]:
    normalized_symbol = _coerce_string(symbol).upper()
    name = _coerce_string(security_name)
    text = f"{normalized_symbol} {name}".lower()
    is_leveraged_or_inverse = bool(LEVERAGED_OR_INVERSE_RE.search(text))

    if normalized_symbol in SECTOR_SYMBOLS:
        sector, industry = SECTOR_SYMBOLS[normalized_symbol]
        return {
            "sector": sector,
            "industry": industry,
            "category": "sector_etf",
            "asset_class": "equity",
            "label_confidence": "high",
            "is_leveraged_or_inverse": is_leveraged_or_inverse,
            "notes": "Exact ETF symbol map.",
        }

    if normalized_symbol in BROAD_CATEGORY_SYMBOLS:
        sector, industry, category, asset_class = BROAD_CATEGORY_SYMBOLS[normalized_symbol]
        return {
            "sector": sector,
            "industry": industry,
            "category": category,
            "asset_class": asset_class,
            "label_confidence": "high",
            "is_leveraged_or_inverse": is_leveraged_or_inverse,
            "notes": "Exact ETF symbol map.",
        }

    for pattern, sector, industry in SECTOR_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return {
                "sector": sector,
                "industry": industry,
                "category": "sector_etf",
                "asset_class": "equity",
                "label_confidence": "medium",
                "is_leveraged_or_inverse": is_leveraged_or_inverse,
                "notes": "ETF name matched sector keyword rule.",
            }

    if re.search(r"\bqqq\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Nasdaq 100 ETF", "nasdaq_100", "equity", "medium", is_leveraged_or_inverse)
    if re.search(r"\bdow\s?30\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Dow 30 ETF", "dow_30", "equity", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(russell\s?2000|small[- ]cap|s&p 600)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "US Small Cap Equity ETF", "small_cap_us_equity", "equity", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(mid[- ]cap|s&p 400)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "US Mid Cap Equity ETF", "mid_cap_us_equity", "equity", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(total world|global 100|all-world)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Global Equity ETF", "global_equity", "equity", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(developed markets|developed world|eafe|pacific|europe|latin america|taiwan)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Developed ex-US Equity ETF", "developed_ex_us_equity", "equity", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(emerging markets|emerging core)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Emerging Markets Equity ETF", "emerging_markets_equity", "equity", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(treasury|t-bill|government bond)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Treasury Bond ETF", "bond_treasury", "bond", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(corporate bond|investment grade|high yield|convertible securities)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Corporate Bond ETF", "bond_corporate", "bond", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(municipal|muni)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Municipal Bond ETF", "bond_municipal", "bond", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(bond|fixed income|income etf|clo|mbs|mortgage-backed|senior loan|short maturity|tips|inflation-protected)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Bond ETF", "bond_broad", "bond", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(bitcoin|ether|crypto)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Crypto ETF", "crypto", "crypto", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(gold|silver|oil|natural gas|commodity|copper)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Commodity ETF", "commodity", "commodity", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(currency|dollar|euro|yen)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Currency ETF", "currency", "currency", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(s&p 500|s&p500|s&p 100|s&p 1500|large[- ]cap|mega cap|broad market|total stock market|total u\.s\. stock|u\.s\. equity market|us equity|russell|dow jones|nasdaq 100)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Broad US Equity ETF", "broad_us_equity", "equity", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(msci|ftse|china|japan|korea|international)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "International Equity ETF", "international_equity", "equity", "medium", is_leveraged_or_inverse)
    if re.search(r"\b(dividend|value|growth|quality|momentum|low volatility|factor|fundamental|wide moat|capital strength|cash cows|buffer)\b", text, flags=re.IGNORECASE):
        return _etf_label(None, "Factor Equity ETF", "factor_equity", "equity", "medium", is_leveraged_or_inverse)

    return {
        "sector": None,
        "industry": "Unclassified ETF",
        "category": "unknown_etf",
        "asset_class": "unknown",
        "label_confidence": "review",
        "is_leveraged_or_inverse": is_leveraged_or_inverse,
        "notes": "ETF passed catalog liquidity/history filters but no classification rule matched.",
    }


def _etf_label(
    sector: str | None,
    industry: str,
    category: str,
    asset_class: str,
    confidence: str,
    is_leveraged_or_inverse: bool,
) -> dict[str, object]:
    return {
        "sector": sector,
        "industry": industry,
        "category": category,
        "asset_class": asset_class,
        "label_confidence": confidence,
        "is_leveraged_or_inverse": is_leveraged_or_inverse,
        "notes": "ETF name matched broad category rule.",
    }


def _latest_liquidity(liquidity_metrics: pd.DataFrame) -> pd.DataFrame:
    if liquidity_metrics.empty:
        return pd.DataFrame(columns=["symbol", "liquidity_date", "quality_adv20", "traded_days_20"])

    work = liquidity_metrics.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["symbol", "date"]).sort_values(["symbol", "date"])
    latest = work.groupby("symbol", as_index=False).tail(1).copy()
    latest["quality_adv20"] = _coalesce_numeric(latest, "quality_adv20", "adv20")
    latest["traded_days_20"] = _coalesce_numeric(latest, "quality_traded_days_20", "traded_days_20")
    latest = latest.rename(columns={"date": "liquidity_date"})
    return latest[["symbol", "liquidity_date", "quality_adv20", "traded_days_20"]]


def _catalog_hash(catalog: pd.DataFrame) -> str:
    hash_columns = [column for column in config.SECURITY_CLASSIFICATION_CATALOG_COLUMNS if column != "catalog_hash"]
    records = catalog[hash_columns].sort_values("symbol").to_dict(orient="records")
    payload = json.dumps(
        [{key: _json_safe(value) for key, value in record.items()} for record in records],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_safe(value: object) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat()
    return value


def _common_data_as_of(symbol_master: pd.DataFrame, liquidity_metrics: pd.DataFrame) -> pd.Timestamp | pd.NaT:
    candidates: list[pd.Timestamp] = []
    if "last_date" in symbol_master and not symbol_master.empty:
        last_date = pd.to_datetime(symbol_master["last_date"], errors="coerce").max()
        if not pd.isna(last_date):
            candidates.append(pd.Timestamp(last_date).normalize())
    if "date" in liquidity_metrics and not liquidity_metrics.empty:
        liquidity_date = pd.to_datetime(liquidity_metrics["date"], errors="coerce").max()
        if not pd.isna(liquidity_date):
            candidates.append(pd.Timestamp(liquidity_date).normalize())
    if not candidates:
        return pd.NaT
    return max(candidates)


def _build_non_sic_security_rows(security_master: pd.DataFrame, data_as_of: pd.Timestamp | pd.NaT) -> list[dict[str, object]]:
    if security_master.empty:
        return []

    work = security_master.copy()
    for column in ["asset_type", "sector_source", "sector", "industry", "security_name"]:
        if column not in work:
            work[column] = pd.NA

    selected = work[
        work["sector_source"].notna()
        & (work["sector_source"] != "sec_sic")
        & (work["asset_type"] != "etf")
        & (work["sector"].notna() | work["industry"].notna())
    ].copy()

    rows: list[dict[str, object]] = []
    for record in selected.to_dict(orient="records"):
        asset_type = record.get("asset_type")
        rows.append(
            {
                "symbol": record.get("symbol"),
                "asset_type": asset_type,
                "security_name": record.get("security_name"),
                "sector": record.get("sector"),
                "industry": record.get("industry"),
                "category": pd.NA,
                "asset_class": "equity" if asset_type == "stock" else asset_type,
                "label_source": record.get("sector_source"),
                "label_confidence": "medium",
                "is_etf": bool(record.get("is_etf")) if not pd.isna(record.get("is_etf")) else False,
                "is_leveraged_or_inverse": False,
                "quality_adv20": pd.NA,
                "age_years": pd.NA,
                "traded_days_20": pd.NA,
                "selection_reason": "security_master_non_sec_sic",
                "data_as_of": None if pd.isna(data_as_of) else data_as_of.date().isoformat(),
                "policy_version": POLICY_VERSION,
                "catalog_hash": pd.NA,
                "notes": "Included because live SIC labelers cannot reproduce this FONA non-SIC fallback.",
            }
        )
    return rows


def _build_etf_rows(
    security_master: pd.DataFrame,
    symbol_master: pd.DataFrame,
    liquidity_metrics: pd.DataFrame,
    data_as_of: pd.Timestamp | pd.NaT,
) -> list[dict[str, object]]:
    if security_master.empty or symbol_master.empty or liquidity_metrics.empty or pd.isna(data_as_of):
        return []

    securities = security_master.copy()
    symbols = symbol_master.copy()
    latest_liquidity = _latest_liquidity(liquidity_metrics)

    for column in ["asset_type", "sector_source", "security_name"]:
        if column not in securities:
            securities[column] = pd.NA

    etfs = securities[(securities["asset_type"] == "etf") & securities["sector_source"].isna()].copy()
    if etfs.empty:
        return []

    symbols["first_date"] = pd.to_datetime(symbols["first_date"], errors="coerce")
    symbols["last_date"] = pd.to_datetime(symbols["last_date"], errors="coerce")
    selected = etfs.merge(symbols[["symbol", "first_date", "last_date"]], on="symbol", how="left")
    selected = selected.merge(latest_liquidity, on="symbol", how="left")
    selected["age_years"] = (data_as_of - selected["first_date"]).dt.days / 365.25
    selected["stale_days"] = (data_as_of - selected["last_date"]).dt.days
    selected = selected[
        (selected["stale_days"] <= MAX_ETF_STALE_DAYS)
        & (selected["age_years"] >= MIN_ETF_AGE_YEARS)
        & (selected["quality_adv20"] >= MIN_ETF_QUALITY_ADV20)
        & (selected["traded_days_20"] >= MIN_ETF_TRADED_DAYS_20)
    ].copy()

    rows: list[dict[str, object]] = []
    for record in selected.to_dict(orient="records"):
        label = classify_etf(record.get("symbol"), record.get("security_name"))
        rows.append(
            {
                "symbol": record.get("symbol"),
                "asset_type": "etf",
                "security_name": record.get("security_name"),
                "sector": label["sector"],
                "industry": label["industry"],
                "category": label["category"],
                "asset_class": label["asset_class"],
                "label_source": "fona_etf_rule",
                "label_confidence": label["label_confidence"],
                "is_etf": True,
                "is_leveraged_or_inverse": label["is_leveraged_or_inverse"],
                "quality_adv20": record.get("quality_adv20"),
                "age_years": round(float(record.get("age_years")), 4),
                "traded_days_20": int(record.get("traded_days_20")),
                "selection_reason": (
                    f"sectorless_etf_adv20>={MIN_ETF_QUALITY_ADV20}_"
                    f"age>={MIN_ETF_AGE_YEARS}_traded_days>={MIN_ETF_TRADED_DAYS_20}"
                ),
                "data_as_of": data_as_of.date().isoformat(),
                "policy_version": POLICY_VERSION,
                "catalog_hash": pd.NA,
                "notes": label["notes"],
            }
        )
    return rows


def build_security_classification_catalog_df(
    security_master: pd.DataFrame,
    symbol_master: pd.DataFrame,
    liquidity_metrics: pd.DataFrame,
) -> pd.DataFrame:
    if security_master.empty:
        return empty_frame(config.SECURITY_CLASSIFICATION_CATALOG_COLUMNS)

    data_as_of = _common_data_as_of(symbol_master, liquidity_metrics)
    rows = _build_non_sic_security_rows(security_master, data_as_of)
    rows.extend(_build_etf_rows(security_master, symbol_master, liquidity_metrics, data_as_of))

    if not rows:
        return empty_frame(config.SECURITY_CLASSIFICATION_CATALOG_COLUMNS)

    catalog = pd.DataFrame(rows, columns=config.SECURITY_CLASSIFICATION_CATALOG_COLUMNS)
    catalog = catalog.drop_duplicates(subset=["symbol"], keep="first")
    catalog = catalog.sort_values("symbol").reset_index(drop=True)
    catalog["catalog_hash"] = _catalog_hash(catalog)
    return catalog[config.SECURITY_CLASSIFICATION_CATALOG_COLUMNS]


def build_security_classification_catalog(
    security_master_path: Path = config.SECURITY_MASTER_PATH,
    symbol_master_path: Path = config.SYMBOL_MASTER_PATH,
    liquidity_metrics_path: Path = config.LIQUIDITY_METRICS_PATH,
    output_path: Path = config.SECURITY_CLASSIFICATION_CATALOG_PATH,
) -> pd.DataFrame:
    security_master = read_parquet_if_exists(security_master_path, config.SECURITY_MASTER_COLUMNS)
    symbol_master = read_parquet_if_exists(symbol_master_path, config.SYMBOL_MASTER_COLUMNS)
    liquidity_metrics = read_parquet_if_exists(liquidity_metrics_path, config.LIQUIDITY_COLUMNS)
    catalog = build_security_classification_catalog_df(security_master, symbol_master, liquidity_metrics)
    write_parquet(catalog, output_path)
    print(f"[classification_catalog] Wrote {len(catalog):,} rows to {output_path}")
    return catalog


if __name__ == "__main__":
    config.ensure_directories()
    build_security_classification_catalog()

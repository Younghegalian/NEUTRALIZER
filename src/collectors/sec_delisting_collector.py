from __future__ import annotations

import re
import time
import zipfile
from datetime import date
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd

from src import config
from src.utils import normalize_symbol, parse_date, write_parquet


SEC_HEADERS = {
    "User-Agent": "FONA/1.0 admin@example.com",
    "Accept-Encoding": "gzip, deflate",
}
SEC_ARCHIVES_ROOT = "https://www.sec.gov/Archives/"
SEC_MASTER_INDEX_URL = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
SEC_COMPANY_TICKERS_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_FORM345_PAGE_URL = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"


def _quarters(start_year: int, end_year: int) -> list[tuple[int, int]]:
    return [(year, quarter) for year in range(start_year, end_year + 1) for quarter in range(1, 5)]


def _request_text(url: str, sleep_seconds: float = 0.12) -> str:
    import requests

    response = requests.get(url, headers=SEC_HEADERS, timeout=(5, 60))
    response.raise_for_status()
    time.sleep(sleep_seconds)
    return response.text


def _request_bytes(url: str, sleep_seconds: float = 0.12) -> bytes:
    import requests

    response = requests.get(url, headers=SEC_HEADERS, timeout=(5, 120))
    response.raise_for_status()
    time.sleep(sleep_seconds)
    return response.content


def parse_master_idx(text: str) -> pd.DataFrame:
    marker = "CIK|Company Name|Form Type|Date Filed|Filename"
    if marker not in text:
        return pd.DataFrame(columns=["cik", "company_name", "form_type", "date_filed", "filename"])
    data = "\n".join(text[text.index(marker) :].splitlines()[2:])
    if not data.strip():
        return pd.DataFrame(columns=["cik", "company_name", "form_type", "date_filed", "filename"])
    return pd.read_csv(
        StringIO(data),
        sep="|",
        names=["cik", "company_name", "form_type", "date_filed", "filename"],
        dtype=str,
    )


def collect_sec_delisting_filings(
    start_year: int = 2010,
    end_year: int | None = None,
    raw_dir: Path = config.RAW_SEC_DIR,
    output_path: Path = config.SEC_DELISTING_FILINGS_PATH,
) -> pd.DataFrame:
    end_year = end_year or date.today().year
    index_dir = raw_dir / "full-index"
    index_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    for year, quarter in _quarters(start_year, end_year):
        if year == date.today().year and quarter > ((date.today().month - 1) // 3 + 1):
            continue
        raw_path = index_dir / f"{year}q{quarter}_master.idx"
        if raw_path.exists():
            text = raw_path.read_text(encoding="latin1")
        else:
            url = SEC_MASTER_INDEX_URL.format(year=year, quarter=quarter)
            try:
                text = _request_text(url)
            except Exception as exc:
                print(f"[sec_delistings] Skipping {year} Q{quarter}: {exc}")
                continue
            raw_path.write_text(text, encoding="latin1")

        df = parse_master_idx(text)
        df = df[df["form_type"].isin(["25", "25-NSE"])].copy()
        if df.empty:
            continue
        df["date_filed"] = pd.to_datetime(df["date_filed"], errors="coerce")
        df["year"] = year
        df["quarter"] = quarter
        frames.append(df)
        print(f"[sec_delistings] {year} Q{quarter}: {len(df):,} Form 25/25-NSE rows")

    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if result.empty:
        result = pd.DataFrame(
            columns=["cik", "company_name", "form_type", "date_filed", "filename", "year", "quarter"]
        )
    result["cik"] = pd.to_numeric(result["cik"], errors="coerce").astype("Int64")
    result = result.dropna(subset=["cik", "date_filed", "filename"]).drop_duplicates(
        ["cik", "form_type", "date_filed", "filename"]
    )
    write_parquet(result, output_path)
    print(f"[sec_delistings] Wrote {len(result):,} filing rows to {output_path}")
    return result


def _xml_value(text: str, tag: str) -> str | None:
    match = re.search(fr"<{tag}>(.*?)</{tag}>", text, flags=re.I | re.S)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()


def extract_delisting_doc_fields(text: str) -> dict[str, object]:
    description = _xml_value(text, "descriptionClassSecurity")
    signature_date = _xml_value(text, "signatureDate")
    effective_match = re.search(
        r"effective\s+(?:at\s+the\s+opening\s+of\s+the\s+trading\s+session\s+on\s+)?([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        text,
    )
    effective_date = parse_date(effective_match.group(1)) if effective_match else pd.NaT
    symbol_matches = re.findall(
        r"(?:ticker|symbol)\s*(?:is|:)?\s*['\"]?([A-Z][A-Z0-9.\-]{0,9})['\"]?",
        text,
        flags=re.I,
    )
    symbols = sorted({normalize_symbol(symbol) for symbol in symbol_matches if normalize_symbol(symbol)})
    return {
        "security_description": description,
        "signature_date": parse_date(signature_date) if signature_date else pd.NaT,
        "effective_date": effective_date,
        "symbols_in_doc": ",".join(symbols),
    }


def enrich_sec_delisting_documents(
    filings_path: Path = config.SEC_DELISTING_FILINGS_PATH,
    raw_dir: Path = config.RAW_SEC_DIR,
    output_path: Path = config.SEC_DELISTING_FILINGS_PATH,
    limit: int | None = None,
) -> pd.DataFrame:
    filings = pd.read_parquet(filings_path)
    docs_dir = raw_dir / "filings"
    docs_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    work = filings.head(limit) if limit else filings

    for idx, row in enumerate(work.itertuples(index=False), start=1):
        filename = row.filename
        local_path = docs_dir / filename.replace("/", "_")
        if local_path.exists():
            text = local_path.read_text(encoding="utf-8", errors="ignore")
        else:
            try:
                text = _request_text(SEC_ARCHIVES_ROOT + filename)
            except Exception as exc:
                print(f"[sec_delistings] Filing fetch failed {filename}: {exc}")
                text = ""
            local_path.write_text(text, encoding="utf-8", errors="ignore")
        fields = extract_delisting_doc_fields(text)
        rows.append(fields)
        if idx % 500 == 0 or idx == len(work):
            print(f"[sec_delistings] Enriched {idx:,}/{len(work):,} filing documents")

    enriched = filings.copy()
    fields_df = pd.DataFrame(rows)
    for column in ["security_description", "signature_date", "effective_date", "symbols_in_doc"]:
        enriched[column] = pd.NA
    enriched.loc[work.index, fields_df.columns] = fields_df.values
    write_parquet(enriched, output_path)
    print(f"[sec_delistings] Wrote enriched filings to {output_path}")
    return enriched


def _form345_links() -> list[tuple[int, int, str]]:
    text = _request_text(SEC_FORM345_PAGE_URL)
    links = re.findall(r'href="([^"]*/(\d{4})q([1-4])_form345\.zip)"', text)
    out = []
    for href, year, quarter in links:
        url = href if href.startswith("http") else "https://www.sec.gov" + href
        out.append((int(year), int(quarter), url))
    return sorted(set(out))


def collect_sec_form345_ticker_map(
    start_year: int = 2010,
    end_year: int | None = None,
    raw_dir: Path = config.RAW_SEC_DIR,
    output_path: Path = config.SEC_FORM345_TICKER_MAP_PATH,
) -> pd.DataFrame:
    end_year = end_year or date.today().year
    form345_dir = raw_dir / "form345"
    form345_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []

    for year, quarter, url in _form345_links():
        if year < start_year or year > end_year:
            continue
        zip_path = form345_dir / f"{year}q{quarter}_form345.zip"
        if not zip_path.exists():
            print(f"[sec_form345] Downloading {year} Q{quarter}")
            zip_path.write_bytes(_request_bytes(url))

        try:
            with zipfile.ZipFile(zip_path) as zf:
                with zf.open("SUBMISSION.tsv") as fh:
                    df = pd.read_csv(
                        fh,
                        sep="\t",
                        dtype=str,
                        usecols=["FILING_DATE", "ISSUERCIK", "ISSUERNAME", "ISSUERTRADINGSYMBOL"],
                    )
        except Exception as exc:
            print(f"[sec_form345] Skipping {zip_path}: {exc}")
            continue

        df = df.rename(
            columns={
                "FILING_DATE": "filing_date",
                "ISSUERCIK": "cik",
                "ISSUERNAME": "issuer_name",
                "ISSUERTRADINGSYMBOL": "symbol",
            }
        )
        df["year"] = year
        df["quarter"] = quarter
        frames.append(df)
        print(f"[sec_form345] {year} Q{quarter}: {len(df):,} submission rows")

    if frames:
        all_rows = pd.concat(frames, ignore_index=True)
    else:
        all_rows = pd.DataFrame(columns=["filing_date", "cik", "issuer_name", "symbol", "year", "quarter"])

    all_rows["cik"] = pd.to_numeric(all_rows["cik"], errors="coerce").astype("Int64")
    all_rows["symbol"] = all_rows["symbol"].map(normalize_symbol)
    all_rows["filing_date"] = pd.to_datetime(all_rows["filing_date"], errors="coerce")
    all_rows = all_rows.dropna(subset=["cik", "symbol", "filing_date"])
    all_rows = all_rows[~all_rows["symbol"].astype(str).str.isnumeric()]

    result = (
        all_rows.groupby(["cik", "symbol"], as_index=False)
        .agg(
            issuer_name=("issuer_name", "last"),
            first_form345_date=("filing_date", "min"),
            last_form345_date=("filing_date", "max"),
            form345_count=("filing_date", "count"),
        )
        .sort_values(["cik", "last_form345_date"])
    )
    write_parquet(result, output_path)
    print(f"[sec_form345] Wrote {len(result):,} CIK-symbol rows to {output_path}")
    return result


def _collect_current_sec_tickers() -> pd.DataFrame:
    import requests

    response = requests.get(SEC_COMPANY_TICKERS_EXCHANGE_URL, headers=SEC_HEADERS, timeout=(5, 30))
    response.raise_for_status()
    payload = response.json()
    df = pd.DataFrame(payload["data"], columns=payload["fields"])
    df = df.rename(columns={"ticker": "symbol"})
    df["cik"] = pd.to_numeric(df["cik"], errors="coerce").astype("Int64")
    df["symbol"] = df["symbol"].map(normalize_symbol)
    return df.dropna(subset=["cik", "symbol"])


def build_sec_delisted_candidates(
    filings_path: Path = config.SEC_DELISTING_FILINGS_PATH,
    form345_path: Path = config.SEC_FORM345_TICKER_MAP_PATH,
    output_path: Path = config.SEC_DELISTED_CANDIDATES_PATH,
) -> pd.DataFrame:
    filings = pd.read_parquet(filings_path)
    form345 = pd.read_parquet(form345_path) if form345_path.exists() else pd.DataFrame()
    current = _collect_current_sec_tickers()
    current = current[["cik", "symbol", "exchange"]].copy()
    current["ticker_source"] = "sec_company_tickers_exchange"

    symbol_rows = []
    if not form345.empty:
        f345 = form345[["cik", "symbol", "last_form345_date", "form345_count"]].copy()
        f345["ticker_source"] = "sec_form345"
        symbol_rows.append(f345)
    symbol_rows.append(current)
    symbols = pd.concat(symbol_rows, ignore_index=True, sort=False).dropna(subset=["cik", "symbol"])

    if "symbols_in_doc" in filings.columns:
        from_docs = filings[["cik", "symbols_in_doc"]].dropna()
        doc_rows = []
        for row in from_docs.itertuples(index=False):
            for symbol in str(row.symbols_in_doc).split(","):
                symbol = normalize_symbol(symbol)
                if symbol:
                    doc_rows.append({"cik": row.cik, "symbol": symbol, "ticker_source": "sec_form25_text"})
        if doc_rows:
            symbols = pd.concat([symbols, pd.DataFrame(doc_rows)], ignore_index=True, sort=False)

    symbols = symbols.drop_duplicates(["cik", "symbol", "ticker_source"])
    candidates = filings.merge(symbols, on="cik", how="left")
    candidates["candidate_symbol"] = candidates["symbol"]
    candidates["candidate_symbol_count_for_filing"] = candidates.groupby("filename")["candidate_symbol"].transform(
        lambda s: s.dropna().nunique()
    )
    candidates = candidates.drop(columns=["symbol"])
    write_parquet(candidates, output_path)
    print(f"[sec_candidates] Wrote {len(candidates):,} SEC delisting candidate rows to {output_path}")
    return candidates


def collect_sec_delisted_candidates(
    start_year: int = 2010,
    end_year: int | None = None,
    enrich_docs: bool = True,
) -> pd.DataFrame:
    collect_sec_delisting_filings(start_year=start_year, end_year=end_year)
    if enrich_docs:
        enrich_sec_delisting_documents()
    collect_sec_form345_ticker_map(start_year=start_year, end_year=end_year)
    return build_sec_delisted_candidates()


if __name__ == "__main__":
    config.ensure_directories()
    collect_sec_delisted_candidates()

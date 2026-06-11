from __future__ import annotations

import hashlib
import html
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

from src import config
from src.collectors.active_symbols import active_symbol_list
from src.utils import (
    coerce_numeric,
    empty_frame,
    first_present,
    normalize_column_name,
    normalize_symbol,
    parse_date,
    write_parquet,
)


STOOQ_DAILY_US_URL = "https://stooq.com/db/h/d_us_txt.zip"
STOOQ_HISTORY_URL = "https://stooq.com/q/d/"
STOOQ_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

DATE_COLUMNS = ["date", "datetime", "timestamp", "time"]
OPEN_COLUMNS = ["open", "o"]
HIGH_COLUMNS = ["high", "h"]
LOW_COLUMNS = ["low", "l"]
CLOSE_COLUMNS = ["close", "c"]
VOLUME_COLUMNS = ["volume", "vol", "v"]


def _yyyymmdd(value: date | None) -> str | None:
    return value.strftime("%Y%m%d") if value else None


def stooq_vendor_symbol(symbol: str) -> str:
    return f"{symbol.lower()}.us"


def stooq_vendor_symbol_candidates(symbol: str) -> list[str]:
    base = symbol.strip().upper()
    candidates = [stooq_vendor_symbol(base)]
    if "." in base:
        candidates.append(stooq_vendor_symbol(base.replace(".", "-")))
    if "-" in base:
        candidates.append(stooq_vendor_symbol(base.replace("-", ".")))
    return list(dict.fromkeys(candidates))


def _new_stooq_session():
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": STOOQ_USER_AGENT})
    return session


def _solve_stooq_challenge(session, text: str) -> bool:
    match = re.search(r'const c="([^"]+)",d=(\d+)', text)
    if not match:
        return False

    challenge, difficulty = match.group(1), int(match.group(2))
    target = "0" * difficulty
    nonce = 0
    while True:
        digest = hashlib.sha256((challenge + str(nonce)).encode()).hexdigest()
        if digest.startswith(target):
            break
        nonce += 1

    response = session.post(
        "https://stooq.com/__verify",
        data={"c": challenge, "n": str(nonce)},
        timeout=30,
    )
    return response.ok


STOOQ_REQUEST_TIMEOUT = (5, 15)


def _get_stooq_text(session, url: str) -> str:
    response = session.get(url, timeout=STOOQ_REQUEST_TIMEOUT)
    response.raise_for_status()
    if _solve_stooq_challenge(session, response.text):
        response = session.get(url, timeout=STOOQ_REQUEST_TIMEOUT)
        response.raise_for_status()
    return response.text


def _strip_tags(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", value)
    return html.unescape(cleaned).strip()


def parse_stooq_history_html(text: str) -> pd.DataFrame:
    table_match = re.search(r"<table[^>]*id=fth1[^>]*>(.*?)</table>", text, flags=re.I | re.S)
    if not table_match:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])

    table = table_match.group(1)
    rows: list[dict[str, str]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table, flags=re.I | re.S):
        cells = [_strip_tags(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)]
        if len(cells) < 9 or cells[0].lower() == "no.":
            continue
        rows.append(
            {
                "Date": cells[1],
                "Open": cells[2].replace(",", ""),
                "High": cells[3].replace(",", ""),
                "Low": cells[4].replace(",", ""),
                "Close": cells[5].replace(",", ""),
                "Volume": cells[8].replace(",", ""),
            }
        )

    return pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])


def download_stooq_symbol_html(
    symbol: str,
    raw_dir: Path = config.RAW_STOOQ_DIR,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Path | None:
    session = _new_stooq_session()
    html_dir = raw_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)

    for vendor_symbol in stooq_vendor_symbol_candidates(symbol):
        output_path = html_dir / f"{vendor_symbol}.csv"
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path

        query = f"s={vendor_symbol}"
        url = f"{STOOQ_HISTORY_URL}?{query}"

        try:
            text = _get_stooq_text(session, url)
        except Exception:
            continue

        df = parse_stooq_history_html(text)
        if df.empty:
            continue

        df.to_csv(output_path, index=False)
        return output_path

    return None


def collect_stooq_html_active(
    raw_dir: Path = config.RAW_STOOQ_DIR,
    output_path: Path = config.STOOQ_STAGING_PATH,
    start_date: date | None = None,
    end_date: date | None = None,
    max_workers: int = 8,
    limit: int | None = None,
) -> pd.DataFrame:
    symbols = active_symbol_list(include_etfs=True, liquid_equity_like=True)
    if limit is not None:
        symbols = symbols[:limit]

    print(f"[stooq_html] Collecting {len(symbols):,} active symbols from Stooq HTML pages")
    successes = 0
    failures = 0
    started = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                download_stooq_symbol_html,
                symbol,
                raw_dir,
                start_date,
                end_date,
            ): symbol
            for symbol in symbols
        }
        for idx, future in enumerate(as_completed(futures), start=1):
            symbol = futures[future]
            try:
                path = future.result()
                if path is None:
                    failures += 1
                else:
                    successes += 1
            except Exception as exc:
                failures += 1
                print(f"[stooq_html] {symbol} failed: {exc}")

            if idx % 250 == 0 or idx == len(symbols):
                elapsed = max(time.time() - started, 1)
                rate = idx / elapsed
                print(
                    f"[stooq_html] {idx:,}/{len(symbols):,} done "
                    f"({successes:,} ok, {failures:,} missing, {rate:.2f} symbols/sec)"
                )

    return normalize_stooq_directory(raw_dir=raw_dir, output_path=output_path)


def download_stooq_archive(
    raw_dir: Path = config.RAW_STOOQ_DIR,
    url: str = STOOQ_DAILY_US_URL,
    force: bool = False,
) -> Path:
    import requests

    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_path = raw_dir / Path(url).name
    if archive_path.exists() and not force:
        print(f"[stooq] Using existing archive {archive_path}")
        return archive_path

    print(f"[stooq] Downloading {url}")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with archive_path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
    print(f"[stooq] Saved archive to {archive_path}")
    return archive_path


def extract_stooq_archive(archive_path: Path, raw_dir: Path = config.RAW_STOOQ_DIR) -> Path:
    extract_dir = raw_dir / archive_path.stem
    if extract_dir.exists() and any(extract_dir.rglob("*")):
        return extract_dir

    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as zf:
        zf.extractall(extract_dir)
    return extract_dir


def _read_price_file(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.read_csv(path, sep=None, engine="python")


def normalize_stooq_file(path: Path) -> pd.DataFrame:
    raw = _read_price_file(path)
    if raw.empty:
        return empty_frame(config.CANONICAL_PRICE_COLUMNS)

    raw = raw.copy()
    raw.columns = [normalize_column_name(col) for col in raw.columns]

    date_col = first_present(raw.columns, DATE_COLUMNS)
    open_col = first_present(raw.columns, OPEN_COLUMNS)
    high_col = first_present(raw.columns, HIGH_COLUMNS)
    low_col = first_present(raw.columns, LOW_COLUMNS)
    close_col = first_present(raw.columns, CLOSE_COLUMNS)
    volume_col = first_present(raw.columns, VOLUME_COLUMNS)

    if not all([date_col, open_col, high_col, low_col, close_col]):
        missing = [
            name
            for name, col in [
                ("date", date_col),
                ("open", open_col),
                ("high", high_col),
                ("low", low_col),
                ("close", close_col),
            ]
            if col is None
        ]
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")

    vendor_symbol = path.stem
    symbol = normalize_symbol(vendor_symbol)
    out = pd.DataFrame(
        {
            "date": raw[date_col].map(parse_date),
            "symbol": symbol,
            "vendor_symbol": vendor_symbol,
            "open": coerce_numeric(raw[open_col]),
            "high": coerce_numeric(raw[high_col]),
            "low": coerce_numeric(raw[low_col]),
            "close": coerce_numeric(raw[close_col]),
            "volume": coerce_numeric(raw[volume_col]) if volume_col else pd.NA,
            "adjusted_close": pd.NA,
            "source": "stooq",
            "is_delisted_source": False,
        }
    )
    return out[config.CANONICAL_PRICE_COLUMNS]


def normalize_stooq_directory(
    raw_dir: Path = config.RAW_STOOQ_DIR,
    output_path: Path = config.STOOQ_STAGING_PATH,
) -> pd.DataFrame:
    paths = sorted(list(raw_dir.rglob("*.txt")) + list(raw_dir.rglob("*.csv")))
    frames: list[pd.DataFrame] = []
    for path in paths:
        if path.name.startswith("."):
            continue
        try:
            frames.append(normalize_stooq_file(path))
        except Exception as exc:
            print(f"[stooq] Skipping {path}: {exc}")

    if frames:
        result = pd.concat(frames, ignore_index=True)
    else:
        result = empty_frame(config.CANONICAL_PRICE_COLUMNS)

    write_parquet(result, output_path)
    print(f"[stooq] Wrote {len(result):,} rows to {output_path}")
    return result


def collect_stooq(
    raw_dir: Path = config.RAW_STOOQ_DIR,
    output_path: Path = config.STOOQ_STAGING_PATH,
    download: bool = True,
    force_download: bool = False,
    url: str = STOOQ_DAILY_US_URL,
    start_date: date | None = None,
    end_date: date | None = None,
    enable_html_fallback: bool = False,
) -> pd.DataFrame:
    if download:
        try:
            archive_path = download_stooq_archive(raw_dir=raw_dir, url=url, force=force_download)
            extract_stooq_archive(archive_path, raw_dir=raw_dir)
        except Exception as exc:
            if enable_html_fallback:
                print(f"[stooq] Bulk archive download failed ({exc}); falling back to HTML collection.")
                return collect_stooq_html_active(
                    raw_dir=raw_dir,
                    output_path=output_path,
                    start_date=start_date,
                    end_date=end_date,
                )
            print(f"[stooq] Bulk archive download failed ({exc}); continuing without Stooq bulk data.")
    return normalize_stooq_directory(raw_dir=raw_dir, output_path=output_path)


if __name__ == "__main__":
    config.ensure_directories()
    collect_stooq()

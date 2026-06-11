from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import write_parquet


SOURCE_PRIORITY = {
    "stooq": 1,
    "yahoo_fallback": 2,
    "yahoo_delisted_probe": 3,
    "kaggle_arandkei_delisted": 4,
}


def deduplicate_prices_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df.copy(), pd.DataFrame(columns=["date", "symbol", "sources_found", "selected_source"])

    work = df.copy()
    work["_source_priority"] = work["source"].map(SOURCE_PRIORITY).fillna(99).astype(int)
    work["_row_order"] = range(len(work))
    work = work.sort_values(["date", "symbol", "_source_priority", "_row_order"])

    selected = work.drop_duplicates(["date", "symbol"], keep="first").drop(
        columns=["_source_priority", "_row_order"]
    )

    duplicate_key_counts = work.groupby(["date", "symbol"], dropna=False).size()
    duplicate_keys = duplicate_key_counts[duplicate_key_counts > 1].index

    if len(duplicate_keys) == 0:
        report = pd.DataFrame(columns=["date", "symbol", "sources_found", "selected_source"])
    else:
        dupes = work.set_index(["date", "symbol"]).loc[duplicate_keys].reset_index()
        report = (
            dupes.groupby(["date", "symbol"], as_index=False)
            .agg(sources_found=("source", lambda s: ",".join(sorted(set(s.astype(str))))))
            .sort_values(["date", "symbol"])
        )
        selected_sources = selected.set_index(["date", "symbol"])["source"]
        report["selected_source"] = [
            selected_sources.loc[(row.date, row.symbol)] for row in report.itertuples(index=False)
        ]

    selected = selected.sort_values(["symbol", "date"]).reset_index(drop=True)
    return selected, report.reset_index(drop=True)


def deduplicate_prices(
    input_path: Path,
    output_path: Path = config.DAILY_PRICES_PATH,
    report_path: Path = config.DUPLICATE_REPORT_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_parquet(input_path)
    selected, report = deduplicate_prices_df(df)
    write_parquet(selected, output_path)
    write_parquet(report, report_path)
    print(f"[deduplicate] Wrote {len(selected):,} canonical rows to {output_path}")
    print(f"[deduplicate] Wrote {len(report):,} duplicate groups to {report_path}")
    return selected, report

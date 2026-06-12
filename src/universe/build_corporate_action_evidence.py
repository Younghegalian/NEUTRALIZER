from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, normalize_symbol, write_parquet


def build_corporate_action_evidence_df(
    evidence_rows: list[dict[str, object]] | None = None,
) -> pd.DataFrame:
    rows = evidence_rows if evidence_rows is not None else config.CURATED_CORPORATE_ACTION_EVIDENCE
    if not rows:
        return empty_frame(config.CORPORATE_ACTION_EVIDENCE_COLUMNS)

    evidence = pd.DataFrame(rows).copy()
    for column in config.CORPORATE_ACTION_EVIDENCE_COLUMNS:
        if column not in evidence.columns:
            evidence[column] = None

    evidence["symbol"] = evidence["symbol"].map(normalize_symbol)
    evidence["event_date"] = pd.to_datetime(evidence["event_date"], errors="coerce").dt.normalize()
    evidence["action_ratio"] = pd.to_numeric(evidence["action_ratio"], errors="coerce")
    evidence["reference_price"] = pd.to_numeric(evidence["reference_price"], errors="coerce")
    for column in ["event_type", "source_name", "source_url", "source_authority", "confidence", "notes"]:
        evidence[column] = evidence[column].fillna("").astype(str).str.strip()

    evidence = evidence.dropna(subset=["symbol", "event_date"]).copy()
    evidence = evidence[evidence["source_url"].ne("")]
    evidence = evidence.sort_values(["symbol", "event_date", "event_type"]).reset_index(drop=True)
    return evidence[config.CORPORATE_ACTION_EVIDENCE_COLUMNS]


def build_corporate_action_evidence(
    output_path: Path = config.CORPORATE_ACTION_EVIDENCE_PATH,
) -> pd.DataFrame:
    result = build_corporate_action_evidence_df()
    write_parquet(result, output_path)
    print(f"[corporate_action_evidence] Wrote {len(result):,} rows to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    build_corporate_action_evidence()

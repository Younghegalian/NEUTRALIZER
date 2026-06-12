from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import config
from src.utils import empty_frame, normalize_symbol, write_parquet


def build_symbol_aliases_df(rows: list[dict[str, object]] | None = None) -> pd.DataFrame:
    source_rows = rows if rows is not None else config.CURATED_SYMBOL_ALIASES
    if not source_rows:
        return empty_frame(config.SYMBOL_ALIAS_COLUMNS)

    aliases = pd.DataFrame(source_rows)
    for column in config.SYMBOL_ALIAS_COLUMNS:
        if column not in aliases.columns:
            aliases[column] = pd.NA

    aliases["canonical_symbol"] = aliases["canonical_symbol"].map(normalize_symbol)
    aliases["alias_symbol"] = aliases["alias_symbol"].map(normalize_symbol)
    aliases["start_date"] = pd.to_datetime(aliases["start_date"], errors="coerce").dt.normalize()
    aliases["end_date"] = pd.to_datetime(aliases["end_date"], errors="coerce").dt.normalize()
    aliases = aliases.dropna(subset=["canonical_symbol", "alias_symbol", "start_date"])
    aliases = aliases[aliases["canonical_symbol"] != aliases["alias_symbol"]]
    aliases = aliases.sort_values(["alias_symbol", "start_date", "canonical_symbol"])
    return aliases[config.SYMBOL_ALIAS_COLUMNS].reset_index(drop=True)


def build_symbol_aliases(
    output_path: Path = config.SYMBOL_ALIASES_PATH,
) -> pd.DataFrame:
    result = build_symbol_aliases_df()
    write_parquet(result, output_path)
    print(f"[symbol_aliases] Wrote {len(result):,} rows to {output_path}")
    return result


if __name__ == "__main__":
    config.ensure_directories()
    build_symbol_aliases()

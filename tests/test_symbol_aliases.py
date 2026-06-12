from __future__ import annotations

import unittest

from src.normalize.build_symbol_aliases import build_symbol_aliases_df


class SymbolAliasTest(unittest.TestCase):
    def test_curated_symbol_aliases_include_fiserv_fi_window(self) -> None:
        aliases = build_symbol_aliases_df()
        row = aliases[(aliases["canonical_symbol"] == "FISV") & (aliases["alias_symbol"] == "FI")].iloc[0]

        self.assertEqual(row["start_date"].strftime("%Y-%m-%d"), "2023-06-07")
        self.assertEqual(row["end_date"].strftime("%Y-%m-%d"), "2025-11-10")
        self.assertEqual(row["action_type"], "ticker_change")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

import pandas as pd

from src import config
from src.universe.build_return_quality_flags import build_return_quality_flags_df
from src.universe.compute_liquidity import compute_liquidity_metrics_df


def _price_row(date: str, symbol: str, close: float, volume: int, source: str = "yahoo_fallback") -> dict:
    return {
        "date": date,
        "symbol": symbol,
        "vendor_symbol": symbol,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": volume,
        "adjusted_close": close,
        "source": source,
        "is_delisted_source": source == "yahoo_delisted_probe",
    }


class ReturnQualityTest(unittest.TestCase):
    def test_reverse_split_evidence_is_exclusion_candidate(self) -> None:
        prices = pd.DataFrame(
            [
                _price_row("2022-12-15", "COSM", 0.33, 52_128_200),
                _price_row("2022-12-16", "COSM", 23.01, 120_031_700),
            ],
            columns=config.CANONICAL_PRICE_COLUMNS,
        )

        flags = build_return_quality_flags_df(prices)

        self.assertEqual(len(flags), 1)
        row = flags.iloc[0]
        self.assertEqual(row["symbol"], "COSM")
        self.assertEqual(row["event_type"], "reverse_split")
        self.assertTrue(bool(row["exclude_from_backtest_return"]))
        self.assertIn("sec.gov", row["evidence_url"])

    def test_news_spike_is_flagged_without_default_exclusion(self) -> None:
        prices = pd.DataFrame(
            [
                _price_row("2023-10-10", "TPST", 3.12, 2_094_931),
                _price_row("2023-10-11", "TPST", 127.01, 13_309_992),
            ],
            columns=config.CANONICAL_PRICE_COLUMNS,
        )

        flags = build_return_quality_flags_df(prices)

        self.assertEqual(len(flags), 1)
        row = flags.iloc[0]
        self.assertEqual(row["severity"], "event_risk")
        self.assertEqual(row["event_type"], "news_spike")
        self.assertFalse(bool(row["exclude_from_backtest_return"]))
        self.assertIn("sec.gov", row["evidence_url"])

    def test_liquidity_marks_return_exclusions_as_price_quality_suspect(self) -> None:
        prices = pd.DataFrame(
            [
                _price_row("2022-12-15", "COSM", 0.33, 52_128_200),
                _price_row("2022-12-16", "COSM", 23.01, 120_031_700),
            ],
            columns=config.CANONICAL_PRICE_COLUMNS,
        )

        liquidity = compute_liquidity_metrics_df(prices)
        split_day = liquidity.loc[liquidity["date"].eq(pd.Timestamp("2022-12-16"))].iloc[0]

        self.assertTrue(bool(split_day["is_price_quality_suspect"]))


if __name__ == "__main__":
    unittest.main()

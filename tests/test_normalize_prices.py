from __future__ import annotations

import unittest

import pandas as pd

from src.normalize.normalize_prices import normalize_price_frame
from src.utils import normalize_symbol, parse_date


class NormalizePricesTest(unittest.TestCase):
    def test_symbol_normalization(self) -> None:
        self.assertEqual(normalize_symbol("aapl.us"), "AAPL")
        self.assertEqual(normalize_symbol("msft.us"), "MSFT")
        self.assertEqual(normalize_symbol("BRK.B"), "BRK.B")

    def test_yyyymmdd_date_parsing(self) -> None:
        self.assertEqual(parse_date(20220309).date().isoformat(), "2022-03-09")
        self.assertEqual(parse_date("20220309").date().isoformat(), "2022-03-09")

    def test_dedup_priority_and_delisted_only_retained(self) -> None:
        stooq = pd.DataFrame(
            [
                {
                    "date": "2020-01-02",
                    "symbol": "AAPL",
                    "vendor_symbol": "aapl.us",
                    "open": 100,
                    "high": 110,
                    "low": 99,
                    "close": 105,
                    "volume": 1000,
                    "adjusted_close": None,
                    "source": "stooq",
                    "is_delisted_source": False,
                }
            ]
        )
        kaggle = pd.DataFrame(
            [
                {
                    "date": "2020-01-02",
                    "symbol": "AAPL",
                    "vendor_symbol": "AAPL",
                    "open": 90,
                    "high": 95,
                    "low": 88,
                    "close": 91,
                    "volume": 1000,
                    "adjusted_close": None,
                    "source": "kaggle_arandkei_delisted",
                    "is_delisted_source": True,
                },
                {
                    "date": "2020-01-02",
                    "symbol": "OLDQ",
                    "vendor_symbol": "OLDQ",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "volume": 5000,
                    "adjusted_close": None,
                    "source": "kaggle_arandkei_delisted",
                    "is_delisted_source": True,
                },
            ]
        )

        daily_prices, symbol_master, duplicate_report, bad_rows = normalize_price_frame([stooq, kaggle])

        self.assertEqual(len(bad_rows), 0)
        aapl = daily_prices[daily_prices["symbol"] == "AAPL"].iloc[0]
        self.assertEqual(aapl["source"], "stooq")
        self.assertIn("OLDQ", set(daily_prices["symbol"]))
        self.assertTrue(
            bool(symbol_master.loc[symbol_master["symbol"] == "OLDQ", "has_delisted_source"].iloc[0])
        )
        self.assertEqual(len(duplicate_report), 1)
        self.assertEqual(duplicate_report.iloc[0]["selected_source"], "stooq")


if __name__ == "__main__":
    unittest.main()

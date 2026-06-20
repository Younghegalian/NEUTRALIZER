from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.normalize.normalize_prices import normalize_price_frame, normalize_prices
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

    def test_rejects_ohlc_outside_high_low(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "date": "2020-01-02",
                    "symbol": "BAD",
                    "vendor_symbol": "BAD",
                    "open": 9,
                    "high": 10,
                    "low": 10,
                    "close": 11,
                    "volume": 100,
                    "adjusted_close": None,
                    "source": "yahoo_fallback",
                    "is_delisted_source": False,
                }
            ]
        )

        daily_prices, _symbol_master, _duplicate_report, bad_rows = normalize_price_frame([raw])

        self.assertTrue(daily_prices.empty)
        self.assertEqual(len(bad_rows), 1)
        self.assertIn("open < low", bad_rows.iloc[0]["bad_reason"])
        self.assertIn("close > high", bad_rows.iloc[0]["bad_reason"])

    def test_duckdb_file_normalize_matches_priority_and_bad_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stooq_path = root / "stooq.parquet"
            kaggle_path = root / "kaggle.parquet"
            daily_prices_path = root / "daily_prices.parquet"
            symbol_master_path = root / "symbol_master.parquet"
            duplicate_report_path = root / "duplicate_report.parquet"
            bad_rows_report_path = root / "bad_rows.parquet"

            pd.DataFrame(
                [
                    {
                        "date": "20200102",
                        "symbol": "aapl.us",
                        "vendor_symbol": "aapl.us",
                        "open": 100,
                        "high": 110,
                        "low": 99,
                        "close": 105,
                        "volume": 1000.4,
                        "adjusted_close": None,
                        "source": "stooq",
                        "is_delisted_source": False,
                    },
                    {
                        "date": "2020-01-02",
                        "symbol": "BAD",
                        "vendor_symbol": "BAD",
                        "open": 9,
                        "high": 10,
                        "low": 10,
                        "close": 11,
                        "volume": 100,
                        "adjusted_close": None,
                        "source": "stooq",
                        "is_delisted_source": False,
                    },
                ]
            ).to_parquet(stooq_path, index=False)
            pd.DataFrame(
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
                        "date": "2020-01-03",
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
            ).to_parquet(kaggle_path, index=False)

            normalize_prices(
                staging_paths=[stooq_path, kaggle_path],
                daily_prices_path=daily_prices_path,
                symbol_master_path=symbol_master_path,
                duplicate_report_path=duplicate_report_path,
                bad_rows_report_path=bad_rows_report_path,
            )

            daily_prices = pd.read_parquet(daily_prices_path)
            symbol_master = pd.read_parquet(symbol_master_path)
            duplicate_report = pd.read_parquet(duplicate_report_path)
            bad_rows = pd.read_parquet(bad_rows_report_path)

            aapl = daily_prices[daily_prices["symbol"] == "AAPL"].iloc[0]
            self.assertEqual(aapl["source"], "stooq")
            self.assertEqual(aapl["volume"], 1000)
            self.assertIn("OLDQ", set(daily_prices["symbol"]))
            self.assertTrue(
                bool(symbol_master.loc[symbol_master["symbol"] == "OLDQ", "has_delisted_source"].iloc[0])
            )
            self.assertEqual(len(duplicate_report), 1)
            self.assertEqual(duplicate_report.iloc[0]["selected_source"], "stooq")
            self.assertEqual(len(bad_rows), 1)
            self.assertIn("open < low", bad_rows.iloc[0]["bad_reason"])
            self.assertIn("close > high", bad_rows.iloc[0]["bad_reason"])


if __name__ == "__main__":
    unittest.main()

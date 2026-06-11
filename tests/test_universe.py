from __future__ import annotations

import unittest

import pandas as pd

from src import config
from src.universe.build_universe import build_universe_df
from src.universe.compute_liquidity import compute_liquidity_metrics_df


class UniverseTest(unittest.TestCase):
    def test_rolling_adv20_does_not_mix_symbols(self) -> None:
        dates = pd.date_range("2020-01-01", periods=20, freq="D")
        rows = []
        for date in dates:
            rows.append(
                {
                    "date": date.date(),
                    "symbol": "AAA",
                    "vendor_symbol": "AAA",
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 100,
                    "adjusted_close": None,
                    "source": "stooq",
                    "is_delisted_source": False,
                }
            )
            rows.append(
                {
                    "date": date.date(),
                    "symbol": "BBB",
                    "vendor_symbol": "BBB",
                    "open": 2,
                    "high": 2,
                    "low": 2,
                    "close": 2,
                    "volume": 10_000,
                    "adjusted_close": None,
                    "source": "stooq",
                    "is_delisted_source": False,
                }
            )

        liquidity = compute_liquidity_metrics_df(pd.DataFrame(rows))
        aaa_last = liquidity[liquidity["symbol"] == "AAA"].iloc[-1]
        bbb_last = liquidity[liquidity["symbol"] == "BBB"].iloc[-1]

        self.assertEqual(aaa_last["adv20"], 100)
        self.assertEqual(bbb_last["adv20"], 20_000)

    def test_traded_days_requires_positive_volume(self) -> None:
        dates = pd.date_range("2020-01-01", periods=20, freq="D")
        prices = pd.DataFrame(
            [
                {
                    "date": date.date(),
                    "symbol": "ZERO",
                    "vendor_symbol": "ZERO",
                    "open": 10,
                    "high": 10,
                    "low": 10,
                    "close": 10,
                    "volume": 0 if i < 10 else 100,
                    "adjusted_close": None,
                    "source": "stooq",
                    "is_delisted_source": False,
                }
                for i, date in enumerate(dates)
            ]
        )

        liquidity = compute_liquidity_metrics_df(prices)

        self.assertEqual(int(liquidity.iloc[-1]["traded_days_20"]), 10)

    def test_universe_exclusions(self) -> None:
        liquidity = pd.DataFrame(
            [
                {
                    "date": "2020-01-02",
                    "symbol": "GOOD",
                    "close": 10,
                    "volume": 200_000,
                    "dollar_volume": 2_000_000,
                    "adv20": 2_000_000,
                    "traded_days_20": 15,
                    "next_open": 10,
                    "has_next_open": True,
                },
                {
                    "date": "2020-01-02",
                    "symbol": "LOWPRICE",
                    "close": 0.99,
                    "volume": 200_000,
                    "dollar_volume": 2_000_000,
                    "adv20": 2_000_000,
                    "traded_days_20": 15,
                    "next_open": 1,
                    "has_next_open": True,
                },
                {
                    "date": "2020-01-02",
                    "symbol": "LOWADV",
                    "close": 10,
                    "volume": 10,
                    "dollar_volume": 100,
                    "adv20": 999_999,
                    "traded_days_20": 15,
                    "next_open": 10,
                    "has_next_open": True,
                },
                {
                    "date": "2020-01-02",
                    "symbol": "LOWDAYS",
                    "close": 10,
                    "volume": 200_000,
                    "dollar_volume": 2_000_000,
                    "adv20": 2_000_000,
                    "traded_days_20": 14,
                    "next_open": 10,
                    "has_next_open": True,
                },
                {
                    "date": "2020-01-02",
                    "symbol": "NONEXT",
                    "close": 10,
                    "volume": 200_000,
                    "dollar_volume": 2_000_000,
                    "adv20": 2_000_000,
                    "traded_days_20": 15,
                    "next_open": None,
                    "has_next_open": False,
                },
            ]
        )

        universe = build_universe_df(liquidity, universe_name=config.UNIVERSE_NAME)
        self.assertEqual(set(universe["symbol"]), {"GOOD"})


if __name__ == "__main__":
    unittest.main()

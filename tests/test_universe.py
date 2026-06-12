from __future__ import annotations

import unittest

import pandas as pd

from src import config
from src.universe.build_backtest_universe import (
    build_backtest_universe_df,
    build_security_events_df,
    build_terminal_events_df,
    select_delisting_events,
)
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

    def test_price_quality_suspect_rows_do_not_enter_universe(self) -> None:
        dates = pd.date_range("2020-01-01", periods=21, freq="D")
        prices = pd.DataFrame(
            [
                {
                    "date": date.date(),
                    "symbol": "SPLITBAD",
                    "vendor_symbol": "SPLITBAD",
                    "open": 2_000_000,
                    "high": 2_000_000,
                    "low": 2_000_000,
                    "close": 2_000_000,
                    "volume": 10_000,
                    "adjusted_close": 2_000_000,
                    "source": "yahoo_fallback",
                    "is_delisted_source": False,
                }
                for date in dates
            ]
        )

        liquidity = compute_liquidity_metrics_df(prices)
        universe = build_universe_df(liquidity, universe_name=config.UNIVERSE_NAME)

        self.assertTrue(liquidity["is_price_quality_suspect"].all())
        self.assertTrue(universe.empty)

    def test_backtest_universe_removes_dates_after_delisting_event(self) -> None:
        symbol_master = pd.DataFrame(
            [
                {
                    "symbol": "DEAD",
                    "vendor_symbol": "DEAD",
                    "first_date": "2020-01-01",
                    "last_date": "2020-01-04",
                    "source_list": "yahoo_delisted_probe",
                    "has_active_source": False,
                    "has_delisted_source": True,
                    "observation_count": 4,
                },
                {
                    "symbol": "LIVE",
                    "vendor_symbol": "LIVE",
                    "first_date": "2020-01-01",
                    "last_date": "2020-01-04",
                    "source_list": "yahoo_fallback",
                    "has_active_source": True,
                    "has_delisted_source": False,
                    "observation_count": 4,
                },
            ],
            columns=config.SYMBOL_MASTER_COLUMNS,
        )
        fmp = pd.DataFrame(
            [
                {
                    "symbol": "DEAD",
                    "companyName": "Dead Co.",
                    "exchange": "NASDAQ",
                    "ipoDate": "2019-01-01",
                    "delistedDate": "2020-01-02",
                    "source": "fmp",
                },
                {
                    "symbol": "LIVE",
                    "companyName": "Live Co.",
                    "exchange": "NYSE",
                    "ipoDate": "2019-01-01",
                    "delistedDate": "2020-01-02",
                    "source": "fmp",
                },
            ]
        )
        events = build_security_events_df(
            symbol_master=symbol_master,
            fmp_delisted_metadata=fmp,
            sec_delisted_candidates=pd.DataFrame(),
        )
        delistings = select_delisting_events(events)
        self.assertEqual(set(delistings["symbol"]), {"DEAD"})

        membership = pd.DataFrame(
            [
                {"date": "2020-01-01", "universe_name": config.UNIVERSE_NAME, "symbol": "DEAD", "reason": "base"},
                {"date": "2020-01-02", "universe_name": config.UNIVERSE_NAME, "symbol": "DEAD", "reason": "base"},
                {"date": "2020-01-03", "universe_name": config.UNIVERSE_NAME, "symbol": "DEAD", "reason": "base"},
                {"date": "2020-01-03", "universe_name": config.UNIVERSE_NAME, "symbol": "LIVE", "reason": "base"},
            ],
            columns=config.UNIVERSE_COLUMNS,
        )
        adjusted = build_backtest_universe_df(membership, delistings)

        dead_dates = adjusted[adjusted["symbol"] == "DEAD"]["date"].dt.strftime("%Y-%m-%d").tolist()
        self.assertEqual(dead_dates, ["2020-01-01", "2020-01-02"])
        self.assertIn("LIVE", set(adjusted["symbol"]))
        self.assertEqual(set(adjusted["universe_name"]), {config.BACKTEST_UNIVERSE_NAME})

    def test_terminal_events_use_last_close_without_zero_fill(self) -> None:
        delistings = pd.DataFrame(
            [
                {
                    "symbol": "DEAD",
                    "event_type": "delisting",
                    "event_date": "2020-01-03",
                    "source": "sec_form25_date_filed",
                    "source_event_id": "test",
                    "source_symbol": "DEAD",
                    "confidence": "proxy",
                    "notes": "test",
                }
            ],
            columns=config.SECURITY_EVENTS_COLUMNS,
        )
        daily_prices = pd.DataFrame(
            [
                {
                    "date": "2020-01-01",
                    "symbol": "DEAD",
                    "vendor_symbol": "DEAD",
                    "open": 10,
                    "high": 10,
                    "low": 10,
                    "close": 10,
                    "volume": 100,
                    "adjusted_close": None,
                    "source": "yahoo_delisted_probe",
                    "is_delisted_source": True,
                },
                {
                    "date": "2020-01-02",
                    "symbol": "DEAD",
                    "vendor_symbol": "DEAD",
                    "open": 5,
                    "high": 5,
                    "low": 5,
                    "close": 5,
                    "volume": 100,
                    "adjusted_close": None,
                    "source": "yahoo_delisted_probe",
                    "is_delisted_source": True,
                },
                {
                    "date": "2020-01-04",
                    "symbol": "DEAD",
                    "vendor_symbol": "DEAD",
                    "open": 1,
                    "high": 1,
                    "low": 1,
                    "close": 1,
                    "volume": 100,
                    "adjusted_close": None,
                    "source": "yahoo_delisted_probe",
                    "is_delisted_source": True,
                },
            ],
            columns=config.CANONICAL_PRICE_COLUMNS,
        )

        terminal = build_terminal_events_df(daily_prices, delistings)
        row = terminal.iloc[0]

        self.assertEqual(row["terminal_date"].strftime("%Y-%m-%d"), "2020-01-02")
        self.assertEqual(row["terminal_price"], 5)
        self.assertEqual(row["previous_close"], 10)
        self.assertAlmostEqual(row["terminal_return"], -0.5)
        self.assertTrue(row["has_terminal_price"])
        self.assertNotEqual(row["terminal_price"], 0)


if __name__ == "__main__":
    unittest.main()

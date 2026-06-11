from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from src import config
from src.db.build_duckdb import build_duckdb
from src.db.query_examples import get_prices, get_universe


class DuckDBTest(unittest.TestCase):
    def test_duckdb_can_query_one_date_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daily_prices_path = root / "daily_prices.parquet"
            symbol_master_path = root / "symbol_master.parquet"
            liquidity_path = root / "liquidity_metrics.parquet"
            membership_path = root / "universe_membership.parquet"
            stats_path = root / "universe_stats.parquet"
            db_path = root / "pit_market.duckdb"

            pd.DataFrame(
                [
                    {
                        "date": date(2020, 1, 2),
                        "symbol": "GOOD",
                        "vendor_symbol": "GOOD",
                        "open": 10.0,
                        "high": 11.0,
                        "low": 9.0,
                        "close": 10.5,
                        "volume": 200_000,
                        "adjusted_close": None,
                        "source": "stooq",
                        "is_delisted_source": False,
                    }
                ],
                columns=config.CANONICAL_PRICE_COLUMNS,
            ).to_parquet(daily_prices_path, index=False)
            pd.DataFrame(
                [
                    {
                        "symbol": "GOOD",
                        "vendor_symbol": "GOOD",
                        "first_date": date(2020, 1, 2),
                        "last_date": date(2020, 1, 2),
                        "source_list": "stooq",
                        "has_active_source": True,
                        "has_delisted_source": False,
                        "observation_count": 1,
                    }
                ],
                columns=config.SYMBOL_MASTER_COLUMNS,
            ).to_parquet(symbol_master_path, index=False)
            pd.DataFrame(
                [
                    {
                        "date": date(2020, 1, 2),
                        "symbol": "GOOD",
                        "close": 10.5,
                        "volume": 200_000,
                        "dollar_volume": 2_100_000,
                        "adv20": 2_100_000,
                        "traded_days_20": 15,
                        "next_open": 10.7,
                        "has_next_open": True,
                    }
                ],
                columns=config.LIQUIDITY_COLUMNS,
            ).to_parquet(liquidity_path, index=False)
            pd.DataFrame(
                [
                    {
                        "date": date(2020, 1, 2),
                        "universe_name": config.UNIVERSE_NAME,
                        "symbol": "GOOD",
                        "reason": "test",
                    }
                ],
                columns=config.UNIVERSE_COLUMNS,
            ).to_parquet(membership_path, index=False)
            pd.DataFrame(
                [
                    {
                        "date": date(2020, 1, 2),
                        "universe_name": config.UNIVERSE_NAME,
                        "symbol_count": 1,
                        "median_close": 10.5,
                        "median_adv20": 2_100_000,
                        "total_dollar_volume": 2_100_000,
                        "delisted_source_count": 0,
                    }
                ],
                columns=config.UNIVERSE_STATS_COLUMNS,
            ).to_parquet(stats_path, index=False)

            build_duckdb(
                db_path=db_path,
                daily_prices_path=daily_prices_path,
                symbol_master_path=symbol_master_path,
                liquidity_metrics_path=liquidity_path,
                universe_membership_path=membership_path,
                universe_stats_path=stats_path,
            )

            self.assertEqual(get_universe("2020-01-02", db_path=db_path), ["GOOD"])
            prices = get_prices("2020-01-02", ["GOOD"], db_path=db_path)
            self.assertEqual(len(prices), 1)
            self.assertEqual(prices.iloc[0]["symbol"], "GOOD")


if __name__ == "__main__":
    unittest.main()

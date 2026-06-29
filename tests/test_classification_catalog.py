from __future__ import annotations

import unittest

import pandas as pd

from src.normalize.build_classification_catalog import build_security_classification_catalog_df


class SecurityClassificationCatalogTest(unittest.TestCase):
    def test_catalog_contains_only_non_sic_and_selected_etf_labels(self) -> None:
        security_master = pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "asset_type": "stock",
                    "is_etf": False,
                    "security_name": "Apple Inc.",
                    "sector": "Technology",
                    "industry": "Electronic Computers",
                    "sector_source": "sec_sic",
                },
                {
                    "symbol": "AFCG",
                    "asset_type": "stock",
                    "is_etf": False,
                    "security_name": "Advanced Flower Capital Inc.",
                    "sector": "Real Estate",
                    "industry": "REIT - Specialty",
                    "sector_source": "fmp_profile",
                },
                {
                    "symbol": "XLK",
                    "asset_type": "etf",
                    "is_etf": True,
                    "security_name": "State Street Technology Select Sector SPDR ETF",
                    "sector": pd.NA,
                    "industry": pd.NA,
                    "sector_source": pd.NA,
                },
                {
                    "symbol": "SPY",
                    "asset_type": "etf",
                    "is_etf": True,
                    "security_name": "State Street SPDR S&P 500 ETF Trust",
                    "sector": pd.NA,
                    "industry": pd.NA,
                    "sector_source": pd.NA,
                },
                {
                    "symbol": "TQQQ",
                    "asset_type": "etf",
                    "is_etf": True,
                    "security_name": "ProShares UltraPro QQQ",
                    "sector": pd.NA,
                    "industry": pd.NA,
                    "sector_source": pd.NA,
                },
                {
                    "symbol": "NEWF",
                    "asset_type": "etf",
                    "is_etf": True,
                    "security_name": "New Fund ETF",
                    "sector": pd.NA,
                    "industry": pd.NA,
                    "sector_source": pd.NA,
                },
            ]
        )
        symbol_master = pd.DataFrame(
            [
                {"symbol": "AAPL", "first_date": "2010-01-04", "last_date": "2026-06-18"},
                {"symbol": "AFCG", "first_date": "2021-01-04", "last_date": "2026-06-18"},
                {"symbol": "XLK", "first_date": "2010-01-04", "last_date": "2026-06-18"},
                {"symbol": "SPY", "first_date": "2010-01-04", "last_date": "2026-06-18"},
                {"symbol": "TQQQ", "first_date": "2010-02-11", "last_date": "2026-06-18"},
                {"symbol": "NEWF", "first_date": "2026-01-02", "last_date": "2026-06-18"},
            ]
        )
        liquidity_metrics = pd.DataFrame(
            [
                {"date": "2026-06-18", "symbol": "XLK", "quality_adv20": 100_000_000, "quality_traded_days_20": 20},
                {"date": "2026-06-18", "symbol": "SPY", "quality_adv20": 1_000_000_000, "quality_traded_days_20": 20},
                {"date": "2026-06-18", "symbol": "TQQQ", "quality_adv20": 500_000_000, "quality_traded_days_20": 20},
                {"date": "2026-06-18", "symbol": "NEWF", "quality_adv20": 500_000_000, "quality_traded_days_20": 20},
            ]
        )

        catalog = build_security_classification_catalog_df(security_master, symbol_master, liquidity_metrics)
        by_symbol = catalog.set_index("symbol")

        self.assertNotIn("AAPL", by_symbol.index)
        self.assertEqual(by_symbol.loc["AFCG", "label_source"], "fmp_profile")
        self.assertEqual(by_symbol.loc["XLK", "sector"], "Technology")
        self.assertEqual(by_symbol.loc["XLK", "category"], "sector_etf")
        self.assertEqual(by_symbol.loc["SPY", "category"], "broad_us_equity")
        self.assertTrue(pd.isna(by_symbol.loc["SPY", "sector"]))
        self.assertEqual(by_symbol.loc["TQQQ", "category"], "nasdaq_100")
        self.assertTrue(bool(by_symbol.loc["TQQQ", "is_leveraged_or_inverse"]))
        self.assertNotIn("NEWF", by_symbol.index)
        self.assertEqual(catalog["catalog_hash"].nunique(), 1)


if __name__ == "__main__":
    unittest.main()

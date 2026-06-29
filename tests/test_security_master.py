from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from src.normalize.build_security_master import build_security_master_df


class SecurityMasterTest(unittest.TestCase):
    @patch("src.normalize.build_security_master._read_sec_company_metadata")
    @patch("src.normalize.build_security_master._read_fmp_profile_metadata")
    @patch("src.normalize.build_security_master._read_fmp_delisted_metadata")
    @patch("src.normalize.build_security_master._read_yahoo_metadata")
    @patch("src.normalize.build_security_master._read_active_listing_metadata")
    def test_builds_asset_type_and_sector(
        self,
        active_mock,
        yahoo_mock,
        fmp_delisted_mock,
        fmp_profile_mock,
        sec_company_mock,
    ) -> None:
        symbol_master = pd.DataFrame({"symbol": ["AAPL", "SPY", "OLD"]})
        active_mock.return_value = pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "active_security_name": "Apple Inc. Common Stock",
                    "active_exchange": "Q",
                    "active_is_etf": False,
                },
                {
                    "symbol": "SPY",
                    "active_security_name": "SPDR S&P 500 ETF",
                    "active_exchange": "P",
                    "active_is_etf": True,
                },
            ]
        )
        yahoo_mock.return_value = pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "yahoo_instrument_type": "EQUITY",
                    "yahoo_security_name": "Apple Inc.",
                    "yahoo_exchange": "NasdaqGS",
                    "yahoo_currency": "USD",
                },
                {
                    "symbol": "SPY",
                    "yahoo_instrument_type": "ETF",
                    "yahoo_security_name": "SPDR S&P 500 ETF Trust",
                    "yahoo_exchange": "NYSEArca",
                    "yahoo_currency": "USD",
                },
            ]
        )
        fmp_delisted_mock.return_value = pd.DataFrame(
            [{"symbol": "OLD", "fmp_delisted_name": "Old Co.", "fmp_delisted_exchange": "NASDAQ"}]
        )
        fmp_profile_mock.return_value = pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "fmp_profile_name": "Apple Inc.",
                    "fmp_profile_exchange": "NASDAQ",
                    "fmp_profile_currency": "USD",
                    "sector": "Vendor Technology",
                    "industry": "Vendor Consumer Electronics",
                    "fmp_is_etf": False,
                    "fmp_is_fund": False,
                }
            ]
        )
        sec_company_mock.return_value = pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "sec_cik": 320193,
                    "sec_company_name": "Apple Inc SEC",
                    "sec_exchange": "NASDAQ",
                    "sic": 3571,
                    "sic_description": "Electronic Computers",
                    "sic_sector": "SEC Technology",
                },
                {
                    "symbol": "OLD",
                    "sec_cik": 123456,
                    "sec_company_name": "Old Co SEC",
                    "sec_exchange": "NYSE",
                    "sic": 2834,
                    "sic_description": "Pharmaceutical Preparations",
                    "sic_sector": "Healthcare",
                }
            ]
        )

        result = build_security_master_df(symbol_master)

        by_symbol = result.set_index("symbol")
        self.assertEqual(by_symbol.loc["AAPL", "asset_type"], "stock")
        self.assertEqual(by_symbol.loc["AAPL", "sector"], "SEC Technology")
        self.assertEqual(by_symbol.loc["AAPL", "industry"], "Electronic Computers")
        self.assertEqual(by_symbol.loc["AAPL", "sector_source"], "sec_sic")
        self.assertEqual(by_symbol.loc["SPY", "asset_type"], "etf")
        self.assertTrue(bool(by_symbol.loc["SPY", "is_etf"]))
        self.assertEqual(by_symbol.loc["OLD", "security_name"], "Old Co.")
        self.assertEqual(by_symbol.loc["OLD", "sector"], "Healthcare")
        self.assertEqual(by_symbol.loc["OLD", "industry"], "Pharmaceutical Preparations")
        self.assertEqual(by_symbol.loc["OLD", "sector_source"], "sec_sic")


if __name__ == "__main__":
    unittest.main()

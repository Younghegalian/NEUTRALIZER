from __future__ import annotations

import unittest

from src.collectors.yahoo_fallback_downloader import _parse_chart_payload


class YahooParserTest(unittest.TestCase):
    def test_rejects_non_us_equity_metadata(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "symbol": "VCI",
                            "exchangeName": "YHD",
                            "instrumentType": "MUTUALFUND",
                            "currency": None,
                        },
                        "timestamp": [1577836800],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [1],
                                    "high": [1],
                                    "low": [1],
                                    "close": [1],
                                    "volume": [100],
                                }
                            ],
                            "adjclose": [{"adjclose": [1]}],
                        },
                    }
                ]
            }
        }

        parsed = _parse_chart_payload("VCI", payload, internal_symbol="VCI")

        self.assertTrue(parsed.empty)

    def test_accepts_us_equity_metadata(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "symbol": "AAPL",
                            "exchangeName": "NMS",
                            "instrumentType": "EQUITY",
                            "currency": "USD",
                        },
                        "timestamp": [1577836800],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [100],
                                    "high": [101],
                                    "low": [99],
                                    "close": [100],
                                    "volume": [1000],
                                }
                            ],
                            "adjclose": [{"adjclose": [100]}],
                        },
                    }
                ]
            }
        }

        parsed = _parse_chart_payload("AAPL", payload, internal_symbol="AAPL")

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed.iloc[0]["symbol"], "AAPL")


if __name__ == "__main__":
    unittest.main()

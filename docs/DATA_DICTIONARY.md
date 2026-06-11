# Data Dictionary

## `daily_prices`

| Column | Type | Description |
| --- | --- | --- |
| `date` | DATE | Trading date. |
| `symbol` | TEXT | Internal normalized symbol. |
| `vendor_symbol` | TEXT | Source/vendor symbol. |
| `open` | DOUBLE | Raw daily open. |
| `high` | DOUBLE | Raw daily high. |
| `low` | DOUBLE | Raw daily low. |
| `close` | DOUBLE | Raw daily close. |
| `volume` | BIGINT | Daily share volume. |
| `adjusted_close` | DOUBLE | Adjusted close when provided by source. |
| `source` | TEXT | Data source. |
| `is_delisted_source` | BOOLEAN | True for delisted-focused sources. |

## `symbol_master`

| Column | Description |
| --- | --- |
| `symbol` | Internal symbol. |
| `vendor_symbol` | Vendor symbols seen for the security. |
| `first_date` | First price date. |
| `last_date` | Last price date. |
| `source_list` | Comma-separated sources. |
| `has_active_source` | Has active-source coverage. |
| `has_delisted_source` | Has delisted-source coverage. |
| `observation_count` | Canonical daily rows. |

## `liquidity_metrics`

| Column | Description |
| --- | --- |
| `dollar_volume` | `close * volume`. |
| `adv20` | Symbol-specific rolling 20-day mean dollar volume. |
| `traded_days_20` | Non-null volume days in rolling 20-day window. |
| `next_open` | Next available open for the same symbol. |
| `has_next_open` | True when `next_open` is available. |

## `universe_membership`

| Column | Description |
| --- | --- |
| `date` | Universe date. |
| `universe_name` | Universe identifier. |
| `symbol` | Included symbol. |
| `reason` | Eligibility rule summary. |

## `universe_stats`

Daily sanity table with symbol counts, median close, median ADV20, total dollar volume, and delisted-source count.


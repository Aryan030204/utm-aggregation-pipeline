import unittest
from collections import defaultdict
from decimal import Decimal

from app.services.query_builder import get_dimension_columns
from app.services.utm_merge_service import UtmMergeService
from app.sql.setup import DAILY_TABLES, HOURLY_TABLES

UTM = ("utm_source", "utm_medium", "utm_campaign")
COUNT_COLUMNS = ("orders", "prepaid_orders", "cod_orders", "ppcod_orders", "cancelled_orders", "refunded_orders")


def raw_row(order_id, hour, source, medium, campaign, price, payment, cancelled=0, refunded=0):
    return {
        "order_id": order_id, "metric_hour": hour,
        "utm_source": source, "utm_medium": medium, "utm_campaign": campaign,
        "total_price": Decimal(price), "payment_type": payment,
        "is_cancelled": cancelled, "is_refunded": refunded,
    }


# One row per order line item, like shopify_orders: o3 and o6 span two rows.
RAW_ROWS = [
    raw_row("o1", 9, "google", "cpc", "spring", "100.10", "PREPAID"),
    raw_row("o2", 9, "google", "cpc", "spring", "50.25", "COD", cancelled=1),
    raw_row("o3", 9, "google", "cpc", "summer", "70.00", "PPCOD"),
    raw_row("o3", 9, "google", "cpc", "summer", "70.00", "PPCOD"),
    raw_row("o4", 10, "google", "organic", "spring", "10.05", "PREPAID", refunded=1),
    raw_row("o5", 10, "direct", "Unknown", "Unknown", "20.00", "COD"),
    raw_row("o6", 23, "facebook", "paid", "spring", "30.00", "PREPAID"),
    raw_row("o6", 23, "facebook", "paid", "spring", "30.00", "PREPAID"),
    raw_row("o7", 23, "facebook", "paid", "summer", "40.40", "COD", cancelled=1, refunded=1),
]


def aggregate(rows, group_fields):
    """What the old per-table SQL computed: group raw rows straight to the table's grain."""
    groups = defaultdict(lambda: {"order_ids": set(), "sales": Decimal("0"), **{c: 0 for c in COUNT_COLUMNS}})
    for row in rows:
        key = tuple(row[f] for f in group_fields)
        g = groups[key]
        g["order_ids"].add(row["order_id"])
        g["sales"] += row["total_price"]
        g[f"{row['payment_type'].lower()}_orders"] += 1
        g["cancelled_orders"] += row["is_cancelled"]
        g["refunded_orders"] += row["is_refunded"]
    result = {}
    for key, g in groups.items():
        g["orders"] = len(g["order_ids"])
        result[key] = g
    return result


def finest_rows():
    """What the single per-date SQL query returns."""
    finest = aggregate(RAW_ROWS, ("metric_hour",) + UTM)
    rows = []
    for key, g in finest.items():
        row = {"metric_date": "2026-09-20", "metric_hour": key[0], **dict(zip(UTM, key[1:]))}
        row.update({c: g[c] for c in COUNT_COLUMNS})
        row["sales"] = g["sales"]
        rows.append(row)
    return rows


class RollupOrdersTests(unittest.TestCase):
    def test_rollup_matches_direct_aggregation_for_all_14_tables(self):
        finest = finest_rows()
        tables = [(t, False) for t in DAILY_TABLES] + [(t, True) for t in HOURLY_TABLES]
        self.assertEqual(len(tables), 14)

        for table_name, is_hourly in tables:
            with self.subTest(table=table_name):
                dims = get_dimension_columns(table_name, is_hourly)
                fields = [d for d in dims if d != "metric_date"]
                expected = aggregate(RAW_ROWS, fields)

                rolled = UtmMergeService.rollup_orders(finest, dims)
                actual = {tuple(r[f] for f in fields): r for r in rolled}

                self.assertEqual(set(actual), set(expected))
                for key, exp in expected.items():
                    for column in COUNT_COLUMNS:
                        self.assertEqual(actual[key][column], exp[column], f"{table_name} {key} {column}")
                    self.assertEqual(actual[key]["sales"], exp["sales"], f"{table_name} {key} sales")

    def test_rollup_of_empty_input_is_empty(self):
        self.assertEqual(UtmMergeService.rollup_orders([], ["metric_date", "utm_source"]), [])


class MergeTests(unittest.TestCase):
    def test_merge_collapses_sessions_and_computes_rates_with_decimal(self):
        dims = ["metric_date", "utm_source"]
        orders = UtmMergeService.rollup_orders(finest_rows(), dims)
        sessions = [
            {"hour": None, "utm_source": "google", "utm_medium": "cpc", "utm_campaign": "spring", "sessions": 30, "atc_sessions": 4},
            {"hour": None, "utm_source": "google", "utm_medium": "organic", "utm_campaign": "x", "sessions": 10, "atc_sessions": 1},
            {"hour": None, "utm_source": "tiktok", "utm_medium": "paid", "utm_campaign": "x", "sessions": 5, "atc_sessions": 0},
        ]
        rows = {r["utm_source"]: r for r in UtmMergeService.merge(dims, "2026-09-20", orders, sessions)}

        google = rows["google"]
        self.assertEqual(google["sessions"], 40)
        self.assertEqual(google["atc_sessions"], 5)
        self.assertEqual(google["orders"], 4)
        # o3 has two rows and SUM(total_price) counts per row (existing behavior, preserved).
        self.assertEqual(google["sales"], Decimal("300.40"))
        self.assertEqual(google["average_order_value"], Decimal("75.10"))
        self.assertAlmostEqual(google["conversion_rate"], 0.1)
        self.assertAlmostEqual(google["cancellation_rate"], 0.25)
        self.assertAlmostEqual(google["refund_rate"], 0.25)

        # Sessions with no orders, and orders with no sessions, both survive the merge.
        self.assertEqual(rows["tiktok"]["orders"], 0)
        self.assertEqual(rows["tiktok"]["average_order_value"], Decimal("0.00"))
        self.assertEqual(rows["facebook"]["sessions"], 0)
        self.assertEqual(rows["facebook"]["conversion_rate"], 0.0)

    def test_hourly_merge_keys_sessions_by_hour(self):
        dims = ["metric_date", "metric_hour", "utm_source"]
        orders = UtmMergeService.rollup_orders(finest_rows(), dims)
        sessions = [{"hour": 9, "utm_source": "google", "utm_medium": "cpc", "utm_campaign": "spring", "sessions": 12, "atc_sessions": 2}]
        rows = {(r["metric_hour"], r["utm_source"]): r for r in UtmMergeService.merge(dims, "2026-09-20", orders, sessions)}

        self.assertEqual(rows[(9, "google")]["sessions"], 12)
        self.assertEqual(rows[(9, "google")]["orders"], 3)
        self.assertEqual(rows[(10, "google")]["sessions"], 0)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import date, timedelta

from history_data import SPECS, build_history, make_series


class HistoryTests(unittest.TestCase):
    def test_year_over_year_matches_calendar_month(self):
        rows = [{"date": "2025-09-01", "value": "100"},
                {"date": "2026-09-01", "value": "103"}]
        series = make_series(rows, SPECS["core_pce"], date(2026, 11, 4))
        self.assertEqual(series["points"][-1]["value"], 3)

    def test_missing_month_does_not_use_another_month(self):
        rows = [{"date": "2026-07-01", "value": "100"},
                {"date": "2026-09-01", "value": "105"}]
        series = make_series(rows, SPECS["retail_sales"], date(2026, 11, 4))
        self.assertIsNone(series["points"][-1]["value"])

    def test_nonfarm_uses_change_in_thousands(self):
        rows = [{"date": "2026-08-01", "value": "159015"},
                {"date": "2026-09-01", "value": "159044"}]
        series = make_series(rows, SPECS["nonfarm_payrolls"], date(2026, 11, 4))
        self.assertEqual(series["points"][-1]["value"], 29)

    def test_three_month_annualization(self):
        rows = [{"date": "2026-06-01", "value": "100"},
                {"date": "2026-09-01", "value": "101"}]
        value = make_series(rows, SPECS["core_pce_3m"], date(2026, 11, 4))["points"][-1]["value"]
        self.assertAlmostEqual(value, (1.01 ** 4 - 1) * 100, places=4)

    def test_assets_units_and_four_week_change(self):
        rows = [{"date": "2026-09-30", "value": "6743396"},
                {"date": "2026-10-28", "value": "6746000"}]
        self.assertEqual(make_series(rows, SPECS["fed_assets"], date(2026, 11, 4))["points"][-1]["value"], 6.746)
        self.assertEqual(make_series(rows, SPECS["fed_assets_month_change"], date(2026, 11, 4))["points"][-1]["value"], 26.04)

    def test_full_year_ends_at_latest_month_not_fetch_date(self):
        rows = [{"date": f"2025-{month:02}-01", "value": "100"} for month in range(1, 13)]
        rows += [{"date": f"2026-{month:02}-01", "value": "103"} for month in range(1, 10)]
        points = make_series(rows, SPECS["core_pce"], date(2026, 11, 4))["points"]
        self.assertEqual(points[0]["date"], "2025-09-01")
        self.assertEqual(points[-1]["date"], "2026-09-01")
        self.assertEqual(len(points), 13)

    def test_ma200_requires_200_real_observations(self):
        rows = [{"date": (date(2026, 1, 1) + timedelta(days=i)).isoformat(), "value": str(i+1)} for i in range(201)]
        rows.append({"date": "2026-12-01", "value": "9999"})  # future data excluded
        series = make_series(rows, SPECS["sp500_trend"], date(2026, 11, 4))
        self.assertIsNone(series["points"][198]["ma200"])
        self.assertEqual(series["points"][199]["ma200"], 100.5)
        self.assertEqual(series["points"][200]["ma200"], 101.5)

    def test_failures_keep_old_data_and_mark_failure(self):
        old = {"vix": {"as_of": "2026-10-01", "points": [{"date": "2026-10-01", "value": 20}]}}
        def fail(*args):
            raise RuntimeError("unavailable")
        result = build_history(fail, old, date(2026, 11, 4))
        self.assertEqual(result["vix"]["as_of"], "2026-10-01")
        self.assertEqual(result["vix"]["fetch_status"], "failed")
        self.assertEqual(result["rate"]["points"], [])
        self.assertNotIn("fetch_status", old["vix"])

    def test_missing_values_are_never_zero(self):
        rows = [{"date":"2026-10-01","value":"."},
                {"date":"2026-10-02","value":"nan"},
                {"date":"2026-10-03","value":"inf"},
                {"date":"2026-10-04","value":"21.15"}]
        series = make_series(rows, SPECS["vix"], date(2026, 11, 4))
        self.assertEqual(series["points"], [{"date":"2026-10-04","value":21.15}])


class SnapshotCalendarTests(unittest.TestCase):
    def test_missing_month_does_not_shift_annual_comparison(self):
        from unittest.mock import patch
        import update_data
        rows = [{"date":f"2025-{month:02}-01", "value":"100"} for month in range(1,13) if month != 10]
        rows += [{"date":f"2026-{month:02}-01", "value":"110"} for month in range(1,10)]
        with patch.object(update_data, "fetch_observations", return_value=list(reversed(rows))):
            snapshot = update_data.fetch_growth_snapshot("CPIAUCSL")
        self.assertEqual(snapshot["yoy"], 10)
        self.assertEqual(snapshot["prev_yoy"], 10)

    def test_monthly_snapshot_reports_missing_previous_month(self):
        from unittest.mock import patch
        import update_data
        rows = [{"date":"2026-09-01","value":"110"},{"date":"2026-07-01","value":"100"}]
        with patch.object(update_data, "fetch_observations", return_value=rows):
            self.assertIsNone(update_data.fetch_growth_snapshot("RSAFS")["mom"])
            self.assertIsNone(update_data.fetch_payroll_snapshot("PAYEMS")["current"])


if __name__ == "__main__":
    unittest.main()

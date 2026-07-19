"""Tests for pipeline resolve, dashboard, and actions."""

from __future__ import annotations

import unittest

from home_care_target.actions import build_action_plans, public_action_summary
from home_care_target.dashboard import build_dashboard, public_dashboard
from home_care_target.pipeline import analyze_clinic, resolve_clinic


class TestPipeline(unittest.TestCase):
    def test_resolve_alias(self):
        p = resolve_clinic("ひばりが丘")
        self.assertIn("ひばりが丘", p.name)

    def test_resolve_urawa(self):
        p = resolve_clinic("浦和")
        self.assertAlmostEqual(p.lat, 35.8788, places=3)

    def test_analyze_one_shot(self):
        a = analyze_clinic(resolve_clinic("市川"))
        self.assertGreater(a.kpi_target_home, 0)
        self.assertGreater(a.capacity_cap_home, 0)
        self.assertGreater(a.demand_home_adjusted, 0)
        row = a.management_row()
        self.assertIn("acquisition_kpi_home", row)
        self.assertIn("capacity_cap_home", row)


class TestDashboardAndActions(unittest.TestCase):
    def test_dashboard_triad(self):
        dash = build_dashboard()
        self.assertGreaterEqual(dash["n_clinics"], 13)
        pub = public_dashboard(dash)
        # public may keep attainment ratio but not raw actuals keys required
        for r in pub["rows"]:
            self.assertIn("acquisition_kpi_home", r)
            self.assertIn("capacity_cap_home", r)
            self.assertNotIn("actual_home", r)

    def test_actions_priority_orders_underperformers(self):
        plans = build_action_plans(months=12)
        self.assertEqual(plans[0].priority, 1)
        # 浦和 should be high priority (under floor)
        aliases = [p.alias for p in plans[:3]]
        self.assertTrue(any(a in ("浦和", "市川") for a in aliases))
        pub = public_action_summary(plans)
        self.assertNotIn("actual_home", str(pub))


if __name__ == "__main__":
    unittest.main()

"""Unit tests for API endpoints and responses."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from fastapi import HTTPException
from app.main import (
    get_dashboard,
    get_recommendations,
    get_resources,
    get_scenarios,
    health_check,
)


class TestAPIEndpoints(unittest.TestCase):
    def test_health_check(self):
        res = health_check()
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["service"], "aws-cloud-cost-optimiser")

    def test_list_scenarios(self):
        scenarios = get_scenarios()
        self.assertEqual(len(scenarios), 4)
        ids = [s.id for s in scenarios]
        self.assertIn("high-cost-waste", ids)
        self.assertIn("healthy-environment", ids)
        self.assertIn("mixed-environment", ids)
        self.assertIn("insufficient-data", ids)

    def test_dashboard_high_cost_waste(self):
        dashboard = get_dashboard(scenario="high-cost-waste")
        self.assertEqual(dashboard.metadata.scenario_id, "high-cost-waste")
        self.assertTrue(dashboard.metadata.is_read_only)
        self.assertTrue(dashboard.metadata.is_simulated)
        self.assertGreater(dashboard.summary.monthly_cost.value, 0)
        self.assertGreater(dashboard.summary.potential_savings.value, 0)
        self.assertGreater(len(dashboard.priority_findings), 0)

    def test_dashboard_healthy_environment(self):
        dashboard = get_dashboard(scenario="healthy-environment")
        self.assertEqual(len(dashboard.priority_findings), 0)
        self.assertEqual(dashboard.summary.potential_savings.value, 0.0)

    def test_dashboard_insufficient_data(self):
        dashboard = get_dashboard(scenario="insufficient-data")
        self.assertTrue(dashboard.metadata.data_limitations_active)
        self.assertIsNotNone(dashboard.metadata.data_limitations_notice)

    def test_dashboard_invalid_scenario_raises_400(self):
        with self.assertRaises(HTTPException) as ctx:
            get_dashboard(scenario="invalid-scenario-id")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid scenario ID", ctx.exception.detail)

    def test_get_resources(self):
        resources = get_resources(scenario="high-cost-waste")
        self.assertGreater(len(resources), 0)

    def test_get_recommendations(self):
        recs = get_recommendations(scenario="high-cost-waste")
        self.assertGreater(len(recs), 0)


if __name__ == "__main__":
    unittest.main()

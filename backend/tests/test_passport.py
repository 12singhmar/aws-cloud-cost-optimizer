"""Unit tests for Change Passport generation, attestation, and What-If simulation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from app.main import (
    AttestRequest,
    SimulateRequest,
    UndoSimulateRequest,
    get_change_passport,
    get_dashboard,
    simulate_change,
    toggle_attestation,
    undo_simulation,
)


class TestChangePassport(unittest.TestCase):
    def setUp(self):
        self.scenario = "high-cost-waste"
        self.rec_id = "rec-ebs-vol-0a7f82c9e4b1a3d5e"

    def test_get_ebs_change_passport(self):
        passport = get_change_passport(self.rec_id, scenario=self.scenario)

        self.assertEqual(passport.resource_id, "vol-0a7f82c9e4b1a3d5e")
        self.assertEqual(passport.resource_type, "EBS")
        self.assertEqual(passport.region, "us-east-1")

        fin = passport.financial_impact
        self.assertEqual(fin.estimated_avoidable_monthly_cost, 40.00)
        self.assertEqual(fin.annualized_avoidable_cost, 480.00)
        self.assertEqual(fin.snapshot_cost_monthly, 12.50)
        self.assertEqual(fin.net_projected_savings_monthly, 27.50)
        self.assertEqual(fin.net_projected_savings_annual, 330.00)
        self.assertIn("Unavailable", fin.realized_savings_status)

        reviews = passport.departmental_reviews
        self.assertIn("Finance", reviews)
        self.assertIn("Engineering", reviews)
        self.assertIn("Security", reviews)
        self.assertIn("Operations", reviews)
        self.assertEqual(reviews["Finance"].status.value, "PASSED")
        self.assertEqual(reviews["Operations"].status.value, "PASSED")

        self.assertGreater(len(passport.validation_checklist), 0)
        self.assertGreater(len(passport.proposed_actions), 0)

    def test_simulation_workflow_and_undo(self):
        initial_dash = get_dashboard(scenario=self.scenario)
        initial_cost = initial_dash.summary.monthly_cost.value

        sim_req = SimulateRequest(
            scenario_id=self.scenario,
            recommendation_id=self.rec_id,
            action_id="snapshot_and_delete",
        )
        sim = simulate_change(sim_req)
        self.assertTrue(sim.is_simulated)
        self.assertEqual(sim.monthly_savings_delta, 27.50)
        self.assertIn("snap-sim-0a7f82c9", sim.simulated_resource_state)

        updated_dash = get_dashboard(scenario=self.scenario)
        updated_cost = updated_dash.summary.monthly_cost.value
        self.assertAlmostEqual(updated_cost, initial_cost - 27.50, places=2)

        passport = get_change_passport(self.rec_id, scenario=self.scenario)
        self.assertEqual(passport.decision_status.value, "Simulated")
        self.assertIsNotNone(passport.simulation_result)

        undo_req = UndoSimulateRequest(
            scenario_id=self.scenario,
            recommendation_id=self.rec_id,
        )
        undo_res = undo_simulation(undo_req)
        self.assertEqual(undo_res["status"], "ok")

        restored_dash = get_dashboard(scenario=self.scenario)
        restored_cost = restored_dash.summary.monthly_cost.value
        self.assertEqual(restored_cost, initial_cost)

    def test_attestation_toggle(self):
        attest_req = AttestRequest(
            scenario_id=self.scenario,
            check_id="eng-1",
            attested=True,
        )
        attest_res = toggle_attestation(attest_req)
        self.assertEqual(attest_res["status"], "ok")

        passport = get_change_passport(self.rec_id, scenario=self.scenario)
        eng_checks = passport.departmental_reviews["Engineering"].checks
        check_eng1 = next(c for c in eng_checks if c.id == "eng-1")
        self.assertTrue(check_eng1.user_attested)


if __name__ == "__main__":
    unittest.main()

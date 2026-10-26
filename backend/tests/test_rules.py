"""Unit tests for optimization rules covering positive, negative, and boundary conditions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from app.analysis.rules import (
    EBSUnattachedRule,
    EC2IdleRule,
    EC2RightsizingRule,
    S3LifecycleRule,
)
from app.models import Resource, ResourceMetrics, ResourceType


class TestOptimizationRules(unittest.TestCase):
    def setUp(self):
        self.rightsizing_rule = EC2RightsizingRule()
        self.idle_rule = EC2IdleRule()
        self.ebs_rule = EBSUnattachedRule()
        self.s3_rule = S3LifecycleRule()

    def test_rightsizing_triggers_on_low_cpu_utilization(self):
        res = Resource(
            id="i-test-rightsize",
            name="test-web",
            resource_type=ResourceType.EC2,
            region="us-east-1",
            status="running",
            monthly_cost=122.40,
            details={"instance_type": "c5.xlarge", "recommended_type": "c5.large", "recommended_cost": 61.20},
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=14,
            avg_cpu_percent=5.5,
            peak_cpu_percent=18.0,
            network_in_bytes_sec=150000.0,
            has_sufficient_data=True,
        )
        rec = self.rightsizing_rule.evaluate(res, metrics)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.priority, "HIGH")
        self.assertEqual(rec.estimated_savings, 61.20)
        self.assertEqual(rec.confidence, 90)

    def test_rightsizing_does_not_trigger_when_cpu_is_healthy(self):
        res = Resource(
            id="i-test-healthy",
            name="healthy-web",
            resource_type=ResourceType.EC2,
            region="us-east-1",
            status="running",
            monthly_cost=122.40,
            details={"instance_type": "c5.xlarge"},
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=14,
            avg_cpu_percent=25.0,
            peak_cpu_percent=65.0,
            network_in_bytes_sec=200000.0,
            has_sufficient_data=True,
        )
        rec = self.rightsizing_rule.evaluate(res, metrics)
        self.assertIsNone(rec)

    def test_rightsizing_does_not_trigger_on_insufficient_data(self):
        res = Resource(
            id="i-test-nodata",
            name="nodata-web",
            resource_type=ResourceType.EC2,
            region="us-east-1",
            status="running",
            monthly_cost=122.40,
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=2,
            avg_cpu_percent=4.0,
            peak_cpu_percent=12.0,
            has_sufficient_data=False,
        )
        rec = self.rightsizing_rule.evaluate(res, metrics)
        self.assertIsNone(rec)

    def test_rightsizing_does_not_treat_missing_metrics_as_zero(self):
        res = Resource(
            id="i-test-missing",
            name="missing-metrics",
            resource_type=ResourceType.EC2,
            region="us-east-1",
            status="running",
            monthly_cost=122.40,
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=14,
            avg_cpu_percent=None,
            peak_cpu_percent=None,
            has_sufficient_data=True,
        )
        rec = self.rightsizing_rule.evaluate(res, metrics)
        self.assertIsNone(rec)

    def test_idle_rule_triggers_on_completely_idle_instance(self):
        res = Resource(
            id="i-test-idle",
            name="idle-worker",
            resource_type=ResourceType.EC2,
            region="us-east-1",
            status="running",
            monthly_cost=78.00,
            details={"instance_type": "m5.large"},
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=14,
            avg_cpu_percent=0.8,
            peak_cpu_percent=2.1,
            network_in_bytes_sec=1200.0,
            has_sufficient_data=True,
        )
        rec = self.idle_rule.evaluate(res, metrics)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.priority, "HIGH")
        self.assertEqual(rec.estimated_savings, 78.00)

        rec_rightsize = self.rightsizing_rule.evaluate(res, metrics)
        self.assertIsNone(rec_rightsize, "Idle instance must not receive conflicting rightsizing recommendation")

    def test_ebs_unattached_rule_calculates_exact_gp3_costs(self):
        res = Resource(
            id="vol-0a7f82c9e4b1a3d5e",
            name="data-analytics-temp-backup",
            resource_type=ResourceType.EBS,
            region="us-east-1",
            status="available",
            monthly_cost=40.00,
            details={
                "volume_type": "gp3",
                "size_gb": 250,
                "provisioned_iops": 6000,
                "provisioned_throughput_mbps": 250,
                "days_unattached": 31,
                "storage_cost": 20.00,
                "provisioned_iops_cost": 15.00,
                "provisioned_throughput_cost": 5.00,
            },
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=14,
            disk_iops=0.0,
            has_sufficient_data=True,
        )
        rec = self.ebs_rule.evaluate(res, metrics)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.priority, "HIGH")
        self.assertEqual(rec.estimated_savings, 40.00)
        self.assertEqual(rec.confidence, 95)

    def test_ebs_unattached_does_not_trigger_on_attached_volume(self):
        res = Resource(
            id="vol-in-use",
            name="root-vol",
            resource_type=ResourceType.EBS,
            region="us-east-1",
            status="in-use",
            monthly_cost=8.00,
            details={"volume_type": "gp3", "size_gb": 100},
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=14,
            disk_iops=250.0,
            has_sufficient_data=True,
        )
        rec = self.ebs_rule.evaluate(res, metrics)
        self.assertIsNone(rec)

    def test_ebs_unattached_does_not_trigger_when_recently_created(self):
        res = Resource(
            id="vol-brand-new",
            name="new-volume",
            resource_type=ResourceType.EBS,
            region="us-east-1",
            status="available",
            monthly_cost=8.00,
            details={"volume_type": "gp3", "size_gb": 100, "days_unattached": 0},
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=0,
            has_sufficient_data=False,
            data_quality_warning="Volume created < 24 hours ago.",
        )
        rec = self.ebs_rule.evaluate(res, metrics)
        self.assertIsNone(rec)

    def test_s3_lifecycle_rule_calculates_glacier_tiering_savings(self):
        res = Resource(
            id="bucket-telemetry",
            name="production-app-telemetry-logs",
            resource_type=ResourceType.S3,
            region="us-west-2",
            status="active",
            monthly_cost=340.40,
            details={
                "storage_class": "Standard",
                "lifecycle_policy": None,
                "current_storage_gb": 14800.0,
                "stale_storage_gb_over_90d": 8200.0,
            },
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=30,
            has_sufficient_data=True,
        )
        rec = self.s3_rule.evaluate(res, metrics)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.estimated_savings, 155.80)
        self.assertEqual(rec.priority, "HIGH")

    def test_s3_lifecycle_rule_does_not_trigger_when_lifecycle_already_enabled(self):
        res = Resource(
            id="bucket-managed",
            name="managed-assets",
            resource_type=ResourceType.S3,
            region="us-east-1",
            status="active",
            monthly_cost=10.35,
            details={
                "storage_class": "Standard",
                "lifecycle_policy": "Enabled",
                "stale_storage_gb_over_90d": 200.0,
            },
        )
        metrics = ResourceMetrics(
            resource_id=res.id,
            observation_days=30,
            has_sufficient_data=True,
        )
        rec = self.s3_rule.evaluate(res, metrics)
        self.assertIsNone(rec)


if __name__ == "__main__":
    unittest.main()

"""Abstract Base Cloud Provider Contract.

Defines the interface for querying cloud resources, metrics, and spend.
Implementations may be a mock provider (for deterministic test scenarios)
or a real AWS provider (using boto3 / CloudWatch / Cost Explorer in future extensions)
without modifying the optimization analysis engine.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.models import (
    CostTrendPoint,
    Resource,
    ResourceMetrics,
    ScenarioMetadata,
)


class CloudProvider(ABC):
    """Abstract interface for cloud infrastructure inventory, metrics, and telemetry."""

    @abstractmethod
    def list_scenarios(self) -> List[ScenarioMetadata]:
        """List all available scenario configurations."""
        pass

    @abstractmethod
    def get_scenario_metadata(self, scenario_id: str) -> Optional[ScenarioMetadata]:
        """Retrieve metadata for a specific scenario."""
        pass

    @abstractmethod
    def get_resources(self, scenario_id: str) -> List[Resource]:
        """Retrieve the resource inventory for a scenario."""
        pass

    @abstractmethod
    def get_metrics(self, resource_id: str, scenario_id: str) -> Optional[ResourceMetrics]:
        """Retrieve telemetry and utilization metrics for a specific resource."""
        pass

    @abstractmethod
    def get_historical_cost_trend(self, scenario_id: str) -> List[CostTrendPoint]:
        """Retrieve monthly spend trend points for the scenario."""
        pass

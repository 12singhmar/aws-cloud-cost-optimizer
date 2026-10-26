"""Mock Cloud Provider implementation using deterministic scenarios."""

from typing import Dict, List, Optional

from app.models import (
    CostTrendPoint,
    Resource,
    ResourceMetrics,
    ScenarioMetadata,
)
from app.providers.base import CloudProvider
from app.scenarios import SCENARIO_REGISTRY, ScenarioDefinition


class MockAWSProvider(CloudProvider):
    """Deterministic Mock Provider representing AWS infrastructure telemetry."""

    def __init__(self, registry: Optional[Dict[str, ScenarioDefinition]] = None):
        self._registry = registry or SCENARIO_REGISTRY

    def list_scenarios(self) -> List[ScenarioMetadata]:
        return [scenario.metadata for scenario in self._registry.values()]

    def get_scenario_metadata(self, scenario_id: str) -> Optional[ScenarioMetadata]:
        scenario = self._registry.get(scenario_id)
        return scenario.metadata if scenario else None

    def get_resources(self, scenario_id: str) -> List[Resource]:
        scenario = self._registry.get(scenario_id)
        if not scenario:
            return []
        return [r.model_copy() for r in scenario.resources]

    def get_metrics(self, resource_id: str, scenario_id: str) -> Optional[ResourceMetrics]:
        scenario = self._registry.get(scenario_id)
        if not scenario:
            return None
        metrics = scenario.metrics.get(resource_id)
        return metrics.model_copy() if metrics else None

    def get_historical_cost_trend(self, scenario_id: str) -> List[CostTrendPoint]:
        scenario = self._registry.get(scenario_id)
        if not scenario:
            return []
        return [p.model_copy() for p in scenario.cost_trend]

    def get_scenario_definition(self, scenario_id: str) -> Optional[ScenarioDefinition]:
        return self._registry.get(scenario_id)

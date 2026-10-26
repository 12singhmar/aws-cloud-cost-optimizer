"""AWS Cloud Cost Optimiser - FastAPI Application.

Provides read-only scenario-based cost analysis, resource inventory,
evidence-backed optimization recommendations, and cross-functional Change Passports.
"""

from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.analysis.engine import AnalysisEngine
from app.models import (
    ChangePassport,
    DashboardResponse,
    Recommendation,
    Resource,
    ScenarioMetadata,
    SimulateRequest,
    SimulationResult,
    UndoSimulateRequest,
)
from app.providers.mock_provider import MockAWSProvider

app = FastAPI(
    title="AWS Cloud Cost Optimiser API",
    description="Explainable, read-only AWS cloud cost and utilisation analysis platform with Change Passport.",
    version="1.1.0",
)

# CORS middleware for local Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize provider and engine
provider = MockAWSProvider()
engine = AnalysisEngine(provider=provider)


class AttestRequest(BaseModel):
    scenario_id: str
    check_id: str
    attested: bool


@app.get("/api/health", tags=["System"])
def health_check():
    """System health check endpoint."""
    return {"status": "ok", "service": "aws-cloud-cost-optimiser", "version": "1.1.0"}


@app.get("/api/scenarios", response_model=List[ScenarioMetadata], tags=["Scenarios"])
def get_scenarios():
    """List all available deterministic test scenarios."""
    return provider.list_scenarios()


@app.get("/api/dashboard", response_model=DashboardResponse, tags=["Dashboard"])
def get_dashboard(
    scenario: str = Query(
        "high-cost-waste",
        description="Scenario ID (e.g. 'high-cost-waste', 'healthy-environment', 'mixed-environment', 'insufficient-data')",
    )
):
    """Retrieve full aggregated dashboard metrics and recommendations for a scenario."""
    meta = provider.get_scenario_metadata(scenario)
    if not meta:
        valid_ids = [s.id for s in provider.list_scenarios()]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario ID '{scenario}'. Valid scenario IDs: {valid_ids}",
        )

    dashboard = engine.analyze_scenario(scenario)
    if not dashboard:
        raise HTTPException(status_code=500, detail="Failed to run analysis on scenario.")
    return dashboard


@app.get("/api/recommendations", response_model=List[Recommendation], tags=["Recommendations"])
def get_recommendations(
    scenario: str = Query("high-cost-waste", description="Scenario ID to evaluate")
):
    """Retrieve generated optimisation recommendations for a scenario."""
    meta = provider.get_scenario_metadata(scenario)
    if not meta:
        valid_ids = [s.id for s in provider.list_scenarios()]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario ID '{scenario}'. Valid scenario IDs: {valid_ids}",
        )

    recs = engine.get_recommendations_for_scenario(scenario)
    if recs is None:
        raise HTTPException(status_code=500, detail="Failed to evaluate recommendations.")
    return recs


@app.get("/api/resources", response_model=List[Resource], tags=["Resources"])
def get_resources(
    scenario: str = Query("high-cost-waste", description="Scenario ID to query")
):
    """Retrieve the raw resource inventory for a scenario."""
    meta = provider.get_scenario_metadata(scenario)
    if not meta:
        valid_ids = [s.id for s in provider.list_scenarios()]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario ID '{scenario}'. Valid scenario IDs: {valid_ids}",
        )

    return provider.get_resources(scenario)


# ---------------------------------------------------------------------------
# Change Passport Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/api/change-passport/{recommendation_id}",
    response_model=ChangePassport,
    tags=["Change Passport"],
)
def get_change_passport(
    recommendation_id: str,
    scenario: str = Query("high-cost-waste", description="Scenario ID context"),
):
    """Retrieve a cross-functional Change Passport for an optimization recommendation."""
    meta = provider.get_scenario_metadata(scenario)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Invalid scenario ID '{scenario}'")

    passport = engine.generate_change_passport(recommendation_id, scenario)
    if not passport:
        raise HTTPException(
            status_code=404,
            detail=f"Recommendation '{recommendation_id}' not found in scenario '{scenario}'.",
        )
    return passport


@app.post(
    "/api/change-passport/simulate",
    response_model=SimulationResult,
    tags=["Change Passport"],
)
def simulate_change(req: SimulateRequest):
    """Simulate the financial and operational impact of an approved action."""
    meta = provider.get_scenario_metadata(req.scenario_id)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Invalid scenario ID '{req.scenario_id}'")

    sim = engine.simulate_change(req.scenario_id, req.recommendation_id, req.action_id)
    return sim


@app.post("/api/change-passport/simulate/undo", tags=["Change Passport"])
def undo_simulation(req: UndoSimulateRequest):
    """Undo a hypothetical simulation, reverting scenario metrics to pre-change baseline."""
    meta = provider.get_scenario_metadata(req.scenario_id)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Invalid scenario ID '{req.scenario_id}'")

    engine.undo_simulation(req.scenario_id, req.recommendation_id)
    return {"status": "ok", "message": f"Simulation for {req.recommendation_id} reverted."}


@app.post("/api/change-passport/attest", tags=["Change Passport"])
def toggle_attestation(req: AttestRequest):
    """Record user attestation for a departmental review item."""
    engine.toggle_attestation(req.scenario_id, req.check_id, req.attested)
    return {"status": "ok", "check_id": req.check_id, "attested": req.attested}

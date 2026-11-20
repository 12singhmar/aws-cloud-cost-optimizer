"""HTTP API (FastAPI). Thin layer: every endpoint just calls a module.

Read-only by design: there is no endpoint that changes anything in AWS.
Run:  uvicorn app.main:app --reload     Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import billcheck, lab
from app.analyzer import analyze, strip_lab_tags
from app.config import FLEET_FILE
from app.pricing import load_pricebook
from app.rules import RULE_CATALOG
from app.store import list_snapshots, load_bill, load_lab, load_snapshot

app = FastAPI(title="AWS Cloud Cost Optimizer", version="2.0.0",
              description="Read-only waste detection with checkable results.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET"], allow_headers=["*"])


def _snapshot(snapshot_id: str):
    try:
        return load_snapshot(snapshot_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, f"Snapshot '{snapshot_id}' not found")


@lru_cache(maxsize=16)
def _analysis(snapshot_id: str) -> dict:
    return analyze(_snapshot(snapshot_id))


@app.get("/api/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/api/snapshots")
def snapshots():
    return list_snapshots()


@app.get("/api/rules")
def rules():
    return RULE_CATALOG


@app.get("/api/analysis/{snapshot_id}")
def analysis(snapshot_id: str):
    return _analysis(snapshot_id)


@app.get("/api/lab/{snapshot_id}")
def lab_score(snapshot_id: str):
    manifest = load_lab(snapshot_id)
    if manifest is None:
        return {"available": False}
    return {"available": True, **lab.score(manifest, _analysis(snapshot_id)["findings"])}


@app.get("/api/billcheck/{snapshot_id}")
def bill_check(snapshot_id: str):
    bill = load_bill(snapshot_id)
    if bill is None:
        return {"available": False}
    s = strip_lab_tags(_snapshot(snapshot_id))
    return {"available": True, **billcheck.compare(s, bill, load_pricebook(s.meta.region))}


@app.get("/api/fleet")
def fleet():
    if not FLEET_FILE.exists():
        return {"available": False}
    return {"available": True, **json.loads(FLEET_FILE.read_text())}


@app.get("/api/prices/{region}")
def prices(region: str):
    try:
        return load_pricebook(region).summary()
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

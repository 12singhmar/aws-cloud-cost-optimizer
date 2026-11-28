"""FastAPI backend. Run:  python -m uvicorn app.main:app

No AWS account needed:
  GET  /api/info                    regions with prices, saved scans
  GET  /api/instance-types/{region} instance types with prices
  POST /api/estimate                cost checker
AWS account:
  GET  /api/profiles                AWS CLI profiles on this computer
  POST /api/connect                 choose a profile and test it
  GET  /api/status                  are we connected?
  POST /api/scan                    scan every region and save the result
  GET  /api/report/{scan_id}        costs and waste for a saved scan
  POST /api/fix                     clean up one flagged resource (after the user confirms)
"""

import os
import re
import threading
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import aws
from app.estimate import Setup, check
from app.fixes import run_fix
from app.models import Scan
from app.prices import available_regions, load_prices
from app.rules import find_waste, report

SCAN_DIR = Path(__file__).resolve().parents[1] / "data" / "scans"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,60}$")

os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")   # we run on a laptop, not on EC2
connection = {"profile": os.environ.get("AWS_PROFILE")}
busy = threading.Lock()                                       # one scan or fix at a time

app = FastAPI(title="AWS Cost Cleaner")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])


def session():
    return aws.make_session(connection["profile"])


def load_scan(scan_id):
    path = SCAN_DIR / f"{scan_id}.json"
    if not SAFE_ID.match(scan_id) or not path.exists():
        raise HTTPException(404, "Scan not found")
    return Scan.model_validate_json(path.read_text())


def saved_scans():
    scans = [Scan.model_validate_json(p.read_text()) for p in SCAN_DIR.glob("*.json")]
    scans.sort(key=lambda s: s.scanned_at, reverse=True)
    return [{"id": s.id, "account": s.account, "scanned_at": s.scanned_at, "fake_aws": s.fake_aws,
             "resources": len(s.resources)} for s in scans]


# ---------------------------------------------------------------- no account needed

@app.get("/api/info")
def info():
    return {"regions": available_regions(), "scans": saved_scans(), "test_mode": aws.is_fake_aws()}


@app.get("/api/instance-types/{region}")
def instance_types(region):
    p = load_prices(region)
    if p is None:
        raise HTTPException(404, "No prices for this region")
    return sorted(({"type": t, "vcpu": v["vcpu"], "memory_gib": v["memory_gib"], "hourly": v["usd_per_hour"]}
                   for t, v in p.instances.items()), key=lambda x: x["hourly"])


@app.post("/api/estimate")
def estimate(setup: Setup):
    try:
        return check(setup)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------- AWS account

class ConnectRequest(BaseModel):
    profile: str | None = None


@app.get("/api/profiles")
def profiles():
    return {"profiles": boto3.Session().available_profiles, "current": connection["profile"]}


@app.post("/api/connect")
def connect(req: ConnectRequest):
    connection["profile"] = req.profile or None
    return status()


@app.get("/api/status")
def status():
    try:
        who = aws.whoami(session())
    except (BotoCoreError, ClientError) as e:
        return {"connected": False, "error": str(e), "test_mode": aws.is_fake_aws()}
    return {"connected": True, "profile": connection["profile"], "test_mode": aws.is_fake_aws(), **who}


@app.post("/api/scan")
def scan_now():
    if not busy.acquire(blocking=False):
        raise HTTPException(409, "Already busy, try again in a moment")
    try:
        result = aws.scan_account(session())
        SCAN_DIR.mkdir(parents=True, exist_ok=True)
        (SCAN_DIR / f"{result.id}.json").write_text(result.model_dump_json(indent=1))
        return {"id": result.id}
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(502, f"AWS error: {e}")
    finally:
        busy.release()


@app.get("/api/scans")
def scans():
    return saved_scans()


@app.get("/api/report/{scan_id}")
def get_report(scan_id: str):
    return report(load_scan(scan_id))


class FixRequest(BaseModel):
    scan_id: str
    resource_id: str
    action: str


@app.post("/api/fix")
def fix(req: FixRequest):
    # only fix what the scan actually flagged, with the action it suggested
    findings, _ = find_waste(load_scan(req.scan_id))
    match = next((f for f in findings if f.resource_id == req.resource_id and f.fix_action == req.action), None)
    if match is None:
        raise HTTPException(400, "This resource was not flagged with that action in this scan")
    if not busy.acquire(blocking=False):
        raise HTTPException(409, "Already busy, try again in a moment")
    try:
        return {"message": run_fix(session(), match.region, req.action, req.resource_id)}
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(502, f"AWS error: {e}")
    finally:
        busy.release()

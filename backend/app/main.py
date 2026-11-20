"""FastAPI backend.

Works without AWS:
  GET  /api/overview            price list info + saved scans
  GET  /api/catalog/{region}    instance types with real prices
  POST /api/optimize            run the optimization engine on a workload
  GET  /api/usage/{scan_id}     usage analysis of every server in a scan

Needs AWS:
  GET  /api/profiles            AWS CLI profiles found on this computer
  POST /api/connect             choose a profile (and region) and test it
  GET  /api/status              are we connected?
  POST /api/scan                read the account now (read-only) and save it
  GET  /api/report/{scan_id}    waste findings for a saved scan
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import aws, usage
from app.models import Scan
from app.optimizer import Workload, optimize
from app.prices import available_regions, load_prices
from app.rules import build_report

SCAN_DIR = Path(__file__).resolve().parents[1] / "data" / "scans"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,60}$")
REGION_NAMES = {"ap-south-1": "Mumbai", "us-east-1": "N. Virginia", "us-west-2": "Oregon",
                "eu-west-1": "Ireland", "eu-central-1": "Frankfurt", "ap-southeast-1": "Singapore"}

# This runs on a laptop, not on an EC2 server, so skip the slow EC2 metadata lookup.
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

# Current connection. Starts from environment variables, can be changed with /api/connect.
connection = {"profile": os.environ.get("AWS_PROFILE"),
              "region": os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")}

app = FastAPI(title="AWS Cloud Cost Optimizer")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])
scan_lock = threading.Lock()


def session():
    return aws.make_session(connection["profile"], connection["region"])


def load_scan(scan_id: str) -> Scan:
    path = SCAN_DIR / f"{scan_id}.json"
    if not SAFE_ID.match(scan_id) or not path.exists():
        raise HTTPException(404, "Scan not found")
    return Scan.model_validate_json(path.read_text())


def scan_list() -> list[dict]:
    scans = []
    for path in SCAN_DIR.glob("*.json"):
        s = Scan.model_validate_json(path.read_text())
        scans.append({"id": s.id, "source": s.source, "account": s.account, "region": s.region,
                      "scanned_at": s.scanned_at, "description": s.description,
                      "servers": len(s.instances)})
    scans.sort(key=lambda s: (s["source"] == "aws", s["scanned_at"]), reverse=True)
    return scans


# ---------------------------------------------------------------- no AWS needed

@app.get("/api/overview")
def overview():
    regions = available_regions()
    p = load_prices(regions[0]) if regions else None
    return {"regions": [{"code": r, "name": REGION_NAMES.get(r, r)} for r in regions],
            "instance_types": len(p.instances) if p else 0,
            "price_list_version": p.version if p else None,
            "scans": scan_list()}


@app.get("/api/catalog/{region}")
def catalog(region: str):
    if region not in available_regions():
        raise HTTPException(404, "No prices for this region")
    p = load_prices(region)
    items = [{"type": t, "vcpu": i["vcpu"], "memory_gib": i["memory_gib"], "hourly": i["usd_per_hour"],
              "arm": i["arm"], "category": i["category"]} for t, i in p.instances.items()]
    return sorted(items, key=lambda x: (x["type"].split(".")[0], x["hourly"]))


@app.post("/api/optimize")
def run_optimizer(w: Workload):
    if w.region not in available_regions():
        raise HTTPException(400, f"No prices for {w.region}")
    try:
        return optimize(w)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/usage/{scan_id}")
def usage_analysis(scan_id: str):
    s = load_scan(scan_id)
    servers = [usage.analyze(i, s.metrics.get(i.id)) for i in s.instances if i.state == "running"]
    for srv in servers:
        if "workload" in srv:
            srv["workload"]["region"] = s.region
    return {"scan": {"id": s.id, "source": s.source, "account": s.account, "region": s.region,
                     "description": s.description}, "servers": servers}


# ---------------------------------------------------------------- AWS connection

class ConnectRequest(BaseModel):
    profile: Optional[str] = None
    region: Optional[str] = None


@app.get("/api/profiles")
def profiles():
    return {"profiles": boto3.Session().available_profiles, "current": connection}


@app.post("/api/connect")
def connect(req: ConnectRequest):
    connection["profile"] = req.profile or None
    connection["region"] = req.region or None
    return status()


@app.get("/api/status")
def status():
    try:
        info = aws.whoami(session())
    except (BotoCoreError, ClientError) as e:
        return {"connected": False, "error": str(e), "profile": connection["profile"]}
    if not info["region"]:
        return {"connected": False, "profile": connection["profile"],
                "error": "Connected, but no region is set. Choose a region."}
    return {"connected": True, "profile": connection["profile"], **info,
            "prices_available": info["region"] in available_regions()}


@app.post("/api/scan")
def scan_now():
    if not scan_lock.acquire(blocking=False):
        raise HTTPException(409, "A scan is already running")
    try:
        sess = session()
        if not sess.region_name:
            raise HTTPException(400, "No region set")
        load_prices(sess.region_name)
        result = aws.scan_account(sess)
        SCAN_DIR.mkdir(parents=True, exist_ok=True)
        (SCAN_DIR / f"{result.id}.json").write_text(result.model_dump_json(indent=1))
        return {"id": result.id}
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(502, f"AWS error: {e}")
    finally:
        scan_lock.release()


@app.get("/api/scans")
def list_scans():
    return scan_list()


@app.get("/api/report/{scan_id}")
def report(scan_id: str):
    s = load_scan(scan_id)
    try:
        return build_report(s, load_prices(s.region))
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))

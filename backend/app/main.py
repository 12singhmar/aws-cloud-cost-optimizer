"""FastAPI backend.

GET  /api/status          are we connected to AWS?
POST /api/scan            read the AWS account now and save the result
GET  /api/scans           list saved scans
GET  /api/report/{id}     findings for one saved scan

Every scan is saved to data/scans/, so old results can be shown without AWS.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import aws
from app.models import Scan
from app.prices import available_regions, load_prices
from app.rules import build_report

SCAN_DIR = Path(__file__).resolve().parents[1] / "data" / "scans"
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,60}$")

# This runs on a laptop, not on an EC2 server, so skip the slow EC2 metadata lookup.
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")

# Which AWS profile to use. Set before starting:  set AWS_PROFILE=ccx  (Windows)
PROFILE = os.environ.get("AWS_PROFILE")
REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")

app = FastAPI(title="AWS Cloud Cost Optimizer")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])
scan_lock = threading.Lock()


def session():
    return aws.make_session(PROFILE, REGION)


@app.get("/api/status")
def status():
    try:
        info = aws.whoami(session())
    except (BotoCoreError, ClientError) as e:
        return {"connected": False, "error": str(e), "profile": PROFILE}
    region = info["region"]
    return {"connected": True, "profile": PROFILE, **info,
            "prices_available": region in available_regions()}


@app.post("/api/scan")
def scan_now():
    if not scan_lock.acquire(blocking=False):
        raise HTTPException(409, "A scan is already running")
    try:
        sess = session()
        if not sess.region_name:
            raise HTTPException(400, "No region set. Use: aws configure set region <region> --profile <name>")
        load_prices(sess.region_name)        # fail early if we have no prices for this region
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
    scans = []
    for path in SCAN_DIR.glob("*.json"):
        s = Scan.model_validate_json(path.read_text())
        scans.append({"id": s.id, "source": s.source, "account": s.account,
                      "region": s.region, "scanned_at": s.scanned_at})
    # newest real scans first, sample last
    scans.sort(key=lambda s: (s["source"] == "aws", s["scanned_at"]), reverse=True)
    return scans


@app.get("/api/report/{scan_id}")
def report(scan_id: str):
    path = SCAN_DIR / f"{scan_id}.json"
    if not SAFE_ID.match(scan_id) or not path.exists():
        raise HTTPException(404, "Scan not found")
    scan = Scan.model_validate_json(path.read_text())
    try:
        return build_report(scan, load_prices(scan.region))
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))

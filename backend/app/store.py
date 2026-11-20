"""Loading and saving files under backend/data (snapshots, labs, bills)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from app.config import BILL_DIR, LAB_DIR, SNAPSHOT_DIR
from app.models import Snapshot

SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _path(folder: Path, snapshot_id: str) -> Path:
    # Snapshot ids come from the URL, so never let them escape the folder.
    if not SAFE_ID.match(snapshot_id):
        raise ValueError(f"Invalid snapshot id: {snapshot_id!r}")
    return folder / f"{snapshot_id}.json"


def list_snapshots() -> list[dict]:
    items = []
    for p in sorted(SNAPSHOT_DIR.glob("*.json")):
        meta = json.loads(p.read_text())["meta"]
        items.append({**meta,
                      "has_lab": _path(LAB_DIR, meta["id"]).exists(),
                      "has_bill": _path(BILL_DIR, meta["id"]).exists()})
    # real account data first (newest first), demo data last
    aws =sorted([m for m in items if m["source"] == "aws"], key=lambda m: m["collected_at"], reverse=True)
    return aws + [m for m in items if m["source"] != "aws"]


def load_snapshot(snapshot_id: str) -> Snapshot:
    p = _path(SNAPSHOT_DIR, snapshot_id)
    if not p.exists():
        raise FileNotFoundError(snapshot_id)
    return Snapshot.model_validate_json(p.read_text())


def save_snapshot(s: Snapshot) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(SNAPSHOT_DIR, s.meta.id)
    p.write_text(s.model_dump_json(indent=1))
    return p


def load_json(folder: Path, snapshot_id: str) -> Optional[dict]:
    p = _path(folder, snapshot_id)
    return json.loads(p.read_text()) if p.exists() else None


def load_lab(snapshot_id: str) -> Optional[dict]:
    return load_json(LAB_DIR, snapshot_id)


def load_bill(snapshot_id: str) -> Optional[dict]:
    return load_json(BILL_DIR, snapshot_id)

"""Real AWS prices, saved by scripts/fetch_prices.py from the public AWS Price List."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PRICE_DIR = Path(__file__).resolve().parents[1] / "data" / "prices"
HOURS_PER_MONTH = 730   # AWS uses 730 hours for monthly estimates


class Prices:
    def __init__(self, data: dict):
        self.region = data["region"]
        self.version = data.get("ec2_price_list_version", "")
        self.instances = data["instances"]
        self.other = data["other"]

    def has_instance(self, itype: str) -> bool:
        return itype in self.instances

    def instance_hourly(self, itype: str) -> float:
        return self.instances[itype]["usd_per_hour"]

    def get(self, key: str) -> float:
        return self.other[key]["usd"]

    def sku(self, key: str) -> str:
        p = self.other[key]
        return f"{p['sku']} ({p['description']})"

    def instance_sku(self, itype: str) -> str:
        p = self.instances[itype]
        return f"{p['sku']} ({p['description']})"


def available_regions() -> list[str]:
    return sorted(p.stem for p in PRICE_DIR.glob("*.json"))


@lru_cache(maxsize=8)
def load_prices(region: str) -> Prices:
    path = PRICE_DIR / f"{region}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No prices for {region}. Run: python scripts/fetch_prices.py --region {region}")
    return Prices(json.loads(path.read_text()))

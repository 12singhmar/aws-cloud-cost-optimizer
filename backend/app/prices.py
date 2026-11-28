"""Real AWS prices, saved per region by scripts/fetch_prices.py."""

import json
from functools import lru_cache
from pathlib import Path

PRICE_DIR = Path(__file__).resolve().parents[1] / "data" / "prices"
HOURS_PER_MONTH = 730    # AWS uses 730 hours for a month (365 x 24 / 12)


class Prices:
    def __init__(self, data):
        self.region = data["region"]
        self.version = data.get("price_list_version", "")
        self.instances = data["instances"]
        self.other = data["other"]

    def get(self, key):
        return self.other[key]["usd"] if key in self.other else None

    def instance_hourly(self, itype):
        return self.instances[itype]["usd_per_hour"] if itype in self.instances else None


def available_regions():
    return sorted(p.stem for p in PRICE_DIR.glob("*.json"))


@lru_cache(maxsize=32)
def load_prices(region):
    path = PRICE_DIR / f"{region}.json"
    if not path.exists():
        return None
    return Prices(json.loads(path.read_text()))

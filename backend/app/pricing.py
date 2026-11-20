"""Price book: looks up real AWS prices saved by scripts/fetch_prices.py.

Nothing here is typed in by hand. If a price is missing we raise an error
instead of guessing - a wrong price is worse than no price.
"""

from __future__ import annotations

import json
from functools import lru_cache

from app.config import HOURS_PER_MONTH, PRICE_DIR
from app.models import PriceRef


class PriceNotFound(KeyError):
    pass


class PriceBook:
    def __init__(self, data: dict):
        self.region = data["region"]
        self.version = data.get("ec2_price_list_version", "")
        self.fetched_at = data.get("fetched_at", "")
        self.source = data.get("source", "")
        self._instances = data["instances"]
        self._other = data["other"]

    # -- instances ---------------------------------------------------------
    def has_instance(self, itype: str) -> bool:
        return itype in self._instances

    def instance(self, itype: str) -> dict:
        if itype not in self._instances:
            raise PriceNotFound(f"No price for instance type {itype} in {self.region}")
        return self._instances[itype]

    def instance_hourly(self, itype: str) -> float:
        return self.instance(itype)["usd_per_hour"]

    def instance_monthly(self, itype: str) -> float:
        return round(self.instance_hourly(itype) * HOURS_PER_MONTH, 4)

    def instance_ref(self, itype: str) -> PriceRef:
        p = self.instance(itype)
        return PriceRef(key=f"ec2:{itype}", usd=p["usd_per_hour"], unit="Hrs",
                        sku=p["sku"], description=p["description"])

    # -- everything else ----------------------------------------------------
    def get(self, key: str) -> float:
        if key not in self._other:
            raise PriceNotFound(f"No price '{key}' in {self.region}")
        return self._other[key]["usd"]

    def ref(self, key: str) -> PriceRef:
        p = self._other[key]
        return PriceRef(key=key, usd=p["usd"], unit=p["unit"], sku=p["sku"],
                        description=p["description"])

    def summary(self) -> dict:
        return {
            "region": self.region,
            "version": self.version,
            "fetched_at": self.fetched_at,
            "source": self.source,
            "instance_types": len(self._instances),
            "other": [self.ref(k).model_dump() for k in sorted(self._other)],
        }


@lru_cache(maxsize=8)
def load_pricebook(region: str) -> PriceBook:
    path = PRICE_DIR / f"{region}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No price file for {region}. Run: python scripts/fetch_prices.py --region {region}")
    return PriceBook(json.loads(path.read_text()))

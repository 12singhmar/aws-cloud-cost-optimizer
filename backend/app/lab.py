"""Waste Lab scorecard: how good is the detector, measured on a real account?

scripts/lab_plant.py creates resources in your AWS account whose correct
answer we already know:
  - "waste"  : should be flagged (e.g. an unattached disk)
  - "decoy"  : looks suspicious to a naive tool, but is fine
               (e.g. low CPU but busy network = a proxy, not idle)

The answer key lives in a separate manifest file. The analyser never sees it
(and lab tags are stripped), so this is a fair test - like hiding the answer
sheet from the student.

Scoring (standard classification terms):
  True positive  (TP) : waste, flagged by the right rule
  False negative (FN) : waste, missed (or flagged by the wrong rule)
  False positive (FP) : decoy, flagged
  True negative  (TN) : decoy, left alone
  Precision = TP / (TP + FP)   "when we say waste, how often are we right?"
  Recall    = TP / (TP + FN)   "how much of the waste do we find?"
"""

from __future__ import annotations


def score(manifest: dict, findings: list[dict]) -> dict:
    """Only *active* findings count: a finding blocked by the backtest is not
    advice the tool gives, so it cannot be a false positive."""
    findings = [f for f in findings if f.get("status", "active") == "active"]
    by_resource: dict[str, list[dict]] = {}
    for f in findings:
        by_resource.setdefault(f["resource_id"], []).append(f)

    rows, tp, fn, fp, tn = [], 0, 0, 0, 0
    for item in manifest["items"]:
        hits = by_resource.get(item["resource_id"], [])
        rules = [h["rule_id"] for h in hits]
        if item["role"] == "waste":
            ok = item["expected_rule"] in rules
            outcome = "TP" if ok else "FN"
            tp += ok
            fn += not ok
        else:
            # A decoy may target specific rules (e.g. "must not be called idle");
            # an empty list means no rule should flag it.
            must_not = item.get("must_not") or []
            bad = [r for r in rules if not must_not or r in must_not]
            outcome = "FP" if bad else "TN"
            fp += bool(bad)
            tn += not bad
        rows.append({**item, "flagged_by": rules, "outcome": outcome,
                     "correct": outcome in ("TP", "TN")})

    lab_ids = {i["resource_id"] for i in manifest["items"]}
    others = [f for f in findings if f["resource_id"] not in lab_ids]
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "lab_id": manifest.get("lab_id"),
        "synthetic": manifest.get("synthetic", False),
        "planted_at": manifest.get("created_at"),
        "counts": {"TP": tp, "FN": fn, "FP": fp, "TN": tn},
        "precision": precision,
        "recall": recall,
        "accuracy": (tp + tn) / len(rows) if rows else None,
        "items": rows,
        "other_findings": [{"resource_id": f["resource_id"], "title": f["title"],
                            "rule_id": f["rule_id"]} for f in others],
    }

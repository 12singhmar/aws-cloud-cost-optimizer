# Design and Testing Report

## 1. Problem

Cloud bills grow through small, forgotten things: an unattached disk, a reserved IP, a test server left
running. Cost tools find these, but they share one weakness: **they never show whether their advice is
right**. A "you could save $74/month" message has no evidence that the saving is real, or that acting on
it won't break something.

## 2. Objectives

1. Detect common AWS waste from **real account data**, read-only.
2. Price every finding with **official AWS prices**, traceable to a SKU.
3. Explain every finding: evidence, line-by-line calculation, read-only checks, safe fix steps.
4. **Measure the tool's own trustworthiness** three ways: backtest, planted ground truth, real bill.
5. Cost the student **no money** (AWS free plan + free public data).

## 3. Requirements

### Functional
| ID | Requirement | Where |
|---|---|---|
| FR1 | Collect a read-only snapshot of an AWS account (EC2, EBS, EIP, snapshots, S3, 14 days of hourly metrics) | `scripts/collect_snapshot.py` |
| FR2 | Load real prices from the AWS Price List | `scripts/fetch_prices.py`, `app/pricing.py` |
| FR3 | Detect 8 kinds of waste with documented thresholds | `app/rules.py`, `app/config.py` |
| FR4 | Refuse to judge when data is insufficient, and say so | `app/analyzer.py` (notices) |
| FR5 | Backtest instance advice and block advice that fails | `app/backtest.py`, `app/analyzer.py` |
| FR6 | Score the detector against a planted answer key | `scripts/lab_plant.py`, `app/lab.py` |
| FR7 | Compare estimates with the real bill per resource | `scripts/load_bill.py`, `app/billcheck.py` |
| FR8 | Web UI with overview, findings, backtest, lab, bill check, fleet study, method | `frontend/` |

### Non-functional
| ID | Requirement | How it is met |
|---|---|---|
| NFR1 | Safety: the tool cannot change the account | API exposes GET only (tested); collector uses describe/list/get only; separate IAM users |
| NFR2 | Reproducibility | Analysis runs on saved snapshots; "now" = snapshot time; demo data is seeded |
| NFR3 | Explainability | Every finding carries evidence, calculation steps, price SKUs, commands |
| NFR4 | Privacy | Account number masked; no keys in repo; lab tags stripped before analysis |
| NFR5 | Cost | Only free-tier APIs; lab ≈ $8–10 of free-plan credit |
| NFR6 | Maintainability | One rule = one function; all thresholds in `config.py`; 37 automated tests; CI |
| NFR7 | Accessibility | Status shown with icon + word (never colour alone); light/dark themes; works at 375 px |

## 4. Architecture

```
            ┌──────────────── outside world ────────────────┐
            │ AWS account     AWS Price List    Azure trace │
            └──────┬──────────────┬──────────────────┬──────┘
   scripts/        │ read-only    │ public files     │ public file
   (adapters)  collect_snapshot  fetch_prices     fleet_study      lab_plant / lab_teardown / load_bill
                   │              │                  │
   backend/data/  snapshots/    prices/           fleet/          labs/   bills/
                   └──────┬───────┘                  │              │       │
   backend/app/        analyzer ── rules ── costs ── pricing        lab   billcheck
   (pure logic)           │
                       backtest
                          │
                       main.py (FastAPI, GET only)
                          │  JSON
   frontend/           React UI (7 pages, SVG charts)
```

**Key design decision: snapshots in the middle.** Scripts that talk to AWS write files; the app only
reads files. Benefits: the app has no AWS credentials at all (safety), results are reproducible
(the viva demo works offline), and the logic is testable without AWS (tests build snapshots by hand).
This is the *ports and adapters* idea in its simplest form.

## 5. Design decisions (and the alternatives we rejected)

| Decision | Why | Rejected alternative |
|---|---|---|
| Prices from the AWS Price List files, stored with SKU | Real, citable, free, no account needed | Hard-coded prices (the old version had m5.large wrong by 12%) |
| `GetMetricStatistics`, not `GetMetricData` | Free tier covers it | `GetMetricData` is always charged |
| Billing export (CUR 2.0), not Cost Explorer API | Free; has per-resource, per-hour lines | Cost Explorer API charges per request and lacks resource detail by default |
| p95 of hourly **max** CPU for rightsizing | Averages hide busy hours (Fleet Study: 18.2% harm rate for avg-only) | Average CPU < 10% |
| Backtest gate | p95 can miss short regular jobs (2 h/night = 8% of week 2 but only 4% of 14 days) | Trusting a single window |
| Waste Lab with decoys | Precision needs negatives; flag-everything would score 100% recall | Only planting waste |
| Answer key in a separate file + lab tags stripped | Detector cannot cheat | Tags like `expected=waste` visible to the detector |
| "Not estimated" for S3 lifecycle | No access-pattern data → no honest number | Assume a % of data is cold |
| Snapshot cost labelled "upper bound" | AWS bills stored blocks, not volume size; Bill Check shows the gap | Pretending it is exact |

## 6. Rules

See `RULE_CATALOG` in `app/rules.py` (also shown on the "How it works" page). Each rule returns
`Finding` objects with: evidence, calculation steps, price references, confidence + reason,
risk + reason, read-only check commands, fix steps.

Idle and rightsizing never both fire for one instance. Instances without ≥ 7 days of mostly-complete
data get a notice instead of a finding. Missing hours are never treated as zero.

## 7. Novelty, in one paragraph

The tool is evaluated on itself. (1) A **backtest gate** replays history and blocks advice that would have
hurt. (2) A **Waste Lab** plants known waste and decoys in a real account to measure precision and recall
on ground truth. (3) A **Bill Check** compares estimates with the real per-resource bill. (4) A **Fleet
Study** on 2.7 M real VMs quantifies how often the common rule of thumb is harmful (18.2%). Commercial
tools show estimates; this project measures them.

## 8. Test plan

37 automated tests (`backend/tests`), run by CI on every push.

| Area | What is tested | File |
|---|---|---|
| Prices & costs | SKUs present; unknown price raises (no guessing); gp3 free baseline; IPv4 hours; percentile | `test_pricing_and_costs.py` |
| Rules | Each rule fires on its case and not on near-misses: busy-network decoy, 2-day-old volume, attached IP, existing-volume snapshot, AMI-backed snapshot, smallest size, burstable credit baseline, 40% boundary, insufficient and gappy data, young instance | `test_rules.py` |
| Fairness | Lab tags hidden from the detector; every finding fully explained | `test_rules.py` |
| Backtest | Steady instance holds; new nightly job blocks the advice and removes it from savings; idle that wakes up; < 10 days → no backtest | `test_backtest_lab_bill.py` |
| Lab scoring | TP/FN/FP/TN incl. wrong-rule, rule-specific decoys, blocked findings, outside-lab findings | `test_backtest_lab_bill.py` |
| Bill check | Rate comparison; $0 billed is explained, not divided by zero; CUR parsing skips credits | `test_backtest_lab_bill.py` |
| API | Health, demo analysis, lab, bill, fleet; 404 for unknown/path-traversal ids; **only GET routes exist** | `test_api_and_collector.py` |
| AWS collector | Runs against a fake AWS (moto) | `test_api_and_collector.py` |
| End to end | Plant lab → collect → teardown leaves nothing behind, on fake AWS | `test_lab_scripts.py` |

Bugs the tests caught during development:
- Unassociated Elastic IPs can come back with an empty-string instance id, which would have hidden every idle IP.
- Instances younger than the metric window looked like they had "missing data" and were skipped.
- The rightsizing rule missed a nightly job; the backtest caught it, which led to the backtest gate.

Manual tests: UI checked at 1440 px and 375 px, light and dark, no console errors.

## 9. Limitations (stated, not hidden)

- **Memory is not measured** (needs the CloudWatch agent), so rightsizing confidence is capped at Medium.
- The Waste Lab is small (11 items). It proves the pipeline works on a real account; it is not a statistical benchmark.
  The Fleet Study supplies the scale.
- The Fleet Study's harm measure uses the same p95 statistic as our rule, so our rule's 0% is partly by construction.
  Its out-of-sample test is the backtest.
- One region per snapshot; On-Demand Linux prices only; no Savings Plans / Reserved Instance advice.
- CPU scaling by vCPU ratio is an approximation (different CPU generations, burst behaviour).

## 10. Future work

Memory via CloudWatch agent; multi-region collection; RDS and NAT Gateway rules; scheduled collection
and trend over time; calibrating snapshot estimates from the Bill Check.

# Viva Guide

## The project in two sentences

A read-only tool that finds wasted money in an AWS account using real prices. Its novelty is that it
**tests its own advice**: it replays history (backtest), plants known waste in a real account (Waste Lab), and
compares its estimates with the real bill (Bill Check).

## Suggested split (team of 3–4)

| Person | Owns | Should be able to explain |
|---|---|---|
| A | Data collection & pricing | `collect_snapshot.py`, `fetch_prices.py`, free-tier choices, IAM |
| B | Rules & cost model | `rules.py`, `costs.py`, `config.py` thresholds |
| C | Evaluation | `backtest.py`, `lab.py`, `billcheck.py`, Fleet Study |
| D (or A) | Frontend & testing | React pages, charts, the test suite, CI |

Everyone should be able to give the two-sentence summary and walk through one finding end to end.

## 8-minute demo script

1. **Overview** (1 min): "This is our real account snapshot, collected read-only on <date>." Point at the green
   *Real AWS account* badge, the run-rate, savings, and the "Can we trust these results?" box.
2. **Findings** (2 min): open the unattached volume. Evidence → calculation → SKU → "check it yourself" command.
   "Every number traces back to an official AWS price."
3. **Backtest** (1.5 min): open the *batch* instance. "Week 1 said downsize. Then a nightly job started. Our p95 rule
   alone would have missed it, so the backtest blocks the advice and it is not counted in savings."
4. **Waste Lab** (1.5 min): confusion matrix. "We planted 6 waste items and 5 decoys. The answer key is in a separate file
   and lab tags are stripped, so the detector cannot cheat."
5. **Bill Check** (1 min): "Estimates match the bill within X% except snapshots, which we price as an upper bound.
   This page is how we found out by how much."
6. **Fleet Study** (1 min): "On 2.7 million real Azure VMs, the usual rule hurts 18.2% of the servers it flags."

Have the demo snapshot ready as a fallback; it works with no internet.

## Likely questions

**Where is the real data?**
`backend/data/snapshots/aws-*.json`, collected from our own AWS account with `collect_snapshot.py`. The
bill is from the AWS CUR 2.0 export. The account number is masked; resource IDs are real.

**Did this cost money?**
No. Free plan credits only; the free plan does not bill the card unless upgraded. The collector uses only
free APIs. We avoided `GetMetricData` and the Cost Explorer API on purpose because they are always charged.

**Why not just use AWS Trusted Advisor / Compute Optimizer?**
They give estimates but never measure their own accuracy, and some checks need paid support plans. Our
contribution is the evaluation layer: backtest, ground-truth lab, bill comparison.

**Why p95 of the max, not average CPU?**
Averages hide busy hours. The Fleet Study shows 18.2% of VMs flagged by "avg < 10%" would be maxed out
after halving. p95 of hourly max means "95% of hours are below this", so the busiest ~1 hour a day is
allowed to be higher.

**Why 40%?**
Halving vCPUs roughly doubles the CPU %. 40% becomes 80%, leaving a 20% safety margin. It is in `config.py`
with that reason written next to it.

**Isn't 0% harm for your rule in the Fleet Study circular?**
Partly, yes, and we say so on the page. That study measures the cost of the common rule and how much
saving our safety check gives up (21%). The out-of-sample test of our rule is the backtest, which decides
on week 1 and checks on later data.

**What about burstable (t3) instances?**
They earn CPU credits at a baseline rate (t3.micro 10%, t3.nano 5%). We only downsize if the projected
average stays under 80% of the smaller size's baseline.

**How do you stop the lab from cheating?**
The expected answers live in `data/labs/manifest-*.json`, which the analyser never reads. The only
lab marker on resources is the `ccx-lab` tag, and `strip_lab_tags()` removes it before any rule runs (tested).

**What is a decoy? Give an example.**
A resource that looks wasteful to a naive tool but isn't. The proxy has ~0% CPU but downloads steadily,
so it is working. The batch server is quiet for a week and then runs a nightly job.

**What if CloudWatch data is missing?**
We never treat missing as zero. If there are fewer than 7 days or under 80% coverage, the instance gets a
notice ("not enough data") instead of a finding.

**Why snapshots (files) instead of calling AWS live?**
Safety (the web app holds no credentials), reproducibility (same input → same output), testability, and
the demo works offline.

**How did you test code that talks to AWS?**
With `moto`, a library that fakes AWS locally. We plant the whole lab, collect, and tear down on fake AWS
in a test. It caught a real bug: unassociated IPs can return an empty-string instance id.

**Why are snapshot estimates wrong in the Bill Check?**
AWS bills only the blocks a snapshot stores, not the full volume size. We price the full size, so our
number is an upper bound. The finding says "upper bound", and the Bill Check measures the gap.

**Is the tool safe to run on a company account?**
The collector needs only the read-only policy in `docs/iam/readonly-policy.json`. The API has only GET
routes (a test checks this). Fix steps are suggestions for a human to run.

**What would you do next?**
Memory metrics via the CloudWatch agent, more services (RDS, NAT Gateway), multi-region, and using
the Bill Check to automatically calibrate estimates.

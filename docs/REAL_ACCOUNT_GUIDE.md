# Running it on a real AWS account (with zero money)

This guide gets **real account data** into the project: a snapshot of a live account, a Waste Lab
with known answers, and the real bill to check the estimates against.

Total time: about 1 hour of work, spread over ~12 days of waiting.

## 0. Will this cost money?

- **AWS free plan** (accounts created after 15 July 2025): you get $100 in credits at sign-up (up to $100 more
  for trying services). On the free plan **AWS does not charge your card unless you upgrade to a paid plan**.
  The plan ends after 6 months or when credits run out. Sign-up still asks for a card for identity checks.
- The Waste Lab uses about **$8–10 of those credits** over 10 days (three `t3.micro` servers, one public IP,
  tiny disks). The read-only collector costs nothing: describe/list calls are free, and we use CloudWatch
  `GetMetricStatistics` (inside the free 1 million requests). We deliberately avoid `GetMetricData` and the
  Cost Explorer API because they are always charged.
- **Never click "Upgrade to paid plan".** Check your plan any time: Billing console → *Free Tier*.

> Check AWS's current free-plan terms when you sign up. They changed in July 2025 and may change again.

## 1. Account and safety (day 0, 20 min)

1. Create the account at aws.amazon.com and choose the **Free plan**.
2. Turn on MFA for the root user (IAM → Security recommendations).
3. Billing → Budgets → **Create budget → "Zero spend budget"** template, with your email. You get an email
   if anything is ever charged.
4. Pick region **Asia Pacific (Mumbai) `ap-south-1`** in the console's top-right corner and stay there.

## 2. Two IAM users: one read-only, one for the lab (day 0, 10 min)

Least privilege: the tool itself never gets write permission.

| User | Policy file | Used by |
|---|---|---|
| `ccx-readonly` | [iam/readonly-policy.json](iam/readonly-policy.json) | `collect_snapshot.py`, `load_bill.py` |
| `ccx-lab-admin` | [iam/lab-admin-policy.json](iam/lab-admin-policy.json) | `lab_plant.py`, `lab_teardown.py` |

For each: IAM → Users → Create user → *Attach policies directly* → Create policy → JSON tab → paste the file.
Then the user → Security credentials → **Create access key** → "Command Line Interface". Configure the AWS CLI:

```bash
aws configure --profile ccx-readonly
```

```bash
aws configure --profile ccx-lab-admin
```

(region `ap-south-1`, output `json`). **Never commit keys.** They live in `~/.aws/credentials`, outside the repo.

## 3. Turn on the billing export (day 0, 5 min)

Billing → **Data Exports** → Create:
- Export type: **Standard data export**, table **CUR 2.0**
- Tick **Include resource IDs**; time granularity **Hourly**
- Format **CSV (gzip)**; let AWS create a new S3 bucket for it (e.g. `ccx-bill-<yourname>`)
- Add `s3:GetObject` / `s3:ListBucket` on that bucket to the read-only policy (the file has a placeholder)

AWS delivers the first files within 24 hours and refreshes them during the day.

## 4. Plant the Waste Lab (day 0, 5 min)

```bash
cd backend
python scripts/lab_plant.py --profile ccx-lab-admin --yes
```

It prints a lab id like `lab-2026-11-25-ab12` and saves the answer key to `data/labs/manifest-<id>.json`.
It creates 6 waste items and 5 decoys, all tagged `ccx-lab=<id>` (see the script's docstring for the list).

## 5. Wait 10 days

The backtest needs 7 days to decide and 3 days to check. The "batch" decoy starts its nightly job on day 7.
Collect on **day 10, 11 or 12** (before day 14, so week 1 is still inside the 14-day metric window).

## 6. Collect the snapshot (day 10–12, 2 min)

```bash
python scripts/collect_snapshot.py --profile ccx-readonly --lab lab-2026-11-25-ab12
```

This writes `data/snapshots/aws-<date>.json` (account number masked) and links the answer key.
Restart the backend and pick the snapshot in the top bar: Overview, Findings, Backtest and Waste Lab now
show **real account data**.

## 7. Load the bill (the next day)

```bash
python scripts/load_bill.py --snapshot aws-2026-12-05-0900 --s3 s3://ccx-bill-yourname/ --profile ccx-readonly
```

The Bill Check page now compares estimates with real charges. On the free plan, charges show as usage
and are then cancelled by a separate credit line. We compare the usage lines.

## 8. Tear down (same day)

```bash
python scripts/lab_teardown.py --profile ccx-lab-admin --lab lab-2026-11-25-ab12 --dry-run
```

```bash
python scripts/lab_teardown.py --profile ccx-lab-admin --lab lab-2026-11-25-ab12 --yes
```

Run the dry-run again: it should list nothing. Optionally delete the Data Export and its bucket, and
deactivate both access keys (IAM → Users → Security credentials).

## 9. Submit

Commit `backend/data/snapshots/aws-*.json`, `backend/data/labs/aws-*.json` and `backend/data/bills/aws-*.json`.
They contain resource IDs and a masked account number, no secrets. The examiner can then run the app offline
and see your real results.

## Timeline at a glance

| Day | Action |
|---|---|
| 0 | Account, budget alert, IAM users, billing export, `lab_plant.py` |
| 1–9 | Nothing (optionally run `collect_snapshot.py` without `--lab` to see "not enough data" notices) |
| 10–12 | `collect_snapshot.py --lab ...` |
| 11–13 | `load_bill.py`, then `lab_teardown.py` |

## If something goes wrong

| Problem | Fix |
|---|---|
| `No AWS credentials found` | Pass `--profile`, or re-run `aws configure --profile ...` |
| `AccessDenied` on a call | That permission is missing from the policy file you pasted |
| `No default VPC subnet found` | `aws ec2 create-default-vpc --profile ccx-lab-admin` |
| `t3.micro is not marked free-tier eligible` | Stop (Ctrl+C) and check your plan before continuing |
| Findings page says "only N hours of CPU data" | Wait longer; the rules refuse to judge on < 7 days |

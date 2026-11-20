# AWS Cloud Cost Optimizer

A web app that works out the cheapest way to run AWS servers without hurting them. It uses the
official AWS price list and real CPU history from CloudWatch. Most of it works **without an AWS account**.

It has three parts:

| Part | What it does | Needs AWS account? |
|---|---|---|
| **Cost Planner** | You describe a server (type, hours, CPU use, disk). The optimizer finds the cheapest plan and explains every step. | No |
| **Usage Analysis** | Reads hourly CPU history and finds idle servers, oversized servers and servers that are quiet at fixed times (e.g. weekends). Sends the result to the planner. | No (uses a public dataset of real EC2 servers) |
| **My AWS Account** | Connects to your account (read-only, boto3), finds wasted disks, IPs, snapshots and servers, and feeds real CPU history into Usage Analysis. | Yes |

## The optimizer (backend/app/optimizer.py)

The optimizer applies five steps in order. Each step starts from the result of the previous one,
so a saving is never counted twice and the steps always add up to the total.

1. **Rightsize.** Work needed = current vCPUs × busy-time CPU. The new type needs enough vCPUs to keep
   busy-time CPU under 70%, and at least the same memory. We search all instance types in the region and
   take the cheapest one that fits. Burstable types (t3/t3a/t4g) are allowed only if the average CPU
   stays under 80% of that type's CPU-credit baseline.
2. **Switch to ARM (Graviton).** Same search, also allowing ARM types. Only if the user ticks "software can run on ARM".
3. **Schedule or reserve.** Compare: on-demand for only the hours needed, vs. a 1-year or 3-year reservation
   (paid for every hour, used or not). Break-even = reservation cost ÷ (on-demand price × 730 h).
   A server needed 45 h/week should be scheduled; one needed 24/7 should be reserved.
4. **Disk gp2 → gp3.** gp2 gives 3 IOPS per GB and IOPS × 256 KiB of throughput. gp3 includes 3,000 IOPS
   and 125 MiB/s. We add the extra IOPS/throughput gp3 needs to match gp2, then compare prices.
5. **Region.** Price the same plan in the other regions. Applied only if the user allows moving.

## Usage analysis (backend/app/usage.py)

- **Busy-time CPU** = 95th percentile of the hourly maximum CPU (the busiest hour of a normal day,
  ignoring rare spikes).
- **Quiet hours**: every hour is mapped to its hour of the week (0 = Monday 00:00 … 167 = Sunday 23:00).
  An hour of the week is quiet only if its maximum CPU stayed under 5% in **every** week we have.
  Quiet hours are joined into windows (the week wraps from Sunday to Monday); windows shorter than
  4 hours are ignored.
- **Verdict**: Idle (CPU under 3% in 95% of hours) → Can follow a schedule (20+ quiet hours a week)
  → Oversized (busy-time CPU under 35%) → Well used.

## Waste rules for a connected account (backend/app/rules.py)

Unattached EBS volume, unused Elastic IP, stopped instance (disks still billed), snapshot of a deleted
disk, idle instance. Each finding shows the evidence, the cost calculation and the AWS price ID (SKU).

## Data

- **Prices**: public AWS Price List files, downloaded by `scripts/fetch_prices.py` for 6 regions
  (on-demand and reserved prices, 147 instance types each). Nothing is typed in by hand.
- **Public usage data**: CPU of 8 real EC2 servers from AWS CloudWatch, 14 days (2014), from the
  [Numenta Anomaly Benchmark](https://github.com/numenta/NAB/tree/master/data/realAWSCloudwatch) (MIT licence).
  `scripts/import_public_data.py` converts it into our scan format. The dataset has no instance types,
  so m5.large is assumed (shown on screen, and you can change it in the planner).
- **Your account**: read with boto3, describe/get calls only. A test checks the scanner never calls
  anything that changes AWS.

## Run it

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app
```

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Connect an AWS account

1. Create an account (since Sept 2026 most new users can sign up with Google/GitHub without a card,
   on the Free plan).
2. Install AWS CLI v2 (2.32+) and sign in once: `aws login --profile ccx`
3. In the app, click **Connect AWS**, choose the `ccx` profile and a region.

Keys never go through the web page; boto3 reads the AWS CLI's own credentials.
Access keys from `aws configure` or a sandbox's temporary keys in environment variables also work.

## Tests

```bash
cd backend
python -m pytest
```

34 tests: the optimizer steps, usage analysis, waste rules, and the boto3 scanner against a fake AWS (`moto`).

## Project structure

```
backend/app/
  optimizer.py   the five optimization steps
  usage.py       busy-time CPU, quiet hours, verdict
  rules.py       waste rules for a scanned account
  aws.py         boto3 scanner (read-only)
  prices.py      loads saved AWS prices
  models.py      data classes
  main.py        FastAPI endpoints
backend/scripts/
  fetch_prices.py, import_public_data.py
frontend/src/
  App.jsx, ConnectDialog.jsx, pages/Home|Planner|Usage|Account.jsx
```

## Limitations

- Memory use is not measured (CloudWatch needs an agent for that), so the user enters it or we keep the current amount.
- vCPUs of different generations are treated as equal.
- On-demand Linux and Standard Reserved Instances only; no Savings Plans or Spot.
- The public dataset is from 2014 and does not include instance types or network traffic.

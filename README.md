# AWS Cost Cleaner

Students and small teams often get surprise AWS bills from things they forgot: a server left
running, a spare disk, an unused IP address, a NAT gateway. The AWS console shows one region at a
time, so something started in the wrong region is easy to miss.

This app has two parts:

1. **My AWS account** – connects to an AWS account (read with boto3), scans **every region**, lists
   everything that costs money with its monthly price, finds waste, and can clean it up after you
   confirm.
2. **Cost checker** – before you launch anything: what will a setup cost per month and how many
   days will your free credits last. Works without an AWS account.

All prices come from the official AWS Price List (17 regions), downloaded by `scripts/fetch_prices.py`.

## What it finds

| Problem | How we decide | Fix button |
|---|---|---|
| Unattached disk | disk state is "available" | back up, then delete |
| Unused Elastic IP | IP not attached to anything | release |
| Stopped server | stopped, but its disks are still billed | delete server |
| Old snapshot | the disk it came from was deleted (and no machine image uses it) | delete |
| Idle NAT gateway | sent 0 bytes in 7 days | delete |
| Empty load balancer | no servers behind it | delete |
| Idle server | CPU under 3% in 95% of hours, over 7 days | stop |
| Oversized server | CPU under 35% even at its busiest, over 7 days | shown, change type in AWS console |

The scan itself only reads (describe / get / list calls). Changes happen only in `app/fixes.py`,
only after you click a button and confirm, and only for something the latest scan flagged.

## Run it

```
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app
```

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Connect an AWS account

1. Install AWS CLI v2 (2.32 or newer) and sign in once: `aws login --profile ccx`
2. In the app click **Connect AWS** and pick the `ccx` profile.

Access keys (`aws configure`) also work. Keys are never typed into the web page.

## Test mode (no real account)

`scripts/fake_aws.py` starts a fake AWS on your computer (moto) with some waste in 5 regions.
Start the backend with `AWS_ENDPOINT_URL=http://127.0.0.1:5000`, `AWS_ACCESS_KEY_ID=test` and
`AWS_SECRET_ACCESS_KEY=test`. The app shows "Test mode" on every page.

## Tests

```
cd backend
python -m pytest
```

The tests use moto, so they need no AWS account.

## Files

```
backend/app/aws.py       scan every region (read-only)
backend/app/costs.py     monthly cost of each thing
backend/app/rules.py     what counts as waste
backend/app/fixes.py     clean-up actions
backend/app/estimate.py  cost checker
backend/app/main.py      API
frontend/src/pages/Account.jsx, Checker.jsx
```

## Limits

- NAT gateway data charges and load balancer usage charges are not included, only the hourly charge.
- Snapshot cost is an upper bound (AWS bills only the data a snapshot stores).
- The idle and oversized checks need 7 days of CPU data.
- Free-tier credits are not subtracted from the prices shown.

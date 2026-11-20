# AWS Cloud Cost Optimizer

A small web app that connects to a real AWS account (read-only, with boto3) and finds resources
you are paying for but not using. Each problem shows what we found, how much it costs per month
using real AWS prices, and the command to fix it.

## What it checks

| Rule | What it means |
|---|---|
| Unattached EBS volume | A disk not connected to any server, still billed every month |
| Unused Elastic IP | A public IP reserved but not attached (AWS charges for every public IPv4) |
| Stopped instance | Server is off, but its disks are still billed |
| Orphaned snapshot | A backup whose original disk was deleted |
| Idle instance | Running 7+ days with CPU under 3% (95% of hours) and almost no network traffic |

Prices come from the public AWS Price List, downloaded by `backend/scripts/fetch_prices.py`
(saved for ap-south-1, us-east-1, us-west-2 and eu-west-1). Every cost shows the AWS price ID (SKU) it used.

## How it works

```
React page  --->  FastAPI backend  --->  boto3  --->  your AWS account (describe/get calls only)
                        |
                        +--> rules.py + saved prices  --->  findings
                        +--> every scan saved in backend/data/scans/ (so old results open without AWS)
```

The tool never changes anything in AWS. A test checks that `aws.py` only uses describe/get/list calls.

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

Open http://localhost:5173. Without AWS connected you can still open the **sample data** (not a real account).

## Connecting a real AWS account

boto3 uses the normal AWS credentials, so any of these work:

**A. Free AWS account (no card for most new users since Sept 2026)**
1. Sign up at aws.amazon.com with Google or GitHub and choose the Free plan. AWS is rolling this out gradually, so some people may still be asked for a card.
2. Install the AWS CLI v2 (2.32 or newer) and sign in: `aws login --profile ccx`
3. Start the backend with that profile:
   - Windows: `set AWS_PROFILE=ccx` then `python -m uvicorn app.main:app`
   - Mac/Linux: `AWS_PROFILE=ccx python -m uvicorn app.main:app`

**B. AWS Builder Center sandbox (free, 8 hours, no card)**
Some Builder Center workshops give a temporary AWS account. If it gives you access keys, set
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` and `AWS_REGION` before starting
the backend. Everything is deleted after 8 hours, so the idle-server rule will not have enough data.

**C. Access keys** from `aws configure --profile ccx` (any normal account).

If your account's region has no saved prices, run `python scripts/fetch_prices.py --region <region>`.

## Testing on a real account

1. In the AWS console, create a few wasteful things: a 1 GB gp3 volume (not attached), an Elastic IP
   (not attached), a t3.micro that you stop, a snapshot of a volume you then delete.
2. Also create things that look similar but are fine: an Elastic IP attached to a running server, a
   snapshot of a disk that still exists.
3. Click **Scan now** and check the tool flags only the wasteful ones.
4. Leave one t3.micro running for 7 days, scan again, and it should appear as idle.
5. Delete everything afterwards.

All of these are tiny (a few cents a day) and come from the free plan's credits.

## Tests

```bash
cd backend
python -m pytest
```

The tests use `moto` (a fake AWS) so they run without an account.

## Limitations

- One region per scan (the region of your profile).
- On-Demand Linux prices only; free-tier credits are not subtracted.
- Snapshot cost is an upper bound: AWS bills only the data a snapshot actually stores.
- Memory usage is not checked (CloudWatch does not record it without an agent).

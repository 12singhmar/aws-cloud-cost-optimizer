# AWS Cloud Cost Optimizer — *recommendations you can check*

A read-only tool that finds wasted money in an AWS account and, unlike typical cost dashboards,
**proves how far its own advice can be trusted**.

Most cost tools stop at "you could save $X". This one adds three checks:

| Check | Question it answers | How |
|---|---|---|
| **Backtest** | "If we had run this a week ago, would the advice have held?" | Decide using week 1 of CloudWatch data only, replay the rest. Advice that would have hurt is **blocked** automatically. |
| **Waste Lab** | "Does the detector actually work on a real account?" | A script plants known waste *and decoys* in your AWS account. The answer key is hidden from the detector. Precision and recall are measured. |
| **Bill Check** | "Are the dollar estimates right?" | Each estimate is compared with the real AWS bill (CUR 2.0 export) for the same resource and hours. |

Plus a **Fleet Study** on 2.7 million real VMs (Microsoft's public Azure trace): the common rule
"average CPU < 10% → downsize" flags 170,114 long-lived VMs, and **18.2% of them would be harmed**.
This project's peak-aware rule avoids all of those while keeping 79% of the savings.

All prices come from the **official AWS Price List** (Mumbai, `ap-south-1`) with their SKUs. Nothing is typed in by hand.

## Quick start (demo, no AWS account needed)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload        # API on http://127.0.0.1:8000  (docs at /docs)
```

```bash
cd frontend
npm install
npm run dev                                     # UI on http://localhost:5173
```

The built-in **demo account is synthetic** and labelled as such on every page. Real results come from your own
account; follow **[docs/REAL_ACCOUNT_GUIDE.md](docs/REAL_ACCOUNT_GUIDE.md)** (zero money on the AWS free plan).

## Project layout

```
backend/
  app/            the product (FastAPI, read-only)
    config.py       every threshold, with the reason for it
    pricing.py      real AWS prices (from data/prices)
    costs.py        "how much does this resource cost per month?"
    rules.py        8 waste rules, each fully explained
    backtest.py     decide on week 1, check on the rest
    analyzer.py     runs everything, blocks advice that fails its backtest
    lab.py          Waste Lab scoring (precision / recall)
    billcheck.py    estimate vs real bill
    main.py         HTTP API
  scripts/        everything that touches the outside world
    fetch_prices.py     download prices from the public AWS Price List
    collect_snapshot.py READ-ONLY copy of your account -> data/snapshots/
    lab_plant.py        create known waste + decoys (the only script that creates things)
    lab_teardown.py     delete everything the lab created
    load_bill.py        CUR 2.0 billing export -> data/bills/
    fleet_study.py      the 2.7M-VM Azure study
    make_demo.py        build the synthetic demo account
  data/           prices, snapshots, lab answer keys, bills, fleet results
  tests/          37 automated tests (incl. fake-AWS tests with moto)
frontend/         React + Vite UI, hand-written SVG charts
docs/             guide, design & testing report, viva guide, IAM policies
```

## Tests

```bash
cd backend && python -m pytest -q        # 37 tests: rules, backtest, lab, bill, API, collector on fake AWS
cd frontend && npm run lint && npm run build
```

CI runs both on every push (`.github/workflows/ci.yml`).

## Documents

- [docs/REAL_ACCOUNT_GUIDE.md](docs/REAL_ACCOUNT_GUIDE.md): step-by-step: free plan, safety, lab, bill, teardown
- [docs/DESIGN_AND_TESTING.md](docs/DESIGN_AND_TESTING.md): requirements, architecture, design decisions, test plan, limitations
- [docs/VIVA_GUIDE.md](docs/VIVA_GUIDE.md): demo script and likely examiner questions with answers

## Data sources

- AWS Price List bulk files: `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/...` (public)
- Azure Public Dataset V2 (Microsoft, 2019): https://github.com/Azure/AzurePublicDataset
- Your own account, via read-only AWS APIs and the CUR 2.0 data export

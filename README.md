# AWS Cloud Cost Optimiser

A scenario-driven, explainable AWS cloud cost and utilisation analysis platform with cross-functional Change Passports and What-If simulation.

## Project Overview

**AWS Cloud Cost Optimiser** is a web-based, strictly read-only decision-support platform designed to analyse cloud spend, resource telemetry, and infrastructure metadata to surface credible, prioritised cost-optimisation opportunities.

Rather than acting as a static dashboard or recommending automated, risky changes, the system generates evidence-backed findings and transforms them into governance-ready **Change Passports** featuring:
- **Telemetry & Evidence**: Actual utilisation metrics, observation windows, and resource attributes.
- **Defensible Estimated Savings**: Calculated using documented pricing assumptions without double-counting ($40.00/mo avoidable, $12.50/mo safety snapshot, $27.50/mo net projected savings).
- **Cross-Functional Reviews**: 4 departmental governance tracks (Finance/FinOps, Engineering, Security/Compliance, SRE/Operations) with interactive user attestations.
- **Pre-Change Checklist & Rollback Runbook**: Step-by-step guidance, copyable AWS CLI commands, and automated snapshot recovery runbooks.
- **What-If Simulation Engine**: In-memory modeling of proposed changes, projecting dynamic billing reductions (-$27.50/mo or -$40.00/mo) across dashboard KPIs with full undo capability.
- **Dark & Light Theme**: Universal theme support with smooth transitions, system preference detection, and `localStorage` persistence.
- **Read-Only Safety**: The system never modifies, stops, or terminates live AWS resources. All data is simulated deterministically and labeled as such.

---

## Architectural Layers

```
                      +---------------------------------------+
                      |       React Dashboard (Vite)          |
                      |  - Dark/Light Theme Switcher          |
                      |  - Header Scenario Selector           |
                      |  - Executive KPI Cards                |
                      |  - Priority Findings List             |
                      |  - Slide-out Detail Drawer            |
                      |  - Cross-Functional Change Passport   |
                      |  - Interactive What-If Simulation     |
                      +-------------------+-------------------+
                                          | HTTP REST
                                          v
                      +---------------------------------------+
                      |         FastAPI Route Layer           |
                      |  - /api/health                        |
                      |  - /api/scenarios                     |
                      |  - /api/dashboard?scenario=           |
                      |  - /api/recommendations?              |
                      |  - /api/resources?                    |
                      |  - /api/change-passport/{rec_id}      |
                      |  - /api/change-passport/simulate      |
                      |  - /api/change-passport/simulate/undo |
                      |  - /api/change-passport/attest        |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |       Analysis Engine & Rules         |
                      |  - EC2 Low CPU Rightsizing Rule       |
                      |  - Unattached EBS gp3 Rule            |
                      |  - Idle Compute Resource Rule         |
                      |  - S3 Storage Lifecycle Rule          |
                      |  - Deduplication & Financial Traces   |
                      |  - Change Passport Generator          |
                      |  - In-Memory What-If Simulation       |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |          CloudProvider Base           |
                      |      (Abstract Provider Contract)     |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |           Mock AWS Provider           |
                      |      (Deterministic Scenarios)        |
                      +---------------------------------------+
```

### 1. Abstract Cloud Provider Interface (`app/providers/base.py`)
Decouples resource data acquisition from optimization logic. Exposes `get_resources()`, `get_metrics()`, and `get_historical_cost_trend()`. This enables switching from simulated telemetry to a live read-only AWS SDK (boto3) provider in the future without altering analysis rules.

### 2. Independent Analysis Engine (`app/analysis/engine.py`)
Consumes provider data, evaluates active rules, prevents duplicate findings, generates comprehensive Change Passports, and manages in-memory What-If simulations with dynamic spend adjustments and undo capability.

### 3. Modular Optimisation Rules (`app/analysis/rules.py`)
Independently testable rule implementations with configurable thresholds and strict validation preconditions.

---

## Optimisation Rules

| Rule | Service | Evaluation Criteria | Output & Verification |
|------|---------|---------------------|-----------------------|
| **1. EC2 Rightsizing** | EC2 | Avg CPU < 10.0% and Peak CPU < 30.0% over ≥ 7 days. Excludes completely idle instances. | Proposes rightsizing to smaller instance tier (e.g. `c5.xlarge` → `c5.large`, saving $61.20/mo). Advises memory auditing during peak traffic. |
| **2. Unattached EBS Volume** | EBS | Volume state is `available` (unattached) for ≥ 7 days with zero active I/O. | Identifies avoidable storage and provisioned IOPS fees ($40.00/mo waste). Recommends creating an EBS snapshot before deletion (yielding $27.50/mo net savings). |
| **3. Idle Compute Resource** | EC2 | Avg CPU < 2.0%, Peak CPU < 5.0%, and Network throughput < 5 KB/s over ≥ 7 days. | Flags inactive/abandoned instances (`m5.large`, saving $78.00/mo). Mutual exclusion ensures idle instances do not receive conflicting rightsizing findings. |
| **4. Rapid S3 Storage Growth** | S3 | Identifies unmanaged stale objects (>90 days old) in Standard tier lacking lifecycle transitions. | Proposes automated transition to Glacier Instant Retrieval ($0.019/GB delta, saving $155.80/mo on 8,200 GB stale data). |

---

## The Change Passport Workflow

The **Change Passport** elevates cost recommendations into explainable, cross-functional engineering proposals. It addresses the realities of organizational decision-making:

### 1. Transparent Pricing & Financial Trace
- **Avoidable Monthly Waste**: $40.00/mo ($480.00/yr) for unattached 250 GB gp3 volume (`vol-0a7f82c9e4b1a3d5e`).
  * Base Storage: 250 GB × $0.080/GB-month = $20.00/mo
  * Provisioned IOPS: 3,000 IOPS above 3,000 baseline × $0.005 = $15.00/mo
  * Provisioned Throughput: 125 MB/s above 125 MB/s baseline × $0.040 = $5.00/mo
- **Safety Snapshot Overhead**: 250 GB × $0.050/GB-month = $12.50/mo.
- **Net Projected Recurring Savings**: $40.00 - $12.50 = **$27.50/mo** ($330.00/yr).
- **Realized Savings Honesty**: Transparently labeled as *"Unavailable — requires post-change billing telemetry"*.

### 2. Cross-Functional Governance Tracks
- **Finance / FinOps**: Verifies cost center tagging (`CreatedBy: migration-job`) and validates positive return on investment.
- **Engineering**: Verifies data migration ingestion completeness and confirms zero application mount dependencies.
- **Security / Compliance**: Audits data classification policies (PII/compliance checks) and preserves KMS encryption key access.
- **SRE / Operations**: Verifies automated pre-deletion snapshot hooks and confirms 30-day detachment history via AWS CloudTrail.
- **Interactive Attestation**: Engineers can check off verification steps directly in the UI, updating the passport state from *Needs review* to *Ready for simulation*.

### 3. Pre-Change Checklist & Rollback Runbook
- 5 sequential, numbered verification steps with copyable AWS CLI commands.
- Guaranteed disaster recovery runbook detailing snapshot restoration in < 15 minutes (`aws ec2 create-volume --snapshot-id snap-sim-0a7f82c9...`).

### 4. What-If Simulation Engine
- Choose between proposed decommission actions:
  * **Option A (Recommended)**: Snapshot and Delete Volume (Net: $27.50/mo savings, Low risk, High reversibility).
  * **Option B**: Immediate Delete Without Snapshot (Net: $40.00/mo savings, High risk, Irreversible).
  * **Option C**: Retain and Tag (Net: $0.00/mo savings).
- Executing a simulation dynamically updates scenario monthly spend ($910.35 → $882.85/mo), marks resource state as decommissioned, and records an illustrative snapshot.
- Full **Undo Simulation** capability resets the dashboard back to the unsimulated baseline.

---

## Deterministic Evaluation Scenarios

Accessible via the dashboard header scenario selector:

1. **High Cost & Resource Waste (`high-cost-waste`)**
   - **Environment**: Multiple compute and storage inefficiencies ($910.35/mo baseline spend).
   - **Resources**: Oversized EC2 instance (`c5.xlarge`, saving $61.20/mo), idle EC2 instance (`m5.large`, saving $78.00/mo), unattached provisioned EBS volume (`gp3`, saving $40.00/mo avoidable), rapid-growth S3 telemetry bucket (saving $155.80/mo), alongside healthy web hosts and RDS databases.
   - **Expected Result**: 4 prioritised, evidence-backed findings totaling **$335.00/mo** in potential savings. Full Change Passport available for the unattached EBS volume.

2. **Healthy Cloud Environment (`healthy-environment`)**
   - **Environment**: Well-architected infrastructure with appropriately sized compute (55-75% CPU), all volumes attached, and active S3 lifecycle policies.
   - **Expected Result**: **0 findings**. Clean empty state confirming workloads meet efficiency benchmarks.

3. **Mixed Environment (`mixed-environment`)**
   - **Environment**: Production workload with a single oversized staging host (`m5.2xlarge`) and an unattached volume left behind after migration.
   - **Expected Result**: **2 differentiated findings** (1 High priority unattached EBS, 1 Medium priority rightsizing).

4. **Insufficient Data & Observability Gaps (`insufficient-data`)**
   - **Environment**: Newly launched resources (< 7 days observation window) and missing CloudWatch metrics.
   - **Expected Result**: **0 false-positive recommendations**. Metric-dependent rules are cleanly suppressed rather than falsely assuming zero utilisation. Transparent data-quality warnings alert the operator to observability gaps.

---

## API Reference

Base URL: `http://127.0.0.1:8000`

### `GET /api/health`
Returns system health and service version.

### `GET /api/scenarios`
Lists all available deterministic test scenarios.

### `GET /api/dashboard?scenario={scenario_id}`
Returns aggregated executive KPIs, 6-month cost trends, service spend distributions, prioritised recommendations, and recent activity. Dynamically factors in active What-If simulations.

### `GET /api/recommendations?scenario={scenario_id}`
Returns generated recommendations for the specified scenario.

### `GET /api/resources?scenario={scenario_id}`
Returns the raw cloud resource inventory for the specified scenario.

### `GET /api/change-passport/{recommendation_id}?scenario={scenario_id}`
Returns the comprehensive, cross-functional Change Passport with evidence, calculation traces, 4 departmental reviews, checklist, and proposed actions.

### `POST /api/change-passport/simulate`
Executes an in-memory What-If simulation for a selected action, returning projected billing and simulated resource state.
```json
{
  "scenario_id": "high-cost-waste",
  "recommendation_id": "rec-ebs-vol-0a7f82c9e4b1a3d5e",
  "action_id": "snapshot_and_delete"
}
```

### `POST /api/change-passport/simulate/undo`
Reverts an active simulation, restoring pre-change baseline metrics.

### `POST /api/change-passport/attest`
Records user attestation for a departmental review item.
```json
{
  "scenario_id": "high-cost-waste",
  "check_id": "eng-1",
  "attested": true
}
```

---

## Running the Application Locally

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 1. Backend Startup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
API docs available at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 2. Frontend Startup
```powershell
cd frontend
npm install
npm run dev
```
Dashboard available at: [http://localhost:5173](http://localhost:5173).

---

## Running Automated Tests

### Backend Unit Test Suite (21 Tests)
```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```
Verifies:
- All 4 optimization rules (positive, negative, boundary conditions, metric absence)
- Mutual exclusion between idle and rightsizing rules
- gp3 formula precision ($40.00/mo waste, $12.50 snapshot)
- API endpoint contracts across all 4 scenarios
- Change Passport generation, attestation toggling, simulation execution, and undo flow

### Frontend Lint & Production Build
```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```

---

## Demonstration Walkthrough

1. **Open [http://localhost:5173](http://localhost:5173)**:
   - Toggle between **Dark Mode** and **Light Mode** using the sun/moon button in the header. Notice instantaneous CSS variable adaptation.
2. **Inspect High Cost & Resource Waste**:
   - Review executive KPIs ($910.35/mo monthly cost, $335.00/mo potential savings).
   - In Priority Findings, click on the **"Delete unattached EBS volume (data-analytics-temp-backup)"** card.
3. **Explore the Recommendation Drawer & Open Change Passport**:
   - Slide-out drawer displays evidence and human verification guidance.
   - Click the prominent **"Open Change Passport Workspace"** button.
4. **Interact with the Change Passport**:
   - **Financials Tab**: Trace the $40.00/mo waste formula (250 GB gp3 + 3,000 extra IOPS + 125 MB/s extra throughput) and the $12.50/mo snapshot overhead.
   - **Reviews Tab**: View the 4 departmental tracks. Click the attestation checkboxes for Engineering and Security. Notice status updates dynamically.
   - **Checklist Tab**: Inspect the 5-step validation procedure and the copyable AWS CLI rollback snippet.
   - **Simulation Tab**: Select *"Create Safety Snapshot, then Delete Volume"* and click **"Run What-If Simulation"**.
5. **Observe Dynamic Dashboard Updates**:
   - Close the modal. Notice the main dashboard monthly cost has decreased dynamically from **$910.35/mo** to **$882.85/mo** (-$27.50/mo reduction).
   - Recent activity logs display the active simulation event.
6. **Undo Simulation**:
   - Reopen the Change Passport, go to What-If Simulation, and click **"Undo Simulation"**.
   - Notice the spend immediately restores to the $910.35/mo baseline.
7. **Switch Scenarios**:
   - Switch to **Healthy Cloud Environment** to confirm 0 findings.
   - Switch to **Insufficient Data** to observe observability gap notices and suppression of false findings.

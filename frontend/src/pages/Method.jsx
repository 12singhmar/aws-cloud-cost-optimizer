import { Card, PageHead } from '../ui.jsx'

const STEPS = [
  ['Collect', 'A read-only script copies the account into a snapshot file: servers, disks, IPs, backups, buckets, 14 days of hourly CPU and network.'],
  ['Price', 'Prices come from the official AWS Price List files, each with its SKU. Nothing is typed in by hand.'],
  ['Detect', '8 simple rules, each with written thresholds. Anything without enough data gets a notice, never a guess.'],
  ['Backtest', 'Decide on week 1 only, replay the rest. Advice that would have hurt is blocked.'],
  ['Verify', 'Waste Lab scores the detector on planted waste + decoys. Bill Check compares estimates with the real bill.'],
]

export default function Method({ rules, prices }) {
  return (
    <>
      <PageHead title="How it works">
        A strictly read-only tool. It never changes your account; it tells you what to check and how to fix it.
      </PageHead>
      <div className="pipeline">
        {STEPS.map(([t, d], k) => (
          <div className="step" key={t}><span className="n">STEP {k + 1}</span><b>{t}</b><p>{d}</p></div>
        ))}
      </div>
      <Card title="The rules" sub="all thresholds live in backend/app/config.py">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Rule</th><th>Fires when</th></tr></thead>
            <tbody>{rules.map((r) => <tr key={r.id}><td><b>{r.name}</b><div className="mono muted">{r.id}</div></td><td className="small">{r.test}</td></tr>)}</tbody>
          </table>
        </div>
      </Card>
      {prices && (
        <Card title="Price book" sub={`${prices.region} · AWS Price List version ${prices.version}`}>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Price</th><th className="num">USD</th><th>Unit</th><th>SKU</th></tr></thead>
              <tbody>{prices.other.map((p) => <tr key={p.key}><td className="small">{p.description}</td><td className="num">{p.usd}</td><td className="small">{p.unit}</td><td className="mono small">{p.sku}</td></tr>)}</tbody>
            </table>
          </div>
          <p className="small muted" style={{ marginTop: 8 }}>Plus {prices.instance_types} EC2 instance types. Refresh with <span className="mono">python scripts/fetch_prices.py</span>.</p>
        </Card>
      )}
      <Card title="What this tool does not do (on purpose)">
        <ul className="steps small">
          <li>No changes to AWS. No write permissions are needed to run it.</li>
          <li>No memory-based rightsizing: CloudWatch does not record memory without an agent, so rightsizing is capped at Medium confidence.</li>
          <li>No Savings Plans / Reserved Instance advice: that needs months of history a student account does not have.</li>
          <li>No made-up savings: where usage patterns are unknown (S3 lifecycle) the saving is shown as “not estimated”.</li>
        </ul>
      </Card>
    </>
  )
}

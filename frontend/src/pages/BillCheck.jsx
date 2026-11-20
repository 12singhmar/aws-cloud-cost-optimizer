import { usd } from '../api.js'
import { Card, Empty, PageHead, Stat, SyntheticBanner } from '../ui.jsx'

function ErrorCell({ v }) {
  if (v === null) return <span className="muted">billed $0</span>
  const ok = Math.abs(v) <= 2
  return <span className={`badge ${ok ? 'good' : 'bad'}`}>{ok ? '✓' : '!'} {v > 0 ? '+' : ''}{v}%</span>
}

export default function BillCheck({ bill }) {
  if (!bill?.available) {
    return (
      <>
        <PageHead title="Bill Check" />
        <Empty title="No bill loaded for this snapshot">
          Turn on the CUR 2.0 data export (hourly, with resource IDs), then run
          <span className="mono"> scripts/load_bill.py --snapshot &lt;id&gt;</span>. AWS needs up to 24 hours to deliver the first file.
        </Empty>
      </>
    )
  }
  return (
    <>
      <PageHead title="Bill Check">
        Most cost tools stop at an estimate. Here we compare each estimate with what AWS actually charged for the
        same resource over the same hours, using the official billing export.
      </PageHead>
      {bill.synthetic && <SyntheticBanner what="bill" />}
      <div className="grid grid-4">
        <Stat label="Resources matched" value={bill.matched} hint="present in both snapshot and bill" />
        <Stat label="Mean absolute error" value={`${bill.mean_abs_error_pct ?? '—'}%`} hint="lower is better" />
        <Stat label="Estimated" value={usd(bill.total_estimated, 2)} hint="our prices × billed hours" />
        <Stat label="Actually billed" value={usd(bill.total_actual, 2)} hint="usage charges, before credits" />
      </div>
      <Card title="Estimate vs bill, per resource" sub={bill.source}>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Resource</th><th>Type</th><th className="num">Hours</th><th className="num">Estimated</th><th className="num">Billed</th><th>Error</th><th>Why</th></tr></thead>
            <tbody>
              {bill.rows.map((r) => (
                <tr key={r.resource_id}>
                  <td><span className="mono">{r.resource_id}</span>{r.name && <div className="muted small">{r.name}</div>}</td>
                  <td className="small">{r.kind}</td>
                  <td className="num">{r.hours}</td>
                  <td className="num">{usd(r.estimated_usd, 4)}</td>
                  <td className="num">{usd(r.actual_usd, 4)}</td>
                  <td><ErrorCell v={r.error_pct} /></td>
                  <td className="small">{r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Reading the gaps">
        <p className="small">Expect snapshots to come out high: we price a snapshot at its full volume size, but AWS
          bills only the blocks actually stored. That is why snapshot savings are labelled an <b>upper bound</b> on the
          Findings page. {bill.synthetic
            ? 'In this demo the gap is made up; the real bill check measures it.'
            : 'The rows above show by how much for this account.'}</p>
      </Card>
    </>
  )
}

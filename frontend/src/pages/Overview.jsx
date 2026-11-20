import { HBars } from '../charts.jsx'
import { pct, usd } from '../api.js'
import { Card, PageHead, Stat, Verdict } from '../ui.jsx'

export default function Overview({ analysis, lab, bill, go }) {
  const s = analysis.summary
  const top = analysis.findings.filter((f) => f.status === 'active').slice(0, 5)
  return (
    <>
      <PageHead title="Overview">
        What this account costs per month at list price, what looks wasteful, and how far each answer can be
        trusted. Every number links back to its evidence.
      </PageHead>

      <div className="grid grid-4">
        <Stat label="Monthly run-rate (list price)" value={usd(s.monthly_run_rate)}
          hint={`${s.resources_scanned} resources scanned, before free-tier credits`} />
        <Stat label="Potential savings / month" value={usd(s.potential_savings)}
          hint={`${pct(s.savings_share)} of run-rate`} />
        <Stat label="Findings" value={s.findings}
          hint={`${s.by_priority.High} high · ${s.by_priority.Medium} medium · ${s.by_priority.Low} low`} />
        <Stat label="Blocked by backtest" value={s.blocked}
          hint="Advice that would have hurt when replayed on history" />
      </div>

      <div className="grid grid-2">
        <Card title="Where the money goes" sub="estimated monthly cost by type">
          <HBars rows={analysis.spend_by_type.map((r) => ({ label: r.type, value: r.usd }))} format={(v) => usd(v)} />
        </Card>
        <Card title="Can we trust these results?" sub="three independent checks">
          <dl className="kv">
            <dt>Waste Lab</dt>
            <dd>{lab?.available
              ? <>precision <b>{pct(lab.precision)}</b>, recall <b>{pct(lab.recall)}</b> on {lab.items.length} planted resources {lab.synthetic && <span className="muted">(demo)</span>}</>
              : <span className="muted">no lab for this snapshot</span>}</dd>
            <dt>Bill check</dt>
            <dd>{bill?.available
              ? <>mean error <b>{bill.mean_abs_error_pct}%</b> over {bill.matched} resources {bill.synthetic && <span className="muted">(demo)</span>}</>
              : <span className="muted">no bill export loaded</span>}</dd>
            <dt>Backtest</dt>
            <dd>{analysis.backtests.length
              ? <>{analysis.backtests.filter((b) => b.verdict === 'Held up').length} held up, {analysis.backtests.filter((b) => b.verdict === 'Would have hurt').length} would have hurt (of {analysis.backtests.length} instances)</>
              : <span className="muted">needs 10+ days of metrics</span>}</dd>
            <dt>Prices</dt>
            <dd>AWS Price List {analysis.pricing.region}, version {analysis.pricing.version}</dd>
          </dl>
          <div className="pill-row" style={{ marginTop: 14 }}>
            <button className="btn" onClick={() => go('lab')}>Open Waste Lab</button>
            <button className="btn" onClick={() => go('bill')}>Open Bill Check</button>
            <button className="btn" onClick={() => go('backtest')}>Open Backtest</button>
          </div>
        </Card>
      </div>

      <Card title="Top findings" sub="sorted by priority, then saving">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Finding</th><th>Priority</th><th>Confidence</th><th>Backtest</th><th className="num">Saving / month</th></tr></thead>
            <tbody>
              {top.map((f) => (
                <tr key={f.id} style={{ cursor: 'pointer' }} onClick={() => go('findings', f.id)}>
                  <td><b>{f.title}</b><div className="muted small">{f.rule_name}</div></td>
                  <td><span className={`badge p-${f.priority}`}>{f.priority}</span></td>
                  <td>{f.confidence}</td>
                  <td>{f.backtest ? <Verdict value={f.backtest.verdict} /> : <span className="muted">—</span>}</td>
                  <td className="num">{f.monthly_savings === null ? 'not estimated' : usd(f.monthly_savings)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {analysis.notices.length > 0 && (
        <Card title="What we could not judge" sub="shown instead of guessing">
          <ul className="steps">{analysis.notices.map((n, k) => <li key={k}>{n.text}</li>)}</ul>
        </Card>
      )}
    </>
  )
}

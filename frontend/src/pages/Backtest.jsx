import { BacktestChart } from '../charts.jsx'
import { Card, Empty, PageHead, Verdict } from '../ui.jsx'

export default function Backtest({ analysis }) {
  const rows = analysis.backtests
  return (
    <>
      <PageHead title="Backtest">
        “If we had run this tool a week ago, would its advice have held?” For every running instance we decide
        using only the first 7 days of CloudWatch data, then replay the hours after that. Advice that would have
        hurt is blocked automatically.
      </PageHead>
      {!rows.length && <Empty title="Not enough history yet">The backtest needs at least 10 days of hourly metrics (7 to decide + 3 to check).</Empty>}
      <div className="grid grid-2">
        {rows.map((b) => (
          <Card key={b.instance} title={b.name || b.instance} sub={`${b.type} · ${b.train_hours} h + ${b.test_hours} h`}>
            <dl className="kv" style={{ marginBottom: 10 }}>
              <dt>Advice from week 1</dt><dd><b>{b.advice_week1}</b></dd>
              <dt>What happened</dt><dd><Verdict value={b.verdict} /></dd>
            </dl>
            <p className="small" style={{ marginBottom: 10 }}>{b.detail}</p>
            {b.series ? <BacktestChart series={b.series} /> : <p className="muted small">No change was advised, so there is nothing to replay.</p>}
          </Card>
        ))}
      </div>
    </>
  )
}

import { FleetScatter, StackedBars } from '../charts.jsx'
import { int, pct, usd } from '../api.js'
import { Card, Empty, PageHead, Stat } from '../ui.jsx'

export default function Fleet({ fleet }) {
  if (!fleet?.available) return <><PageHead title="Fleet Study" /><Empty title="Not computed yet">Run <span className="mono">python scripts/fleet_study.py</span>.</Empty></>
  const n = fleet.naive, p = fleet.peak_aware
  return (
    <>
      <PageHead title="Fleet Study: 2.7 million real VMs">
        Many cost tools say “average CPU under 10% → downsize”. We tested that advice on Microsoft's public Azure
        trace (real production VMs, 30 days) and compared it with this project's peak-aware rule.
      </PageHead>
      <div className="grid grid-4">
        <Stat label="VMs in the dataset" value={int(fleet.vms_total)} hint={`${int(fleet.vms_long_lived)} lived 7+ days (studied)`} />
        <Stat label="Flagged by “avg < 10%”" value={int(n.flagged)} hint="the common rule" />
        <Stat label="…of which would be harmed" value={pct(n.harm_rate, 1)} hint={`${int(n.harmful)} VMs maxed out after halving`} />
        <Stat label="Savings kept by our rule" value={pct(p.savings_retained)} hint="while avoiding every harmful case" />
      </div>
      <div className="grid grid-2">
        <Card title="The lower the average, the safer — but not near 10%" sub="VMs flagged by the naive rule, by average CPU">
          <StackedBars rows={fleet.harm_by_avg_cpu} />
        </Card>
        <Card title="Average hides the busy hours" sub={`random sample of ${int(fleet.scatter_sample.points.length)} flagged VMs`}>
          <FleetScatter points={fleet.scatter_sample.points} />
        </Card>
      </div>
      <Card title="Method, in plain words">
        <ol className="steps">
          <li>Keep VMs that lived at least 7 days ({int(fleet.vms_long_lived)}).</li>
          <li>Halving the vCPUs roughly doubles CPU %. For each VM the dataset gives the 95th percentile of its
            5-minute <b>max</b> CPU (“busy-time CPU”).</li>
          <li><b>Harmed</b> = busy-time CPU × 2 &gt; 100%: the smaller VM would be maxed out for at least ~1 hour
            12 min every day.</li>
          <li>Naive rule: avg &lt; 10%. Our rule: avg &lt; 10% <b>and</b> busy-time &lt; 40% (stays under 80% after halving).</li>
          <li>Savings priced with AWS m5 Mumbai rates: {usd(fleet.price_per_vcpu_hour_usd, 4)} per vCPU-hour.</li>
        </ol>
        <p className="small muted" style={{ marginTop: 10 }}>
          Honest limit: our rule has zero harmed VMs here partly by construction, because it uses the same p95
          measure. Its out-of-sample test is the Backtest on hourly CloudWatch data. Source: {fleet.dataset}.
        </p>
      </Card>
      <Card title="Side by side">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Rule</th><th className="num">VMs flagged</th><th className="num">Harmed</th><th className="num">Monthly saving if all applied</th></tr></thead>
            <tbody>
              <tr><td>{n.rule}</td><td className="num">{int(n.flagged)}</td><td className="num">{int(n.harmful)} ({pct(n.harm_rate, 1)})</td><td className="num">{usd(n.monthly_savings_usd_if_all_applied)}</td></tr>
              <tr><td>{p.rule}</td><td className="num">{int(p.flagged)}</td><td className="num">0</td><td className="num">{usd(p.monthly_savings_usd_if_all_applied)}</td></tr>
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

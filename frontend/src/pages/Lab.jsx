import { pct } from '../api.js'
import { Card, Empty, PageHead, Stat, SyntheticBanner, Verdict } from '../ui.jsx'

export default function Lab({ lab }) {
  if (!lab?.available) {
    return (
      <>
        <PageHead title="Waste Lab" />
        <Empty title="No lab for this snapshot">
          Plant known waste with <span className="mono">scripts/lab_plant.py</span>, wait 10 days, then collect with
          <span className="mono"> --lab &lt;id&gt;</span>. See docs/REAL_ACCOUNT_GUIDE.md.
        </Empty>
      </>
    )
  }
  const c = lab.counts
  return (
    <>
      <PageHead title="Waste Lab">
        We planted resources whose correct answer we already know: real waste the tool must find, and decoys that
        fool naive tools. The answer key is kept apart from the detector, so this is a fair exam.
      </PageHead>
      {lab.synthetic && <SyntheticBanner what="lab" />}
      <div className="grid grid-4">
        <Stat label="Precision" value={pct(lab.precision)} hint="When it says waste, how often it is right" />
        <Stat label="Recall" value={pct(lab.recall)} hint="How much of the planted waste it found" />
        <Stat label="Accuracy" value={pct(lab.accuracy)} hint={`${lab.items.length} planted resources`} />
        <Stat label="Decoys correctly ignored" value={`${c.TN} / ${c.TN + c.FP}`} hint="Look wasteful, are not" />
      </div>
      <div className="grid grid-2">
        <Card title="Confusion matrix" sub="planted truth vs tool output">
          <div className="matrix">
            <span />
            <span className="hd">Tool flagged it</span>
            <span className="hd">Tool left it</span>
            <span className="hd">Waste</span>
            <div className="cell ok"><b>{c.TP}</b>true positive</div>
            <div className="cell err"><b>{c.FN}</b>false negative</div>
            <span className="hd">Decoy</span>
            <div className="cell err"><b>{c.FP}</b>false positive</div>
            <div className="cell ok"><b>{c.TN}</b>true negative</div>
          </div>
        </Card>
        <Card title="Why decoys matter" sub="the hard cases">
          <p className="small">A tool that flags everything gets 100% recall and is useless. Decoys test the opposite
            mistake. Examples: a server with ~0% CPU but steady network traffic (a proxy, not idle), and a server that
            is quiet for a week and then runs a nightly job. The second one is only caught by the backtest.</p>
          {lab.other_findings.length > 0 && (
            <p className="small muted" style={{ marginTop: 10 }}>{lab.other_findings.length} other finding(s) in this account are outside the lab and not scored.</p>
          )}
        </Card>
      </div>
      <Card title="Every planted resource">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Resource</th><th>Planted as</th><th>Why</th><th>Expected</th><th>Tool said</th><th>Result</th></tr></thead>
            <tbody>
              {lab.items.map((i) => (
                <tr key={i.resource_id}>
                  <td><span className="mono">{i.resource_id}</span><div className="muted small">{i.kind}</div></td>
                  <td>{i.role === 'waste' ? 'Waste' : 'Decoy'}</td>
                  <td className="small">{i.why}</td>
                  <td className="small mono">{i.expected_rule || (i.must_not?.length ? `not ${i.must_not.join(', ')}` : 'nothing')}</td>
                  <td className="small mono">{i.flagged_by.length ? i.flagged_by.join(', ') : 'nothing'}</td>
                  <td><Verdict value={i.outcome} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

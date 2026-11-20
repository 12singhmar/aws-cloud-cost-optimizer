export default function Home({ overview, status, go, onConnect }) {
  return (
    <div className="stack">
      <div className="panel hero-panel">
        <h1>Spend less on AWS</h1>
        <p className="muted">
          Tell us what your servers do, or let us read their real CPU history, and we work out the cheapest
          setup that still does the job. Every number comes from the official AWS price list.
        </p>
      </div>

      <div className="cards3">
        <button className="card-link" onClick={() => go('planner')}>
          <b>Cost Planner</b>
          <span className="muted">Enter a server and how it is used. Get the cheapest plan with every step explained.</span>
          <span className="tag-line">No AWS account needed</span>
        </button>
        <button className="card-link" onClick={() => go('usage')}>
          <b>Usage Analysis</b>
          <span className="muted">Find idle, oversized and part-time servers from real CloudWatch CPU data.</span>
          <span className="tag-line">Works with the public dataset</span>
        </button>
        <button className="card-link" onClick={() => (status?.connected ? go('account') : onConnect())}>
          <b>{status?.connected ? 'My AWS Account' : 'Connect AWS'}</b>
          <span className="muted">Scan your own account for wasted disks, IPs, snapshots and servers.</span>
          <span className="tag-line">{status?.connected ? `Connected: ${status.account}` : 'Read-only'}</span>
        </button>
      </div>

      <div className="panel">
        <h2>How it works</h2>
        <ol className="how">
          <li><b>Collect.</b> CPU history comes from CloudWatch (your account, or a public dataset of real EC2 servers). Prices come from the AWS Price List.</li>
          <li><b>Analyse.</b> For each server we find its busy-time CPU, its average CPU and the hours of the week when it is always quiet.</li>
          <li><b>Optimise.</b> Five steps, one after another: rightsize, switch to ARM, schedule or reserve, change disk type, change region.</li>
          <li><b>Explain.</b> Each step shows the maths and the AWS prices it used, so you can check it yourself.</li>
        </ol>
      </div>

      {overview && (
        <p className="muted small">
          Price data: {overview.instance_types} instance types in {overview.regions.length} regions
          ({overview.regions.map((r) => r.name).join(', ')}), AWS Price List version {overview.price_list_version}.
        </p>
      )}
    </div>
  )
}

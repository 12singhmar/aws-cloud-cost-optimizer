export default function Home({ overview, status, go, onConnect }) {
  return (
    <div className="stack">
      <div className="intro">
        <h1>Cloud Cost Optimizer</h1>
        <p className="muted">
          Finds a cheaper way to run your AWS servers using real AWS prices and CPU usage.
        </p>
      </div>

      <div className="cards3">
        <button className="card-link" onClick={() => go('planner')}>
          <b>Cost Planner</b>
          <span className="muted">Enter a server and how much it is used. See the cheapest plan and how we got it.</span>
          <small>No AWS account needed</small>
        </button>
        <button className="card-link" onClick={() => go('usage')}>
          <b>Usage Analysis</b>
          <span className="muted">Check CPU history to find idle servers, oversized servers and quiet hours.</span>
          <small>Uses real CloudWatch data</small>
        </button>
        <button className="card-link" onClick={() => (status?.connected ? go('account') : onConnect())}>
          <b>{status?.connected ? 'My AWS Account' : 'Connect AWS'}</b>
          <span className="muted">Scan your account for unused disks, IPs, snapshots and servers.</span>
          <small>{status?.connected ? status.account : 'Read-only access'}</small>
        </button>
      </div>

      {overview && (
        <p className="muted small">
          Prices for {overview.instance_types} instance types in {overview.regions.length} regions,
          AWS Price List version {overview.price_list_version}.
        </p>
      )}
    </div>
  )
}

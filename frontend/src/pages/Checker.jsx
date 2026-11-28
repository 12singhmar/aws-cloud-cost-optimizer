import { useEffect, useState } from 'react'
import { api, money } from '../api.js'

const NEW_SERVER = { instance_type: 't3.micro', count: 1, hours_per_day: 24, days_per_week: 7, disk_gb: 8, disk_type: 'gp3', public_ip: true }

export default function Checker({ regions }) {
  const [setup, setSetup] = useState({ region: 'ap-south-1', servers: [NEW_SERVER], nat_gateways: 0, load_balancers: 0, credits_usd: 100 })
  const [types, setTypes] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.instanceTypes(setup.region).then(setTypes).catch(() => setTypes([]))
  }, [setup.region])

  // work out the cost again a moment after the user stops typing
  useEffect(() => {
    const timer = setTimeout(() => {
      api.estimate(setup).then((r) => { setResult(r); setError(null) }).catch((e) => setError(e.message))
    }, 300)
    return () => clearTimeout(timer)
  }, [setup])

  function setField(key, value) {
    setSetup({ ...setup, [key]: value })
  }

  function setServer(index, key, value) {
    const servers = setup.servers.map((s, i) => (i === index ? { ...s, [key]: value } : s))
    setSetup({ ...setup, servers })
  }

  function number(e, min, max) {
    const n = e.target.value === '' ? min : Number(e.target.value)
    return Math.min(max, Math.max(min, n))
  }

  return (
    <>
      <h1>Cost checker</h1>
      <p className="muted">What will a setup cost per month, and how long will your free credits last? Uses the official AWS price list. No AWS account needed.</p>

      <div className="checker">
        <div>
          <label>Region{' '}
            <select value={setup.region} onChange={(e) => setField('region', e.target.value)}>
              {regions.map((r) => <option key={r}>{r}</option>)}
            </select>
          </label>
          <label>Free credits ($){' '}
            <input type="number" value={setup.credits_usd} onChange={(e) => setField('credits_usd', number(e, 0, 100000))} />
          </label>

          <datalist id="types">
            {types.map((t) => <option key={t.type} value={t.type}>{t.vcpu} vCPU, {t.memory_gib} GiB</option>)}
          </datalist>

          {setup.servers.map((s, i) => (
            <div className="server" key={i}>
              <b>Server {i + 1}</b>
              {setup.servers.length > 1 && (
                <button className="small" onClick={() => setField('servers', setup.servers.filter((_, j) => j !== i))}> Remove</button>
              )}
              <table>
                <tbody>
                  <tr><td>Instance type</td><td><input list="types" value={s.instance_type} onChange={(e) => setServer(i, 'instance_type', e.target.value.trim())} /></td></tr>
                  <tr><td>How many</td><td><input type="number" value={s.count} onChange={(e) => setServer(i, 'count', number(e, 1, 100))} /></td></tr>
                  <tr><td>Hours a day</td><td><input type="number" value={s.hours_per_day} onChange={(e) => setServer(i, 'hours_per_day', number(e, 1, 24))} /></td></tr>
                  <tr><td>Days a week</td><td><input type="number" value={s.days_per_week} onChange={(e) => setServer(i, 'days_per_week', number(e, 1, 7))} /></td></tr>
                  <tr><td>Disk (GB)</td><td><input type="number" value={s.disk_gb} onChange={(e) => setServer(i, 'disk_gb', number(e, 0, 16000))} />{' '}
                    <select value={s.disk_type} onChange={(e) => setServer(i, 'disk_type', e.target.value)}><option>gp3</option><option>gp2</option></select></td></tr>
                  <tr><td>Public IP</td><td><input type="checkbox" checked={s.public_ip} onChange={(e) => setServer(i, 'public_ip', e.target.checked)} /></td></tr>
                </tbody>
              </table>
            </div>
          ))}
          <button onClick={() => setField('servers', [...setup.servers, NEW_SERVER])}>Add server</button>

          <label>NAT gateways{' '}
            <input type="number" value={setup.nat_gateways} onChange={(e) => setField('nat_gateways', number(e, 0, 20))} />
          </label>
          <label>Load balancers{' '}
            <input type="number" value={setup.load_balancers} onChange={(e) => setField('load_balancers', number(e, 0, 20))} />
          </label>
        </div>

        <div>
          {error && <p className="error">{error}</p>}
          {result && (
            <>
              <table className="summary">
                <tbody>
                  <tr><td>Cost per month</td><td><b>{money(result.monthly_total)}</b> ({money(result.per_day)} a day)</td></tr>
                  <tr><td>{money(result.credits_usd)} of credits lasts</td>
                    <td><b>{result.credits_last_days === null ? 'forever' : `${result.credits_last_days} days`}</b></td></tr>
                </tbody>
              </table>

              <h2>Breakdown</h2>
              <table>
                <thead><tr><th>Item</th><th>Calculation</th><th className="num">Per month</th></tr></thead>
                <tbody>
                  {result.lines.map((l) => (
                    <tr key={l.item}><td>{l.item}</td><td className="small">{l.math}</td><td className="num">{money(l.monthly)}</td></tr>
                  ))}
                  <tr className="total"><td>Total</td><td /><td className="num">{money(result.monthly_total)}</td></tr>
                </tbody>
              </table>

              {result.tips.length > 0 && (
                <>
                  <h2>Ways to pay less</h2>
                  <table>
                    <tbody>
                      {result.tips.map((t) => (
                        <tr key={t.tip}><td>{t.tip}</td><td className="num green">-{money(t.saving)}/month</td></tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}

              <h2>Same setup in other regions</h2>
              <table>
                <tbody>
                  {result.regions.map((r) => (
                    <tr key={r.region}><td>{r.region}{r.region === setup.region && ' (selected)'}</td><td className="num">{money(r.monthly)}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="muted small">AWS price list {result.price_list_version}. Linux, 730 hours a month.</p>
            </>
          )}
        </div>
      </div>
    </>
  )
}

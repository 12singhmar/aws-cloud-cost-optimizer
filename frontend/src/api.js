const BASE = 'http://127.0.0.1:8000/api'

async function call(path, options) {
  const res = await fetch(BASE + path, options)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : res.statusText)
  return body
}

const post = (path, data) =>
  call(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data ?? {}) })

export const api = {
  overview: () => call('/overview'),
  catalog: (region) => call(`/catalog/${region}`),
  optimize: (workload) => post('/optimize', workload),
  usage: (scanId) => call(`/usage/${scanId}`),
  profiles: () => call('/profiles'),
  connect: (profile, region) => post('/connect', { profile, region }),
  status: () => call('/status'),
  scan: () => post('/scan'),
  report: (scanId) => call(`/report/${scanId}`),
}

export const money = (v, digits = 2) =>
  '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })

const BASE = 'http://127.0.0.1:8000/api'

async function call(path, options) {
  const res = await fetch(BASE + path, options)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : res.statusText)
  return body
}

function post(path, data) {
  return call(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {}) })
}

export const api = {
  info: () => call('/info'),
  instanceTypes: (region) => call(`/instance-types/${region}`),
  estimate: (setup) => post('/estimate', setup),
  profiles: () => call('/profiles'),
  connect: (profile) => post('/connect', { profile }),
  status: () => call('/status'),
  scan: () => post('/scan'),
  report: (scanId) => call(`/report/${scanId}`),
  fix: (scanId, resourceId, action) => post('/fix', { scan_id: scanId, resource_id: resourceId, action }),
}

export function money(v) {
  return '$' + Number(v).toFixed(2)
}

export const KIND_NAMES = {
  instance: 'Server',
  volume: 'Disk',
  elastic_ip: 'IP address',
  snapshot: 'Backup',
  nat_gateway: 'NAT gateway',
  load_balancer: 'Load balancer',
}

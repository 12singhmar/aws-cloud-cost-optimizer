const BASE = 'http://127.0.0.1:8000/api'

async function call(path, options) {
  const res = await fetch(BASE + path, options)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail || res.statusText)
  return body
}

export const getStatus = () => call('/status')
export const getScans = () => call('/scans')
export const getReport = (id) => call(`/report/${id}`)
export const runScan = () => call('/scan', { method: 'POST' })

export const money = (v) => '$' + v.toFixed(2)

// All calls to the backend live here. Base URL can be changed with VITE_API_URL.
const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`)
  return res.json()
}

export const api = {
  snapshots: () => get('/api/snapshots'),
  analysis: (id) => get(`/api/analysis/${encodeURIComponent(id)}`),
  lab: (id) => get(`/api/lab/${encodeURIComponent(id)}`),
  bill: (id) => get(`/api/billcheck/${encodeURIComponent(id)}`),
  fleet: () => get('/api/fleet'),
  rules: () => get('/api/rules'),
  prices: (region) => get(`/api/prices/${region}`),
}

export const usd = (v, digits) => {
  if (v === null || v === undefined) return '—'
  const d = digits ?? (Math.abs(v) < 10 ? 2 : 0)
  return v.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: d, maximumFractionDigits: d })
}
export const pct = (v, digits = 0) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(digits)}%`)
export const int = (v) => (v ?? 0).toLocaleString('en-US')
export const date = (iso) => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC'

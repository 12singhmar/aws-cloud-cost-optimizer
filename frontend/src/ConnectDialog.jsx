import { useEffect, useState } from 'react'
import { api } from './api.js'

// Lets the user pick an AWS CLI profile that already exists on this computer.
// No keys or passwords are ever typed into the web page.
export default function ConnectDialog({ regions, onClose, onConnected }) {
  const [profiles, setProfiles] = useState([])
  const [profile, setProfile] = useState('')
  const [region, setRegion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.profiles().then((p) => {
      setProfiles(p.profiles)
      setProfile(p.current.profile || p.profiles[0] || '')
      setRegion(p.current.region || '')
    }).catch((e) => setError(e.message))
  }, [])

  async function connect() {
    setBusy(true)
    setError(null)
    try {
      const s = await api.connect(profile || null, region || null)
      if (s.connected) {
        onConnected(s)
        onClose()
      } else {
        setError(s.error)
      }
    } catch (e) {
      setError(e.message)
    }
    setBusy(false)
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label="Connect AWS" onClick={(e) => e.stopPropagation()}>
        <h2>Connect AWS</h2>
        <p className="muted small">First sign in once from a terminal with the AWS CLI (version 2.32 or newer):</p>
        <pre>aws login --profile ccx</pre>
        <p className="muted small">Then choose that profile here. The tool only reads your account.</p>

        <label className="field">
          <span className="field-label">AWS CLI profile</span>
          {profiles.length > 0 ? (
            <select value={profile} onChange={(e) => setProfile(e.target.value)}>
              {profiles.map((p) => <option key={p}>{p}</option>)}
            </select>
          ) : (
            <span className="muted small">No profiles found on this computer yet. Run the command above first.</span>
          )}
        </label>
        <label className="field">
          <span className="field-label">Region</span>
          <select value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="">Use the profile's region</option>
            {regions.map((r) => <option key={r.code} value={r.code}>{r.name} ({r.code})</option>)}
          </select>
        </label>

        {error && <p className="error-text">{error}</p>}
        <div className="row end">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" onClick={connect} disabled={busy}>{busy ? 'Connecting...' : 'Connect'}</button>
        </div>
      </div>
    </div>
  )
}

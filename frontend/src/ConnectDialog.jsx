import { useEffect, useState } from 'react'
import { api } from './api.js'

// Pick an AWS CLI profile that already exists on this computer.
// No keys or passwords are typed into the web page.
export default function ConnectDialog({ onClose, onConnected }) {
  const [profiles, setProfiles] = useState([])
  const [profile, setProfile] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.profiles().then((p) => {
      setProfiles(p.profiles)
      setProfile(p.current || p.profiles[0] || '')
    }).catch((e) => setError(e.message))
  }, [])

  async function connect() {
    setBusy(true)
    setError(null)
    try {
      const s = await api.connect(profile || null)
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
    <div className="overlay">
      <div className="dialog" role="dialog" aria-modal="true" aria-label="Connect AWS">
        <h3>Connect AWS</h3>
        <p>First sign in once from a terminal with the AWS CLI (version 2.32 or newer):</p>
        <pre>aws login --profile ccx</pre>
        <label>
          AWS CLI profile{' '}
          {profiles.length > 0 ? (
            <select value={profile} onChange={(e) => setProfile(e.target.value)}>
              {profiles.map((p) => <option key={p}>{p}</option>)}
            </select>
          ) : (
            <span className="muted">none found yet. Run the command above first.</span>
          )}
        </label>
        {error && <p className="error">{error}</p>}
        <div className="buttons">
          <button onClick={onClose}>Cancel</button>
          <button onClick={connect} disabled={busy}>{busy ? 'Connecting...' : 'Connect'}</button>
        </div>
      </div>
    </div>
  )
}

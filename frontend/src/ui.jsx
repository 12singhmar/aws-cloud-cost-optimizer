// Small reusable UI pieces.

export function Card({ title, sub, children, style }) {
  return (
    <section className="card" style={style}>
      {(title || sub) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {sub && <span className="sub">{sub}</span>}
        </div>
      )}
      {children}
    </section>
  )
}

export function Stat({ label, value, hint }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  )
}

export function PageHead({ title, children }) {
  return (
    <header className="page-head">
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </header>
  )
}

// Verdicts always carry an icon + word, never colour alone.
const VERDICT = {
  'Held up': ['good', '✓'],
  TP: ['good', '✓'],
  TN: ['good', '✓'],
  Borderline: ['', '!'],
  'Would have hurt': ['bad', '✕'],
  FP: ['bad', '✕'],
  FN: ['bad', '✕'],
  'No advice': ['', '–'],
}
export function Verdict({ value }) {
  const [cls, icon] = VERDICT[value] || ['', '•']
  return <span className={`badge ${cls}`}>{icon} {value}</span>
}

export function Empty({ title, children }) {
  return (
    <div className="card empty">
      <h3>{title}</h3>
      <div className="small">{children}</div>
    </div>
  )
}

export function SyntheticBanner({ what }) {
  return (
    <div className="banner" role="note">
      <b>Synthetic example.</b> This {what} belongs to the built-in demo account and only shows what the page
      looks like. Real numbers appear when you select a snapshot collected from your AWS account.
    </div>
  )
}

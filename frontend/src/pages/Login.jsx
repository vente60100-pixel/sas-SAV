import { useState } from 'react'

export default function Login({ onLogin, error: parentError }) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const displayError = parentError || error

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!user || !pass) { setError('Remplissez les deux champs'); return }
    setLoading(true)
    setError('')
    await onLogin(user, pass)
    setLoading(false)
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-primary)',
    }}>
      <div className="glass-card animate-in" style={{ width: 400, textAlign: 'center' }}>
        <div style={{ fontSize: 36, fontWeight: 800, color: 'var(--accent)', letterSpacing: 3, marginBottom: 8 }}>
          OKTAGON
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 32, letterSpacing: 1 }}>
          SAV INTELLIGENCE CENTER
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <input
            className="input"
            type="text"
            placeholder="Utilisateur"
            value={user}
            onChange={e => setUser(e.target.value)}
          />
          <input
            className="input"
            type="password"
            placeholder="Mot de passe"
            value={pass}
            onChange={e => setPass(e.target.value)}
          />
          {displayError && <div style={{ color: 'var(--red)', fontSize: 13 }}>{displayError}</div>}
          <button className="btn-primary" type="submit" style={{ marginTop: 8 }} disabled={loading}>
            {loading ? 'Connexion...' : 'Connexion'}
          </button>
        </form>
      </div>
    </div>
  )
}

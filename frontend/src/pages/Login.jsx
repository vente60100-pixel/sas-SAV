import { useState } from 'react'

export default function Login({ onLogin }) {
  const [user, setUser] = useState('')
  const [pass, setPass] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!user || !pass) { setError('Remplissez les deux champs'); return }
    onLogin(user, pass)
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
          {error && <div style={{ color: 'var(--red)', fontSize: 13 }}>{error}</div>}
          <button className="btn-primary" type="submit" style={{ marginTop: 8 }}>
            Connexion
          </button>
        </form>
      </div>
    </div>
  )
}

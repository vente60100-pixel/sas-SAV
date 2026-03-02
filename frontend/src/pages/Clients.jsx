import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getClients } from '../api/client'
import { Search, Users, Star } from 'lucide-react'

export default function Clients() {
  const [clients, setClients] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const timer = setTimeout(() => {
      getClients(search, 50, 0)
        .then(data => { setClients(data.clients || data); setLoading(false) })
        .catch(() => setLoading(false))
    }, search ? 300 : 0)
    return () => clearTimeout(timer)
  }, [search])

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>Clients</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '4px 0 0' }}>{clients.length} clients</p>
        </div>
        <div style={{ position: 'relative', width: 300 }}>
          <Search size={16} style={{ position: 'absolute', left: 14, top: 12, color: 'var(--text-muted)' }} />
          <input
            className="input"
            placeholder="Rechercher un client..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ paddingLeft: 40 }}
          />
        </div>
      </div>

      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Client', 'Prénom', 'Emails', 'Dernier contact', 'VIP'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '14px 16px', fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Chargement...</td></tr>
            ) : clients.map((c, i) => (
              <tr
                key={i}
                onClick={() => navigate(`/clients/${encodeURIComponent(c.email)}`)}
                style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer', transition: 'background 0.2s' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-card-hover)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <td style={{ padding: '12px 16px', fontSize: 14 }}>{c.email}</td>
                <td style={{ padding: '12px 16px', fontSize: 14, color: 'var(--text-secondary)' }}>{c.prenom || '-'}</td>
                <td style={{ padding: '12px 16px' }}>
                  <span className="badge badge-blue">{c.total_emails}</span>
                </td>
                <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-secondary)' }}>
                  {c.last_contact ? new Date(c.last_contact).toLocaleDateString('fr-FR') : '-'}
                </td>
                <td style={{ padding: '12px 16px' }}>
                  {c.vip && <Star size={16} fill="var(--accent)" color="var(--accent)" />}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

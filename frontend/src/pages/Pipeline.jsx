import { useState, useEffect } from 'react'
import { getPipeline } from '../api/client'
import { Filter } from 'lucide-react'

const CATEGORIES = ['', 'LIVRAISON', 'RETOUR_ECHANGE', 'QUESTION_PRODUIT', 'ANNULATION', 'MODIFIER_ADRESSE', 'AUTRE']

export default function Pipeline() {
  const [emails, setEmails] = useState([])
  const [category, setCategory] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getPipeline(50, 0, category)
      .then(data => { setEmails(data.emails || data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [category])

  const urgencyColor = (u) => {
    if (u === 'CRITICAL') return 'badge-red'
    if (u === 'HIGH') return 'badge-orange'
    if (u === 'MEDIUM') return 'badge-yellow'
    return 'badge-gray'
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>Pipeline</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '4px 0 0' }}>{emails.length} emails</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Filter size={16} color="var(--text-muted)" />
          <select
            className="input"
            style={{ width: 200 }}
            value={category}
            onChange={e => setCategory(e.target.value)}
          >
            <option value="">Toutes catégories</option>
            {CATEGORIES.filter(Boolean).map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Date', 'Client', 'Sujet', 'Catégorie', 'Confiance', 'Détection', 'Urgence', 'Statut'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '12px 14px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Chargement...</td></tr>
            ) : emails.map((e, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)', transition: 'background 0.2s' }}
                  onMouseEnter={ev => ev.currentTarget.style.background = 'var(--bg-card-hover)'}
                  onMouseLeave={ev => ev.currentTarget.style.background = 'transparent'}>
                <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text-muted)' }}>
                  {e.date ? new Date(e.date).toLocaleDateString('fr-FR') : '-'}
                </td>
                <td style={{ padding: '10px 14px', fontSize: 13 }}>{e.email?.split('@')[0] || '-'}</td>
                <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-secondary)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {e.subject || '-'}
                </td>
                <td style={{ padding: '10px 14px' }}><span className="badge badge-blue">{e.category || '-'}</span></td>
                <td style={{ padding: '10px 14px', fontSize: 13 }}>{e.confidence != null ? `${(e.confidence * 100).toFixed(0)}%` : '-'}</td>
                <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text-muted)' }}>{e.detection || '-'}</td>
                <td style={{ padding: '10px 14px' }}>{e.urgency && <span className={`badge ${urgencyColor(e.urgency)}`}>{e.urgency}</span>}</td>
                <td style={{ padding: '10px 14px' }}>
                  <span className={`badge ${e.sent ? 'badge-green' : 'badge-orange'}`}>{e.sent ? 'Envoyé' : 'Attente'}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

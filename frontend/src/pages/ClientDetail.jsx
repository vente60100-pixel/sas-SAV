import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getClientDetail } from '../api/client'
import { ArrowLeft, Mail, AlertTriangle, User } from 'lucide-react'

export default function ClientDetail() {
  const { email } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getClientDetail(decodeURIComponent(email))
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [email])

  if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>Chargement...</div>
  if (!data) return <div style={{ color: 'var(--red)', padding: 40 }}>Client non trouvé</div>

  const profile = data.profile || {}
  const history = data.history || []
  const escalations = data.escalations || []

  return (
    <div>
      <button onClick={() => navigate('/clients')} className="btn-secondary" style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 8 }}>
        <ArrowLeft size={16} /> Retour
      </button>

      {/* Profile header */}
      <div className="glass-card animate-in" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ width: 56, height: 56, borderRadius: 16, background: 'rgba(240,255,39,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <User size={28} color="var(--accent)" />
          </div>
          <div style={{ flex: 1 }}>
            <h2 style={{ margin: 0, fontSize: 22 }}>{profile.prenom || decodeURIComponent(email)}</h2>
            <div style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>{decodeURIComponent(email)}</div>
          </div>
          <div style={{ display: 'flex', gap: 16, textAlign: 'center' }}>
            <div>
              <div style={{ fontSize: 24, fontWeight: 700 }}>{profile.total_emails || 0}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Emails</div>
            </div>
            <div>
              <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--orange)' }}>{profile.total_escalations || 0}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Escalations</div>
            </div>
          </div>
        </div>
      </div>

      {/* History */}
      <div className="glass-card animate-in" style={{ animationDelay: '200ms' }}>
        <h3 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 600 }}>
          <Mail size={18} style={{ verticalAlign: 'middle', marginRight: 8 }} />
          Historique ({history.length})
        </h3>
        {history.map((h, i) => (
          <div key={i} style={{ padding: '16px 0', borderBottom: i < history.length - 1 ? '1px solid var(--border)' : 'none' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span className={`badge badge-${h.category === 'LIVRAISON' ? 'blue' : h.category === 'RETOUR_ECHANGE' ? 'orange' : 'gray'}`}>
                {h.category || 'N/A'}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {h.date ? new Date(h.date).toLocaleString('fr-FR') : ''}
              </span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>
              <strong>Client :</strong> {h.subject} — {h.client_message || ''}
            </div>
            {h.sav_response && (
              <div style={{ fontSize: 13, color: 'var(--accent)', background: 'rgba(240,255,39,0.05)', padding: '8px 12px', borderRadius: 8, marginTop: 6 }}>
                <strong>SAV :</strong> {h.sav_response.substring(0, 200)}{h.sav_response.length > 200 ? '...' : ''}
              </div>
            )}
          </div>
        ))}
        {history.length === 0 && <div style={{ color: 'var(--text-muted)' }}>Aucun historique</div>}
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { getEscalations, resolveEscalation, sendEmail } from '../api/client'
import { AlertTriangle, Send, Check } from 'lucide-react'

export default function Escalations() {
  const [escalations, setEscalations] = useState([])
  const [loading, setLoading] = useState(true)
  const [replyId, setReplyId] = useState(null)
  const [replyText, setReplyText] = useState('')
  const [sending, setSending] = useState(false)

  const load = () => {
    setLoading(true)
    getEscalations()
      .then(data => { setEscalations(data.escalations || data); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(load, [])

  const handleResolve = async (id) => {
    if (!confirm('Résoudre cette escalation ?')) return
    await resolveEscalation(id, 'resolved')
    load()
  }

  const handleReply = async (esc) => {
    if (!replyText.trim()) return
    setSending(true)
    try {
      await sendEmail(esc.email, `Re: ${esc.subject || 'OKTAGON SAV'}`, replyText)
      await resolveEscalation(esc.id, 'replied', replyText)
      setReplyId(null)
      setReplyText('')
      load()
    } catch (e) {
      alert('Erreur envoi')
    }
    setSending(false)
  }

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>
          Escalations
          {escalations.length > 0 && (
            <span className="badge badge-orange" style={{ marginLeft: 12, fontSize: 14, verticalAlign: 'middle' }}>
              {escalations.length}
            </span>
          )}
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '4px 0 0' }}>Demandes nécessitant une action humaine</p>
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-muted)', padding: 40 }}>Chargement...</div>
      ) : escalations.length === 0 ? (
        <div className="glass-card" style={{ textAlign: 'center', padding: 60 }}>
          <Check size={48} color="var(--green)" style={{ marginBottom: 16 }} />
          <div style={{ fontSize: 18, fontWeight: 600 }}>Aucune escalation en attente</div>
          <div style={{ color: 'var(--text-muted)', marginTop: 8 }}>Tout est sous contrôle</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {escalations.map(esc => (
            <div key={esc.id} className="glass-card animate-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div>
                  <span className="badge badge-orange" style={{ marginRight: 8 }}>{esc.category}</span>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{esc.email}</span>
                </div>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {esc.date ? new Date(esc.date).toLocaleString('fr-FR') : ''}
                </span>
              </div>

              <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 8 }}>
                <strong>Raison :</strong> {esc.reason}
              </div>
              {esc.preview && (
                <div style={{ fontSize: 13, color: 'var(--text-muted)', background: 'var(--bg-secondary)', padding: '10px 14px', borderRadius: 8, marginBottom: 12 }}>
                  {esc.preview}
                </div>
              )}

              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn-primary" style={{ fontSize: 13 }} onClick={() => setReplyId(replyId === esc.id ? null : esc.id)}>
                  <Send size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                  Répondre
                </button>
                <button className="btn-secondary" style={{ fontSize: 13 }} onClick={() => handleResolve(esc.id)}>
                  <Check size={14} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                  Résoudre
                </button>
              </div>

              {replyId === esc.id && (
                <div style={{ marginTop: 12, padding: 16, background: 'var(--bg-secondary)', borderRadius: 12 }}>
                  <textarea
                    className="input"
                    rows={4}
                    placeholder="Réponse au client..."
                    value={replyText}
                    onChange={e => setReplyText(e.target.value)}
                    style={{ resize: 'vertical', marginBottom: 12 }}
                  />
                  <button
                    className="btn-primary"
                    onClick={() => handleReply(esc)}
                    disabled={sending}
                    style={{ fontSize: 13 }}
                  >
                    {sending ? 'Envoi...' : 'Envoyer'}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

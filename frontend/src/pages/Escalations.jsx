import { useState, useEffect, useRef } from 'react'
import { getEscalations, getEscalationDetail, getEscalationAiDraft, resolveEscalation, sendEmail } from '../api/client'
import { AlertTriangle, Send, Check, X, Brain, Package, User, Clock, ChevronRight, Sparkles, Mail, Shield, MessageCircle, ArrowLeft } from 'lucide-react'

const URGENCY_COLORS = { critique: '#ef4444', haute: '#f97316', moyenne: '#F0FF27', basse: '#22c55e' }
const EMOTION_COLORS = { 'en colère': '#ef4444', frustré: '#f97316', neutre: '#3b82f6', content: '#22c55e', inquiet: '#8b5cf6' }

function UrgencyBadge({ level }) {
  const c = URGENCY_COLORS[level] || '#a0a0a0'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600, background: `${c}18`, color: c, textTransform: 'uppercase', letterSpacing: 0.5 }}>
      {level}
    </span>
  )
}

function EmotionBadge({ emotion }) {
  const c = EMOTION_COLORS[emotion] || '#a0a0a0'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 500, background: `${c}15`, color: c }}>
      {emotion}
    </span>
  )
}

function EscalationCard({ esc, isSelected, onClick }) {
  const urgencyColor = esc.ai_analysis
    ? (URGENCY_COLORS[esc.ai_analysis.urgency] || 'var(--orange)')
    : 'var(--orange)'

  return (
    <div
      onClick={onClick}
      style={{
        padding: 16, borderRadius: 14, cursor: 'pointer',
        background: isSelected ? 'rgba(240,255,39,0.06)' : 'var(--bg-secondary)',
        border: `1px solid ${isSelected ? 'rgba(240,255,39,0.3)' : 'var(--border)'}`,
        borderLeft: `4px solid ${urgencyColor}`,
        transition: 'all 0.2s',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{
          padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600,
          background: `${urgencyColor}15`, color: urgencyColor,
        }}>
          {esc.category}
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {esc.date ? timeAgo(esc.date) : ''}
        </span>
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4, color: 'var(--text-primary)' }}>
        {esc.email?.split('@')[0]}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
        {esc.preview || esc.reason}
      </div>
    </div>
  )
}

function ConversationBubble({ msg }) {
  const isClient = msg.from === 'client'
  return (
    <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexDirection: isClient ? 'row' : 'row-reverse' }}>
      <div style={{
        width: 32, height: 32, borderRadius: 10, flexShrink: 0,
        background: isClient ? 'rgba(59,130,246,0.12)' : 'rgba(240,255,39,0.12)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {isClient ? <User size={16} color="var(--blue)" /> : <Shield size={16} color="var(--accent)" />}
      </div>
      <div style={{
        maxWidth: '80%', padding: '10px 14px', borderRadius: 12, fontSize: 13, lineHeight: 1.6,
        background: isClient ? 'rgba(59,130,246,0.08)' : 'rgba(240,255,39,0.06)',
        border: `1px solid ${isClient ? 'rgba(59,130,246,0.15)' : 'rgba(240,255,39,0.15)'}`,
      }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
          {isClient ? 'Client' : 'SAV'} — {msg.date ? new Date(msg.date).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
        </div>
        {msg.text}
      </div>
    </div>
  )
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return 'Il y a quelques minutes'
  if (hours < 24) return `Il y a ${hours}h`
  return `Il y a ${Math.floor(hours / 24)}j`
}

export default function Escalations() {
  const [escalations, setEscalations] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [draft, setDraft] = useState('')
  const [loadingDraft, setLoadingDraft] = useState(false)
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const textareaRef = useRef(null)

  const load = () => {
    setLoading(true)
    getEscalations()
      .then(data => { setEscalations(data.escalations || []); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(load, [])

  const selectEscalation = async (esc) => {
    setSelected(esc.id)
    setDetail(null)
    setDraft('')
    setSent(false)
    setLoadingDetail(true)
    try {
      const d = await getEscalationDetail(esc.id)
      setDetail(d)
    } catch {
      setDetail(esc)
    }
    setLoadingDetail(false)
  }

  const handleAiDraft = async () => {
    if (!selected) return
    setLoadingDraft(true)
    try {
      const data = await getEscalationAiDraft(selected)
      setDraft(data.draft || '')
      setTimeout(() => textareaRef.current?.focus(), 100)
    } catch {
      setDraft('Erreur lors de la génération.')
    }
    setLoadingDraft(false)
  }

  const handleSend = async () => {
    if (!draft.trim() || !detail) return
    setSending(true)
    try {
      await sendEmail(detail.email, `Re: ${detail.subject || 'OKTAGON SAV'}`, draft)
      await resolveEscalation(detail.id, 'replied', draft)
      setSent(true)
      setTimeout(() => {
        setSelected(null)
        setDetail(null)
        setDraft('')
        setSent(false)
        load()
      }, 2000)
    } catch {
      alert('Erreur lors de l\'envoi')
    }
    setSending(false)
  }

  const handleResolve = async () => {
    if (!detail) return
    await resolveEscalation(detail.id, 'resolved')
    setSelected(null)
    setDetail(null)
    load()
  }

  const selectedEsc = escalations.find(e => e.id === selected)

  return (
    <div style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ marginBottom: 20, flexShrink: 0 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
          Escalations
          {escalations.length > 0 && (
            <span style={{ background: 'var(--red)', color: '#fff', fontSize: 14, fontWeight: 700, padding: '2px 10px', borderRadius: 99 }}>
              {escalations.length}
            </span>
          )}
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '4px 0 0' }}>Gestion assistée par IA — sélectionnez une escalation</p>
      </div>

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1 }}>
          <div className="spinner" />
        </div>
      ) : escalations.length === 0 ? (
        <div className="glass-card" style={{ textAlign: 'center', padding: 60 }}>
          <Check size={48} color="var(--green)" style={{ marginBottom: 16 }} />
          <div style={{ fontSize: 18, fontWeight: 600 }}>Aucune escalation en attente</div>
          <div style={{ color: 'var(--text-muted)', marginTop: 8 }}>Tout est sous contrôle</div>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 20, flex: 1, minHeight: 0 }}>
          {/* Left: Escalation list */}
          <div style={{ width: 340, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto', paddingRight: 8 }}>
            {escalations.map(esc => (
              <EscalationCard
                key={esc.id}
                esc={esc}
                isSelected={selected === esc.id}
                onClick={() => selectEscalation(esc)}
              />
            ))}
          </div>

          {/* Right: Detail panel */}
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            {!selected ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                <div style={{ textAlign: 'center' }}>
                  <ChevronRight size={48} style={{ opacity: 0.3, marginBottom: 12 }} />
                  <div style={{ fontSize: 15 }}>Sélectionnez une escalation</div>
                </div>
              </div>
            ) : loadingDetail ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <div className="spinner" />
              </div>
            ) : detail && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Client + Order info header */}
                <div className="glass-card" style={{ padding: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                      <div style={{ width: 48, height: 48, borderRadius: 14, background: 'rgba(59,130,246,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <User size={24} color="var(--blue)" />
                      </div>
                      <div>
                        <div style={{ fontSize: 18, fontWeight: 700 }}>
                          {detail.client?.prenom || detail.email?.split('@')[0]}
                          {detail.client?.vip && (
                            <span style={{ marginLeft: 8, padding: '2px 8px', borderRadius: 99, fontSize: 11, fontWeight: 600, background: 'rgba(240,255,39,0.15)', color: 'var(--accent)' }}>VIP</span>
                          )}
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{detail.email}</div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      {detail.ai_analysis && <UrgencyBadge level={detail.ai_analysis.urgency} />}
                      {detail.ai_analysis && <EmotionBadge emotion={detail.ai_analysis.emotion} />}
                    </div>
                  </div>

                  {/* Order info */}
                  {detail.order && (
                    <div style={{ display: 'flex', gap: 20, padding: '12px 16px', background: 'var(--bg-secondary)', borderRadius: 10, fontSize: 13 }}>
                      <div><span style={{ color: 'var(--text-muted)' }}>Commande</span> <strong>#{detail.order.number}</strong></div>
                      <div><span style={{ color: 'var(--text-muted)' }}>Total</span> <strong>{detail.order.total}€</strong></div>
                      <div><span style={{ color: 'var(--text-muted)' }}>Statut</span> <strong>{detail.order.status === 'fulfilled' ? 'Expédié' : 'Non expédié'}</strong></div>
                      {detail.order.tracking && <div><span style={{ color: 'var(--text-muted)' }}>Tracking</span> <strong>{detail.order.tracking}</strong></div>}
                      {detail.order.items && <div style={{ color: 'var(--text-secondary)' }}>{detail.order.items.join(', ')}</div>}
                    </div>
                  )}
                </div>

                {/* AI Analysis */}
                {detail.ai_analysis && (
                  <div className="glass-card" style={{ padding: 20, borderLeft: '4px solid var(--accent)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                      <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(240,255,39,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Brain size={16} color="var(--accent)" />
                      </div>
                      <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0, color: 'var(--accent)' }}>Analyse IA</h3>
                    </div>
                    <div style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-secondary)' }}>
                      <p style={{ margin: '0 0 10px' }}><strong style={{ color: 'var(--text-primary)' }}>Résumé :</strong> {detail.ai_analysis.summary}</p>
                      <p style={{ margin: '0 0 10px' }}><strong style={{ color: 'var(--text-primary)' }}>Recommandation :</strong> {detail.ai_analysis.recommendation}</p>
                      <p style={{ margin: '0 0 10px' }}><strong style={{ color: 'var(--text-primary)' }}>Risque :</strong> {detail.ai_analysis.risk}</p>
                      {detail.ai_analysis.similar_cases && (
                        <p style={{ margin: 0, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                          {detail.ai_analysis.similar_cases}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* Conversation history */}
                {detail.history && detail.history.length > 0 && (
                  <div className="glass-card" style={{ padding: 20 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <MessageCircle size={16} color="var(--blue)" /> Historique conversation
                    </h3>
                    {detail.history.map((msg, i) => <ConversationBubble key={i} msg={msg} />)}
                  </div>
                )}

                {/* Response composer */}
                <div className="glass-card" style={{ padding: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Mail size={16} color="var(--green)" /> Réponse
                    </h3>
                    <button
                      onClick={handleAiDraft}
                      disabled={loadingDraft}
                      className="btn-secondary"
                      style={{ fontSize: 12, padding: '6px 14px', display: 'flex', alignItems: 'center', gap: 6, borderColor: 'rgba(240,255,39,0.3)' }}
                    >
                      <Sparkles size={14} color="var(--accent)" />
                      {loadingDraft ? 'Génération...' : 'Générer avec IA'}
                    </button>
                  </div>

                  <textarea
                    ref={textareaRef}
                    className="input"
                    rows={8}
                    placeholder="Rédigez votre réponse ou cliquez sur 'Générer avec IA'..."
                    value={draft}
                    onChange={e => setDraft(e.target.value)}
                    style={{ resize: 'vertical', marginBottom: 14, fontFamily: 'inherit', lineHeight: 1.6 }}
                  />

                  {sent ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', background: 'rgba(34,197,94,0.1)', borderRadius: 10, border: '1px solid rgba(34,197,94,0.3)' }}>
                      <Check size={20} color="var(--green)" />
                      <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--green)' }}>Email envoyé et escalation résolue !</span>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: 10 }}>
                      <button
                        className="btn-primary"
                        onClick={handleSend}
                        disabled={sending || !draft.trim()}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, padding: '10px 20px' }}
                      >
                        <Send size={16} />
                        {sending ? 'Envoi...' : 'Envoyer et résoudre'}
                      </button>
                      <button
                        className="btn-secondary"
                        onClick={handleResolve}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}
                      >
                        <Check size={16} />
                        Résoudre sans répondre
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        .spinner { width: 40px; height: 40px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}

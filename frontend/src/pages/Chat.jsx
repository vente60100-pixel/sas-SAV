import { useState, useRef, useEffect } from 'react'
import { sendChatMessage } from '../api/client'
import { Send, Bot, User } from 'lucide-react'

export default function Chat() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Salut ! Je suis ton assistant IA. Pose-moi n\'importe quelle question sur le SAV, les clients, les commandes...' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const msg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setLoading(true)

    try {
      const data = await sendChatMessage(msg)
      setMessages(prev => [...prev, { role: 'assistant', content: data.response || data.message || 'Pas de réponse' }])
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Erreur de communication avec l\'IA.' }])
    }
    setLoading(false)
    inputRef.current?.focus()
  }

  const suggestions = [
    'Combien d\'emails cette semaine ?',
    'Montre-moi les clients mécontents',
    'Résumé des escalations en attente',
    'Stats par catégorie ce mois',
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>Chat IA</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '4px 0 0' }}>Ton assistant intelligent</p>
      </div>

      {/* Messages */}
      <div className="glass-card" style={{ flex: 1, overflow: 'auto', marginBottom: 16, padding: 20 }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            display: 'flex', gap: 12, marginBottom: 20,
            flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10, flexShrink: 0,
              background: m.role === 'user' ? 'rgba(59,130,246,0.15)' : 'rgba(240,255,39,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {m.role === 'user' ? <User size={18} color="var(--blue)" /> : <Bot size={18} color="var(--accent)" />}
            </div>
            <div style={{
              maxWidth: '70%', padding: '12px 16px', borderRadius: 14, fontSize: 14, lineHeight: 1.6,
              background: m.role === 'user' ? 'rgba(59,130,246,0.1)' : 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              whiteSpace: 'pre-wrap',
            }}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(240,255,39,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Bot size={18} color="var(--accent)" />
            </div>
            <div style={{ padding: '12px 16px', borderRadius: 14, background: 'var(--bg-secondary)', color: 'var(--text-muted)', fontSize: 14 }}>
              Réflexion...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          {suggestions.map((s, i) => (
            <button key={i} className="btn-secondary" style={{ fontSize: 12, padding: '6px 12px' }}
              onClick={() => { setInput(s); inputRef.current?.focus() }}>
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{ display: 'flex', gap: 12 }}>
        <input
          ref={inputRef}
          className="input"
          placeholder="Pose une question..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          disabled={loading}
        />
        <button className="btn-primary" onClick={handleSend} disabled={loading} style={{ flexShrink: 0, width: 48, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}

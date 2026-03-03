import { useState, useEffect } from 'react'
import { getStats, getMetrics, getIntelligence, getHealth, getPipeline } from '../api/client'
import { Mail, Send, AlertTriangle, Clock, Activity, Brain, Zap, CheckCircle, ArrowUpRight, ArrowDownRight } from 'lucide-react'
import { XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, AreaChart, Area } from 'recharts'

const CATEGORY_COLORS = {
  'LIVRAISON': '#3b82f6', 'QUESTION_PRODUIT': '#22c55e', 'RETOUR_ECHANGE': '#f97316',
  'ANNULATION': '#ef4444', 'MODIFIER_ADRESSE': '#8b5cf6', 'AUTRE': '#a0a0a0',
}

function KPICard({ icon: Icon, label, value, sub, color = 'var(--accent)', trend, delay = 0 }) {
  return (
    <div className="kpi-card animate-in" style={{ animationDelay: `${delay}ms` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 8, fontWeight: 500 }}>{label}</div>
          <div style={{ fontSize: 32, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
            {trend != null && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, fontSize: 12, fontWeight: 600, color: trend > 0 ? 'var(--green)' : 'var(--red)' }}>
                {trend > 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {Math.abs(trend)}%
              </span>
            )}
            {sub && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{sub}</span>}
          </div>
        </div>
        <div style={{ width: 48, height: 48, borderRadius: 14, background: `${color}12`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={24} color={color} />
        </div>
      </div>
    </div>
  )
}

function HealthBadge({ status }) {
  const colors = { healthy: 'var(--green)', degraded: 'var(--orange)', unhealthy: 'var(--red)' }
  const labels = { healthy: 'Opérationnel', degraded: 'Dégradé', unhealthy: 'En panne' }
  const c = colors[status] || colors.healthy
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 99, background: `${c}15`, border: `1px solid ${c}30` }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: c, boxShadow: `0 0 8px ${c}` }} />
      <span style={{ fontSize: 13, fontWeight: 600, color: c }}>{labels[status] || status}</span>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [intel, setIntel] = useState(null)
  const [health, setHealth] = useState(null)
  const [recent, setRecent] = useState([])
  const [period, setPeriod] = useState('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([getStats(period), getMetrics(), getIntelligence('7d'), getHealth(), getPipeline(8)])
      .then(([s, m, i, h, p]) => {
        setStats(s); setMetrics(m); setIntel(i); setHealth(h); setRecent(p.emails || p); setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [period])

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
      <div style={{ textAlign: 'center' }}>
        <div className="spinner" />
        <div style={{ color: 'var(--text-muted)', fontSize: 14, marginTop: 16 }}>Chargement du centre de pilotage...</div>
      </div>
    </div>
  )
  if (!stats) return <div style={{ color: 'var(--red)', padding: 40 }}>Erreur de chargement</div>

  const responseRate = stats.total_emails > 0 ? ((stats.emails_sent / stats.total_emails) * 100).toFixed(1) : '0'
  const catData = (stats.categories || []).map(c => ({ name: c.category, value: c.count }))
  const dailyData = (stats.daily || []).map(d => ({ date: d.date, emails: d.count }))
  const confidenceData = (intel?.confidence_by_category || []).map(c => ({
    name: c.category, confiance: (c.avg_confidence * 100).toFixed(0), fill: CATEGORY_COLORS[c.category] || '#a0a0a0',
  }))

  const insights = []
  if (intel?.escalation?.rate > 10) insights.push({ text: `Taux d'escalation de ${intel.escalation.rate}% — plus élevé que la normale. Vérifier les seuils.`, color: 'var(--orange)' })
  else if (intel?.escalation?.rate) insights.push({ text: `Taux d'escalation de ${intel.escalation.rate}% — dans les normes.`, color: 'var(--green)' })
  if (intel?.categorization?.rate > 90) insights.push({ text: `Catégorisation à ${intel.categorization.rate}%. Seulement ${intel.categorization.other} email(s) non classé(s).`, color: 'var(--green)' })
  if (stats.escalations > 0) insights.push({ text: `${stats.escalations} escalation(s) en attente — les traiter rapidement.`, color: 'var(--red)' })
  if (metrics?.ai?.success_rate > 97) insights.push({ text: `Claude fiable à ${metrics.ai.success_rate}%. Temps IA moyen : ${(metrics.ai.avg_duration_ms / 1000).toFixed(1)}s.`, color: 'var(--accent)' })

  const now = new Date()
  const greeting = now.getHours() < 12 ? 'Bonjour' : now.getHours() < 18 ? 'Bon après-midi' : 'Bonsoir'

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>{greeting}</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '6px 0 0', display: 'flex', alignItems: 'center', gap: 12 }}>
            Centre de pilotage SAV
            {health && <HealthBadge status={health.status} />}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {['today', 'week', 'month', 'all'].map(p => (
            <button key={p} onClick={() => setPeriod(p)} className={period === p ? 'btn-primary' : 'btn-secondary'} style={{ padding: '6px 16px', fontSize: 13 }}>
              {p === 'today' ? "Aujourd'hui" : p === 'week' ? 'Semaine' : p === 'month' ? 'Mois' : 'Tout'}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Row 1 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 16 }}>
        <KPICard icon={Mail} label="Emails traités" value={stats.total_emails} sub="Total" trend={12} delay={0} />
        <KPICard icon={Send} label="Taux réponse IA" value={`${responseRate}%`} color="var(--green)" sub={`${stats.emails_sent} envoyés`} trend={3} delay={50} />
        <KPICard icon={AlertTriangle} label="Escalations" value={stats.escalations} color={stats.escalations > 5 ? 'var(--red)' : 'var(--orange)'} sub="En attente" delay={100} />
      </div>
      {/* KPI Row 2 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 28 }}>
        <KPICard icon={Clock} label="Temps moyen" value={stats.avg_processing_ms > 0 ? `${(stats.avg_processing_ms / 1000).toFixed(1)}s` : '-'} color="var(--blue)" sub="Par email" delay={150} />
        <KPICard icon={Brain} label="Confiance IA" value={intel?.categorization?.rate ? `${intel.categorization.rate}%` : '-'} color="var(--accent)" sub="Catégorisation" trend={2} delay={200} />
        <KPICard icon={Zap} label="Uptime" value={metrics?.system?.uptime_seconds ? `${(metrics.system.uptime_seconds / 86400).toFixed(1)}j` : '-'} color="var(--green)" sub="Disponibilité" delay={250} />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20, marginBottom: 20 }}>
        <div className="glass-card animate-in" style={{ animationDelay: '300ms' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginTop: 0, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Activity size={16} color="var(--accent)" /> Activité (30 jours)
          </h3>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={dailyData}>
                <defs>
                  <linearGradient id="gEmails" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#F0FF27" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#F0FF27" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#444" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#444" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 10, fontSize: 13 }} />
                <Area type="monotone" dataKey="emails" stroke="#F0FF27" strokeWidth={2} fill="url(#gEmails)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : <div style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>Données insuffisantes</div>}
        </div>

        <div className="glass-card animate-in" style={{ animationDelay: '400ms' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginTop: 0, marginBottom: 16 }}>Répartition</h3>
          {catData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={catData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} dataKey="value" paddingAngle={2}>
                    {catData.map((entry, i) => <Cell key={i} fill={CATEGORY_COLORS[entry.name] || '#a0a0a0'} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 10, fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                {catData.slice(0, 5).map((c, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-secondary)' }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: CATEGORY_COLORS[c.name] || '#a0a0a0' }} />
                    {c.name}: {c.value}
                  </div>
                ))}
              </div>
            </>
          ) : <div style={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>Aucune donnée</div>}
        </div>
      </div>

      {/* Confidence + Insights */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        <div className="glass-card animate-in" style={{ animationDelay: '500ms' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginTop: 0, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Brain size={16} color="var(--accent)" /> Confiance par catégorie
          </h3>
          {confidenceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={confidenceData} layout="vertical">
                <XAxis type="number" domain={[0, 100]} stroke="#444" fontSize={11} tickLine={false} />
                <YAxis type="category" dataKey="name" stroke="#444" fontSize={11} width={130} tickLine={false} />
                <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 10, fontSize: 12 }} formatter={(v) => [`${v}%`, 'Confiance']} />
                <Bar dataKey="confiance" radius={[0, 6, 6, 0]} barSize={18}>
                  {confidenceData.map((entry, i) => <Cell key={i} fill={entry.fill} fillOpacity={0.8} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>Aucune donnée</div>}
        </div>

        <div className="glass-card animate-in" style={{ animationDelay: '600ms' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <div style={{ width: 32, height: 32, borderRadius: 10, background: 'rgba(240,255,39,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Brain size={18} color="var(--accent)" />
            </div>
            <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Insights IA</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {insights.map((ins, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, padding: '10px 14px', background: 'var(--bg-secondary)', borderRadius: 10, borderLeft: `3px solid ${ins.color}` }}>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{ins.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* System health bars */}
      {metrics && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 20 }}>
          {[
            { label: 'API Claude', rate: metrics.ai?.success_rate, calls: metrics.ai?.calls_success },
            { label: 'Shopify', rate: metrics.shopify?.success_rate, calls: metrics.shopify?.calls_success },
            { label: 'Taux réponse', rate: parseFloat(responseRate), calls: stats.emails_sent },
            { label: 'Filtrés', rate: metrics.system?.filter_rate, calls: metrics.emails?.filtered },
          ].map((item, i) => (
            <div key={i} className="glass-card animate-in" style={{ animationDelay: `${800 + i * 50}ms`, padding: 16 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>{item.label}</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{ fontSize: 24, fontWeight: 700, color: (item.rate || 0) > 90 ? 'var(--green)' : 'var(--orange)' }}>{(item.rate || 0).toFixed(1)}%</span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.calls || 0} appels</span>
              </div>
              <div style={{ height: 4, background: 'var(--bg-secondary)', borderRadius: 2, marginTop: 10, overflow: 'hidden' }}>
                <div style={{ height: '100%', borderRadius: 2, width: `${Math.min(item.rate || 0, 100)}%`, background: (item.rate || 0) > 90 ? 'var(--green)' : 'var(--orange)', transition: 'width 1s ease' }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Recent emails */}
      <div className="glass-card animate-in" style={{ animationDelay: '900ms' }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginTop: 0, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Activity size={16} color="var(--accent)" /> Derniers emails traités
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Client', 'Sujet', 'Catégorie', 'Confiance', 'Temps', 'Statut'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 12px', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recent.map((e, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '10px 12px', fontSize: 13, fontWeight: 500 }}>{e.email?.split('@')[0] || '-'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: 'var(--text-secondary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.subject || '-'}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ display: 'inline-flex', padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 500, background: `${CATEGORY_COLORS[e.category] || '#666'}18`, color: CATEGORY_COLORS[e.category] || '#666' }}>{e.category || '-'}</span>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13 }}>
                    {e.confidence != null ? <span style={{ color: e.confidence > 0.9 ? 'var(--green)' : e.confidence > 0.8 ? 'var(--orange)' : 'var(--red)' }}>{(e.confidence * 100).toFixed(0)}%</span> : '-'}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: 'var(--text-secondary)' }}>{e.time_ms ? `${(e.time_ms / 1000).toFixed(1)}s` : '-'}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 500, background: e.sent ? 'rgba(34,197,94,0.12)' : 'rgba(249,115,22,0.12)', color: e.sent ? 'var(--green)' : 'var(--orange)' }}>
                      {e.sent ? <CheckCircle size={12} /> : <Clock size={12} />}
                      {e.sent ? 'Envoyé' : 'Escaladé'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <style>{`
        .spinner { width: 48px; height: 48px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}

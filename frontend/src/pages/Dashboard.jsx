import { useState, useEffect } from 'react'
import { getStats, getPipeline } from '../api/client'
import { Mail, Send, AlertTriangle, Clock, TrendingUp, Activity } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar } from 'recharts'

const COLORS = ['#F0FF27', '#3b82f6', '#22c55e', '#f97316', '#ef4444', '#8b5cf6', '#ec4899', '#a0a0a0']

function KPICard({ icon: Icon, label, value, sub, color = 'var(--accent)', delay = 0 }) {
  return (
    <div className="kpi-card animate-in" style={{ animationDelay: `${delay}ms` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
            {label}
          </div>
          <div style={{ fontSize: 32, fontWeight: 700, color }}>{value}</div>
          {sub && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{sub}</div>}
        </div>
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: `${color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <Icon size={22} color={color} />
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [period, setPeriod] = useState('all')
  const [recent, setRecent] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getStats(period), getPipeline(10)])
      .then(([s, p]) => { setStats(s); setRecent(p.emails || p); setLoading(false) })
      .catch(() => setLoading(false))
  }, [period])

  if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>Chargement...</div>
  if (!stats) return <div style={{ color: 'var(--red)', padding: 40 }}>Erreur de chargement</div>

  const taux = stats.total_emails > 0
    ? ((stats.emails_sent / stats.total_emails) * 100).toFixed(1)
    : '0'

  // Mock data for charts (will be replaced by real API data)
  const catData = (stats.categories || []).map(c => ({ name: c.category, value: c.count }))
  const dailyData = (stats.daily || []).map(d => ({ date: d.date, emails: d.count }))

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>Dashboard</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '4px 0 0' }}>Vue d'ensemble en temps réel</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {['today', 'week', 'month', 'all'].map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={period === p ? 'btn-primary' : 'btn-secondary'}
              style={{ padding: '6px 16px', fontSize: 13 }}
            >
              {p === 'today' ? "Aujourd'hui" : p === 'week' ? 'Semaine' : p === 'month' ? 'Mois' : 'Tout'}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20, marginBottom: 32 }}>
        <KPICard icon={Mail} label="Emails traités" value={stats.total_emails} sub={`Période: ${period}`} delay={0} />
        <KPICard icon={Send} label="Taux de réponse" value={`${taux}%`} color="var(--green)" sub={`${stats.emails_sent} envoyés`} delay={100} />
        <KPICard icon={AlertTriangle} label="Escalations" value={stats.escalations} color="var(--orange)" sub="En attente" delay={200} />
        <KPICard icon={Clock} label="Temps moyen" value={stats.avg_processing_ms > 0 ? `${(stats.avg_processing_ms / 1000).toFixed(1)}s` : '-'} color="var(--blue)" sub="Par email" delay={300} />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20, marginBottom: 32 }}>
        {/* Line chart */}
        <div className="glass-card animate-in" style={{ animationDelay: '400ms' }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginTop: 0, marginBottom: 20 }}>Emails par jour</h3>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={dailyData}>
                <XAxis dataKey="date" stroke="#666" fontSize={11} />
                <YAxis stroke="#666" fontSize={11} />
                <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 8 }} />
                <Line type="monotone" dataKey="emails" stroke="#F0FF27" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              Données insuffisantes
            </div>
          )}
        </div>

        {/* Pie chart */}
        <div className="glass-card animate-in" style={{ animationDelay: '500ms' }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginTop: 0, marginBottom: 20 }}>Par catégorie</h3>
          {catData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={catData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {catData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              Aucune donnée
            </div>
          )}
        </div>
      </div>

      {/* Recent emails */}
      <div className="glass-card animate-in" style={{ animationDelay: '600ms' }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginTop: 0, marginBottom: 20 }}>
          <Activity size={18} style={{ verticalAlign: 'middle', marginRight: 8 }} />
          Derniers emails traités
        </h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Client', 'Sujet', 'Catégorie', 'Confiance', 'Temps', 'Statut'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 12px', fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recent.map((e, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '10px 12px', fontSize: 13 }}>{e.email?.split('@')[0] || '-'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: 'var(--text-secondary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {e.subject || '-'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className={`badge badge-${e.category === 'LIVRAISON' ? 'blue' : e.category === 'ESCALATION' ? 'red' : 'gray'}`}>
                      {e.category || '-'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13 }}>
                    {e.confidence != null ? `${(e.confidence * 100).toFixed(0)}%` : '-'}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: 'var(--text-secondary)' }}>
                    {e.time_ms ? `${(e.time_ms / 1000).toFixed(1)}s` : '-'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className={`badge ${e.sent ? 'badge-green' : 'badge-orange'}`}>
                      {e.sent ? 'Envoyé' : 'En attente'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Users, Zap, AlertTriangle, MessageSquare, Settings, LogOut, Shield } from 'lucide-react'
import { useState, useEffect } from 'react'
import { getEscalations } from '../api/client'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Pilotage' },
  { to: '/escalations', icon: AlertTriangle, label: 'Escalations', badge: true },
  { to: '/clients', icon: Users, label: 'Clients' },
  { to: '/pipeline', icon: Zap, label: 'Pipeline' },
  { to: '/chat', icon: MessageSquare, label: 'Chat IA' },
  { to: '/settings', icon: Settings, label: 'Paramètres' },
]

export default function Layout({ children, onLogout }) {
  const [escCount, setEscCount] = useState(0)

  useEffect(() => {
    getEscalations().then(d => setEscCount(d.count || 0)).catch(() => {})
    const interval = setInterval(() => {
      getEscalations().then(d => setEscCount(d.count || 0)).catch(() => {})
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside style={{
        width: 240, background: 'var(--bg-secondary)', borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', padding: '24px 0', position: 'fixed',
        top: 0, left: 0, bottom: 0, zIndex: 50
      }}>
        {/* Logo */}
        <div style={{ padding: '0 24px 24px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: 'linear-gradient(135deg, var(--accent), #c8d420)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Shield size={20} color="#000" strokeWidth={2.5} />
            </div>
            <div>
              <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: 2, color: 'var(--accent)' }}>
                OKTAGON
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: 1.5, textTransform: 'uppercase' }}>
                SAV Intelligence
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {navItems.map(({ to, icon: Icon, label, badge }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 16px', borderRadius: 10, textDecoration: 'none',
                fontSize: 14, fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                background: isActive ? 'rgba(240,255,39,0.08)' : 'transparent',
                transition: 'all 0.2s',
                position: 'relative',
              })}
            >
              <Icon size={18} />
              {label}
              {badge && escCount > 0 && (
                <span style={{
                  marginLeft: 'auto', background: 'var(--red)', color: '#fff',
                  fontSize: 11, fontWeight: 700, padding: '1px 7px', borderRadius: 99,
                  minWidth: 20, textAlign: 'center',
                }}>
                  {escCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* System status */}
        <div style={{ padding: '12px 24px', borderTop: '1px solid var(--border)', marginBottom: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--green)', boxShadow: '0 0 6px var(--green)' }} />
            Système actif
          </div>
        </div>

        {/* Logout */}
        <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
          <button
            onClick={onLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '10px 16px', borderRadius: 10, border: 'none',
              background: 'transparent', color: 'var(--text-muted)',
              cursor: 'pointer', fontSize: 14, width: '100%',
              transition: 'color 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--red)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
          >
            <LogOut size={18} />
            Déconnexion
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, marginLeft: 240, padding: '32px 40px', minHeight: '100vh' }}>
        {children}
      </main>
    </div>
  )
}

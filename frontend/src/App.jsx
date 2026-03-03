import { Routes, Route, Navigate } from 'react-router-dom'
import { useState } from 'react'
import { isLoggedIn, login as doLogin, logout, getStats } from './api/client'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Clients from './pages/Clients'
import ClientDetail from './pages/ClientDetail'
import Pipeline from './pages/Pipeline'
import Escalations from './pages/Escalations'
import Chat from './pages/Chat'
import Settings from './pages/Settings'
import Login from './pages/Login'

export default function App() {
  const [authed, setAuthed] = useState(isLoggedIn())
  const [loginError, setLoginError] = useState('')

  const handleLogin = async (user, pass) => {
    doLogin(user, pass)
    try {
      await getStats('today')
      setAuthed(true)
      setLoginError('')
    } catch {
      logout()
      setAuthed(false)
      setLoginError('Identifiants incorrects')
    }
  }

  if (!authed) return <Login onLogin={handleLogin} error={loginError} />

  return (
    <Layout onLogout={() => { logout(); setAuthed(false) }}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/clients" element={<Clients />} />
        <Route path="/clients/:email" element={<ClientDetail />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="/escalations" element={<Escalations />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Layout>
  )
}

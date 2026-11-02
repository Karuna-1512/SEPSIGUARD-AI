import { Moon, Sun, LogOut, Bell, Menu } from 'lucide-react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import Sidebar from './Sidebar'
import { useEffect, useState } from 'react'

const titles: Record<string, string> = { '/app': 'Clinical overview', '/app/risk': 'Risk analysis', '/app/predict': 'New patient prediction', '/app/batch': 'CSV batch prediction', '/app/history': 'Prediction history', '/app/patients': 'Patients', '/app/settings': 'Settings', '/app/about': 'About SepsiGuard AI' }

export default function AppShell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [dark, setDark] = useState(() => localStorage.getItem('sg-dark') === 'true')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [logoutError, setLogoutError] = useState('')
  useEffect(() => { document.documentElement.classList.toggle('dark', dark); localStorage.setItem('sg-dark', String(dark)) }, [dark])
  const title = location.pathname.startsWith('/app/patients/') ? 'Patient details' : titles[location.pathname] || 'SepsiGuard AI'
  return <div className="app-layout">
    <Sidebar mobileOpen={mobileOpen} onNavigate={() => setMobileOpen(false)} />
    <div className="app-main">
      <header className="topbar"><div className="top-title"><button className="icon-button mobile-menu-toggle" onClick={() => setMobileOpen(x => !x)} aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}><Menu size={20} /></button><div><span className="eyebrow">SEPSIGUARD AI</span><h1>{title}</h1></div></div><div className="top-actions"><button className="icon-button notification-button" onClick={() => navigate('/app')} aria-label="Go to high-risk alerts" title="High-risk alerts are on the overview"><Bell size={18} /><span className="notification-dot" /></button><button className="icon-button" onClick={() => setDark(x => !x)} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button><div className="user-chip"><span className="avatar">{user?.full_name?.slice(0, 1) || 'U'}</span><span className="user-name">{user?.full_name}<small>{user?.role}</small></span></div><button className="icon-button" onClick={async () => { try { await logout(); navigate('/') } catch (e) { setLogoutError(e instanceof Error ? e.message : 'Sign out failed.') } }} aria-label="Sign out" title="Sign out"><LogOut size={18} /></button></div></header>
      <main id="main-content" className="content">{logoutError && <div className="error-box" role="alert" style={{ marginBottom: 12 }}><strong>Sign out failed</strong><span>{logoutError}</span><button className="button button-small button-quiet" onClick={async () => { try { await logout(); navigate('/') } catch (e) { setLogoutError(e instanceof Error ? e.message : 'Sign out failed.') } }}>Retry</button></div>}<Outlet /></main>
    </div>
  </div>
}

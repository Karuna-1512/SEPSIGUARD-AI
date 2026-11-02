import { Activity, FileClock, FileUp, FlaskConical, Info, LayoutDashboard, Settings, UsersRound } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { X } from 'lucide-react'

const links = [
  { to: '/app', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/app/risk', label: 'Risk analysis', icon: Activity },
  { to: '/app/predict', label: 'New prediction', icon: Activity },
  { to: '/app/batch', label: 'CSV batch', icon: FileUp },
  { to: '/app/history', label: 'Prediction history', icon: FileClock },
  { to: '/app/patients', label: 'Patients', icon: UsersRound },
  { to: '/app/settings', label: 'Settings', icon: Settings },
  { to: '/app/about', label: 'About & docs', icon: Info },
]

export default function Sidebar({ mobileOpen = false, onNavigate = () => {} }: { mobileOpen?: boolean; onNavigate?: () => void }) {
  return <>
    {mobileOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={onNavigate} />}
    <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
      <div className="sidebar-brand-row"><NavLink to="/app" className="brand" onClick={onNavigate}><span className="brand-mark"><Activity size={20} /></span><span><b>SepsiGuard</b><small>AI research workspace</small></span></NavLink><button className="icon-button mobile-drawer-close" aria-label="Close navigation" onClick={onNavigate}><X size={18} /></button></div>
      <div className="side-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="side-nav">{links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={onNavigate} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={18} /><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-bottom"><div className="model-mini"><span className="status-dot" /><span><b>Research mode</b><small>Not clinically validated</small></span><FlaskConical size={17} /></div><p>SepsiGuard AI · v1.0</p></div>
    </aside>
    <nav className="mobile-nav" aria-label="Mobile navigation">{links.filter(({ to }) => ['/app', '/app/predict', '/app/batch', '/app/history', '/app/patients'].includes(to)).map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} aria-label={label} className={({ isActive }) => `mobile-nav-link ${isActive ? 'active' : ''}`}><Icon size={19} /><span>{label === 'New prediction' ? 'Predict' : label === 'Prediction history' ? 'History' : label}</span></NavLink>)}</nav>
  </>
}

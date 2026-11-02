import { useCallback, useEffect, useState } from 'react'
import { Activity, ArrowRight, ClipboardList, HeartPulse, ShieldAlert, ShieldCheck, UsersRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, formatDate, formatPercent } from '../api'
import type { ModelStatus, Prediction } from '../types'
import { Empty, ErrorBox, Loading, MetricCard, RiskBadge } from '../components/UI'
import PredictionTable from '../components/PredictionTable'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, LineChart, Line, CartesianGrid, XAxis, YAxis } from 'recharts'

type Summary = { patients_analyzed: number; high_risk: number; moderate_risk: number; low_risk: number; predictions_today: number; total_predictions: number; recent_predictions: Prediction[]; high_risk_alerts: (Prediction & { acknowledged: boolean })[] }
const COLORS = ['#4d9a7b', '#d2a34a', '#c76565']

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [distribution, setDistribution] = useState<{ name: string; value: number }[]>([])
  const [trends, setTrends] = useState<{ date: string; total: number; high: number; moderate: number; low: number }[]>([])
  const [model, setModel] = useState<ModelStatus | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [s, d, t, m] = await Promise.all([
        api<Summary>('/dashboard/summary'), api<{ items: { name: string; value: number }[] }>('/dashboard/risk-distribution'),
        api<{ items: { date: string; total: number; high: number; moderate: number; low: number }[] }>('/dashboard/trends'), api<ModelStatus>('/model/status'),
      ])
      setSummary(s); setDistribution(d.items); setTrends(t.items); setModel(m)
    } catch (e) { setError(e instanceof Error ? e.message : 'Dashboard data is unavailable.') } finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])
  async function acknowledge(id: number) { try { await api(`/predictions/${id}/acknowledge`, { method: 'POST' }); await load() } catch (e) { setError(e instanceof Error ? e.message : 'Alert could not be acknowledged.') } }
  if (loading) return <Loading label="Loading dashboard data…" />
  if (error && !summary) return <ErrorBox message={error} onRetry={load} />
  const data = summary!
  const hasPredictions = data.total_predictions > 0
  return <div>
    <div className="page-intro"><div><h2>Good day, researcher.</h2><p>Review recent predicted risk, data quality and model readiness.</p></div><div className="page-actions"><Link className="button button-primary" to="/app/predict"><Activity size={16} /> New prediction</Link><Link className="button button-secondary" to="/app/batch">Upload CSV</Link></div></div>
    {error && <ErrorBox message={error} onRetry={load} />}
    <div className="metric-grid">
      <MetricCard label="Patients analyzed" value={data.patients_analyzed} hint="Unique patient IDs with saved records" icon={<UsersRound size={15} />} />
      <MetricCard label="High risk" value={data.high_risk} hint="Configured high threshold" tone="tone-high" icon={<ShieldAlert size={15} />} />
      <MetricCard label="Moderate risk" value={data.moderate_risk} hint="Configured middle range" tone="tone-moderate" icon={<Activity size={15} />} />
      <MetricCard label="Low risk" value={data.low_risk} hint="Configured low range" tone="tone-low" icon={<ShieldCheck size={15} />} />
      <MetricCard label="Predictions today" value={data.predictions_today} hint={`${data.total_predictions} total prediction records`} icon={<ClipboardList size={15} />} />
    </div>
    <div className="grid two" style={{ gridTemplateColumns: '1.05fr 1.55fr .95fr', marginBottom: 15 }}>
      <section className="panel"><div className="panel-heading"><div><h3>Risk distribution</h3><p>Saved predictions by configured category</p></div><Link className="text-link" to="/app/history">History <ArrowRight size={13} /></Link></div>
        {hasPredictions ? <><div className="chart-box"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={distribution} dataKey="value" nameKey="name" innerRadius="61%" outerRadius="83%" paddingAngle={3} stroke="none">{distribution.map((entry, i) => <Cell key={entry.name} fill={COLORS[i]} />)}</Pie><Tooltip formatter={(value, name) => [value, name]} /></PieChart></ResponsiveContainer></div><div className="chart-legend">{distribution.map((d, i) => <span key={d.name}><i className="legend-dot" style={{ background: COLORS[i] }} />{d.name} {d.value}</span>)}</div></> : <Empty title="No risk distribution yet">Prediction categories will appear after records are saved.</Empty>}
      </section>
      <section className="panel"><div className="panel-heading"><div><h3>Prediction trend</h3><p>Saved predictions by day over the past two weeks</p></div></div>{hasPredictions ? <div className="chart-box"><ResponsiveContainer width="100%" height="100%"><LineChart data={trends} margin={{ left: -22, right: 8, top: 8, bottom: 0 }}><CartesianGrid strokeDasharray="3 4" vertical={false} stroke="var(--line)" /><XAxis dataKey="date" tickFormatter={v => String(v).slice(5)} tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><Tooltip /><Line type="monotone" dataKey="total" name="Predictions" stroke="#277f74" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} /></LineChart></ResponsiveContainer></div> : <Empty title="Trend will appear here">Save predictions to see activity over time.</Empty>}</section>
      <section className="panel"><div className="panel-heading"><div><h3>High-risk alerts</h3><p>Review and acknowledge alerts</p></div><span className="risk-badge risk-high"><i />{data.high_risk_alerts.length}</span></div>{data.high_risk_alerts.length ? data.high_risk_alerts.slice(0, 4).map(p => <div className="alert-row" key={p.id}><span className="alert-mark"><ShieldAlert size={14} /></span><div className="alert-copy"><b>High-risk prediction detected</b><small>{p.patient_id} · {p.age == null ? 'Age not provided' : `${p.age} years`} · {formatPercent(p.prediction_probability)} · {formatDate(p.created_at)}</small><div className="alert-actions"><Link className="text-link" to={`/app/patients/${encodeURIComponent(p.patient_id)}`}>Patient</Link><Link className="text-link" to={`/app/predictions/${p.id}`}>Prediction</Link>{!p.acknowledged && <button className="button button-small button-quiet" onClick={() => acknowledge(p.id)}>Acknowledge</button>}</div></div></div>) : <Empty title="No high-risk alerts">Alerts will be listed when saved predictions meet the configured threshold.</Empty>}</section>
    </div>
    <div className="grid two" style={{ gridTemplateColumns: '1.7fr 1fr' }}>
      <section className="panel"><div className="panel-heading"><div><h3>Recent predictions</h3><p>Latest saved results for your workspace</p></div><Link className="text-link" to="/app/history">View all <ArrowRight size={13} /></Link></div><PredictionTable items={data.recent_predictions} /></section>
      <div className="stack">
        <section className="panel"><div className="panel-heading"><div><h3>Model status</h3><p>Current prediction engine</p></div></div>{model && <><div className="model-status-card"><span className="model-icon"><HeartPulse size={20} /></span><span className="model-status-copy"><b>{model.model_name}</b><small>Version {model.model_version} · {model.number_of_features} inputs · {model.time_steps} time steps</small></span><span className={`status-label ${model.status.startsWith('loaded') ? 'loaded' : model.status === 'error' ? 'error' : ''}`}>{model.status.replace(/_/g, ' ')}</span></div>{model.message && <p className="small-text" style={{ lineHeight: 1.5, marginTop: 12 }}>{model.message}</p>}{model.error && <p className="form-error">{model.error}</p>}</>}</section>
        <section className="panel"><div className="panel-heading"><div><h3>System status</h3><p>Local research workspace</p></div><span className="status-label loaded">Online</span></div><div className="setting-row"><div><b>Prediction API</b><small>Health endpoint available</small></div><span className="risk-badge risk-low">Ready</span></div><div className="setting-row"><div><b>Database</b><small>Persistent history enabled</small></div><span className="risk-badge risk-low">Connected</span></div></section>
      </div>
    </div>
  </div>
}

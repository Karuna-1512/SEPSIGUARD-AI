import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Empty, ErrorBox, Loading } from '../components/UI'

type Distribution = { name: string; value: number }[]
type Trend = { date: string; total: number; high: number; moderate: number; low: number }[]
const colors: Record<string, string> = { LOW: '#4d9a7b', MODERATE: '#d2a34a', HIGH: '#c76565' }

export default function RiskAnalysisPage() {
  const [distribution, setDistribution] = useState<Distribution>([])
  const [trend, setTrend] = useState<Trend>([])
  const [thresholds, setThresholds] = useState<{ low_threshold: number; high_threshold: number } | null>(null)
  const [days, setDays] = useState(30)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  async function load() {
    setLoading(true); setError('')
    try {
      const [d, t, s] = await Promise.all([
        api<{ items: Distribution }>('/dashboard/risk-distribution'),
        api<{ items: Trend }>(`/dashboard/trends?days=${days}`),
        api<{ prediction: { low_threshold: number; high_threshold: number } }>('/settings'),
      ])
      setDistribution(d.items); setTrend(t.items); setThresholds(s.prediction)
    } catch (e) { setError(e instanceof Error ? e.message : 'Risk analysis could not be loaded.') } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [days])
  if (loading) return <Loading label="Loading risk analysis…" />
  return <div>
    <div className="page-intro"><div><h2>Risk analysis</h2><p>Review saved prediction categories and activity over time. These summaries describe this workspace's records.</p></div><div className="field"><label htmlFor="analysis-days">Trend window</label><select id="analysis-days" value={days} onChange={e => setDays(Number(e.target.value))}><option value={7}>7 days</option><option value={14}>14 days</option><option value={30}>30 days</option><option value={90}>90 days</option></select></div></div>
    {error && <ErrorBox message={error} onRetry={load} />}
    <div className="callout" style={{ marginBottom: 14 }}><span className="status-dot" /><span>{thresholds ? `Current configurable boundaries: LOW below ${(thresholds.low_threshold * 100).toFixed(1)}%, MODERATE below ${(thresholds.high_threshold * 100).toFixed(1)}%, HIGH at or above that.` : 'Threshold boundaries are unavailable.'} Thresholds are research parameters and are not clinically validated.</span></div>
    <div className="grid two" style={{ gridTemplateColumns: '1fr 1.7fr' }}><section className="panel"><div className="panel-heading"><div><h3>All-time category distribution</h3><p>Counts of saved prediction records</p></div></div>{distribution.reduce((n, x) => n + x.value, 0) ? <div className="chart-box"><ResponsiveContainer width="100%" height="100%"><BarChart data={distribution} margin={{ left: -17, right: 10, top: 10, bottom: 0 }}><CartesianGrid strokeDasharray="3 4" vertical={false} stroke="var(--line)" /><XAxis dataKey="name" tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><Tooltip /><Bar dataKey="value" name="Saved predictions" radius={[5, 5, 0, 0]}>{distribution.map(item => <Cell key={item.name} fill={colors[item.name] || '#758d88'} />)}</Bar></BarChart></ResponsiveContainer></div> : <Empty title="No prediction records yet">Category distribution appears after predictions are saved.</Empty>}</section>
      <section className="panel"><div className="panel-heading"><div><h3>Category activity</h3><p>Daily saved prediction counts over the selected window</p></div></div>{trend.some(row => row.total > 0) ? <div className="chart-box chart-tall"><ResponsiveContainer width="100%" height="100%"><LineChart data={trend} margin={{ left: -20, right: 10, top: 8, bottom: 0 }}><CartesianGrid strokeDasharray="3 4" vertical={false} stroke="var(--line)" /><XAxis dataKey="date" tickFormatter={value => String(value).slice(5)} tick={{ fontSize: 8, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><YAxis allowDecimals={false} tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><Tooltip /><Line type="monotone" dataKey="high" name="HIGH" stroke={colors.HIGH} strokeWidth={2} dot={false} /><Line type="monotone" dataKey="moderate" name="MODERATE" stroke={colors.MODERATE} strokeWidth={2} dot={false} /><Line type="monotone" dataKey="low" name="LOW" stroke={colors.LOW} strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div> : <Empty title="No trend data in this window">Daily category counts will appear after records are saved.</Empty>}</section></div>
    <section className="panel" style={{ marginTop: 14 }}><div className="panel-heading"><div><h3>Daily counts</h3><p>Aggregated saved predictions; no treatment recommendations are generated.</p></div></div><div className="table-wrap"><table className="data-table"><thead><tr><th>Date</th><th>All</th><th>High</th><th>Moderate</th><th>Low</th></tr></thead><tbody>{trend.filter(row => row.total > 0).slice().reverse().map(row => <tr key={row.date}><td>{row.date}</td><td>{row.total}</td><td style={{ color: colors.HIGH }}>{row.high}</td><td style={{ color: colors.MODERATE }}>{row.moderate}</td><td style={{ color: colors.LOW }}>{row.low}</td></tr>)}</tbody></table>{!trend.some(row => row.total > 0) && <Empty title="No daily records to show" />}</div></section>
  </div>
}

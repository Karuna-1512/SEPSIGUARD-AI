import { FormEvent, useCallback, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Filter, Search } from 'lucide-react'
import { api } from '../api'
import type { Prediction } from '../types'
import { Empty, ErrorBox, Loading, RiskBadge } from '../components/UI'
import PredictionTable from '../components/PredictionTable'

const PAGE_SIZE = 20
type Listing = { items: Prediction[]; total: number; offset: number; limit: number }

export default function HistoryPage() {
  const [data, setData] = useState<Listing | null>(null)
  const [query, setQuery] = useState('')
  const [risk, setRisk] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [applied, setApplied] = useState({ query: '', risk: '', start: '', end: '', offset: 0 })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const load = useCallback(async () => {
    setLoading(true); setError('')
    const params = new URLSearchParams({ offset: String(applied.offset), limit: String(PAGE_SIZE) })
    if (applied.query) params.set('q', applied.query)
    if (applied.risk) params.set('risk_category', applied.risk)
    if (applied.start) params.set('start_date', new Date(`${applied.start}T00:00:00`).toISOString())
    if (applied.end) params.set('end_date', new Date(`${applied.end}T23:59:59`).toISOString())
    try { setData(await api<Listing>(`/predictions?${params}`)) } catch (e) { setError(e instanceof Error ? e.message : 'History could not be loaded.') } finally { setLoading(false) }
  }, [applied])
  useEffect(() => { load() }, [load])
  function submit(event: FormEvent) { event.preventDefault(); setApplied({ query: query.trim(), risk, start, end, offset: 0 }) }
  return <div>
    <div className="page-intro"><div><h2>Prediction history</h2><p>Search and filter saved prediction records. Data is stored in the configured database.</p></div></div>
    <section className="panel"><form className="form-grid three" onSubmit={submit} style={{ alignItems: 'end', marginBottom: 16 }}><div className="field"><label htmlFor="history-search">Search patient ID</label><input id="history-search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Patient identifier" /></div><div className="field"><label htmlFor="risk-filter">Risk category</label><select id="risk-filter" value={risk} onChange={e => setRisk(e.target.value)}><option value="">All categories</option><option>HIGH</option><option>MODERATE</option><option>LOW</option></select></div><div className="field"><label htmlFor="history-start">From date</label><input id="history-start" type="date" value={start} onChange={e => setStart(e.target.value)} /></div><div className="field"><label htmlFor="history-end">To date</label><input id="history-end" type="date" value={end} onChange={e => setEnd(e.target.value)} /></div><div className="page-actions"><button className="button button-primary" type="submit"><Search size={14} /> Apply filters</button><button className="button button-secondary" type="button" onClick={() => { setQuery(''); setRisk(''); setStart(''); setEnd(''); setApplied({ query: '', risk: '', start: '', end: '', offset: 0 }) }}><Filter size={14} /> Clear</button></div></form>
      {error && <ErrorBox message={error} onRetry={load} />}
      {loading ? <Loading label="Loading prediction records…" /> : data?.items.length ? <><PredictionTable items={data.items} /><div className="step-actions"><span className="small-text">Showing {data.offset + 1}–{Math.min(data.offset + data.items.length, data.total)} of {data.total}</span><div style={{ display: 'flex', gap: 7 }}><button className="button button-secondary button-small" aria-label="Previous page" disabled={data.offset === 0} onClick={() => setApplied(a => ({ ...a, offset: Math.max(0, a.offset - PAGE_SIZE) }))}><ChevronLeft size={14} /> Previous</button><button className="button button-secondary button-small" disabled={data.offset + PAGE_SIZE >= data.total} onClick={() => setApplied(a => ({ ...a, offset: a.offset + PAGE_SIZE }))}>Next <ChevronRight size={14} /></button></div></div></> : !error && <Empty title="No predictions match these filters">Clear filters, or run a prediction to add a record.</Empty>}
    </section>
  </div>
}

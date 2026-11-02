import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Plus, Search, UserRound, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, formatDate } from '../api'
import type { Patient } from '../types'
import { Empty, ErrorBox, Loading } from '../components/UI'

type PatientList = { items: Patient[]; total: number }
export default function PatientsPage() {
  const [data, setData] = useState<PatientList | null>(null)
  const [query, setQuery] = useState('')
  const [applied, setApplied] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ patient_id: '', age: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const load = useCallback(async () => { setLoading(true); setError(''); try { setData(await api<PatientList>(`/patients?limit=100${applied ? `&q=${encodeURIComponent(applied)}` : ''}`)) } catch (e) { setError(e instanceof Error ? e.message : 'Patients could not be loaded.') } finally { setLoading(false) } }, [applied])
  useEffect(() => { load() }, [load])
  async function createPatient(event: FormEvent) {
    event.preventDefault(); setError('')
    try {
      await api('/patients?patient_id=' + encodeURIComponent(form.patient_id.trim()), { method: 'POST', body: JSON.stringify({ age: Number(form.age) }) })
      setShowAdd(false); setForm({ patient_id: '', age: '' }); await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Patient could not be added.') }
  }
  return <div>
    <div className="page-intro"><div><h2>Patients</h2><p>Patient records are created by a prediction or by adding an identifier and age.</p></div><button className="button button-primary" onClick={() => setShowAdd(x => !x)}>{showAdd ? <X size={15} /> : <Plus size={15} />}{showAdd ? 'Close' : 'Add patient'}</button></div>
    {error && <ErrorBox message={error} onRetry={load} />}
    {showAdd && <section className="panel" style={{ marginBottom: 14 }}><div className="panel-heading"><div><h3>Add patient profile</h3><p>Store only the identifier and age needed for this research workflow.</p></div></div><form onSubmit={createPatient}><div className="form-grid three"><div className="field"><label htmlFor="new-patient-id">Patient ID</label><input id="new-patient-id" required maxLength={80} value={form.patient_id} onChange={e => setForm({ ...form, patient_id: e.target.value })} /></div><div className="field"><label htmlFor="new-age">Age (years)</label><input id="new-age" type="number" min="0" max="120" required value={form.age} onChange={e => setForm({ ...form, age: e.target.value })} /></div></div><div className="step-actions"><span /><button className="button button-primary" type="submit">Save patient</button></div></form></section>}
    <section className="panel"><div className="panel-heading"><div><h3>Patient registry</h3><p>{data?.total ?? 0} records</p></div></div><form className="page-actions" onSubmit={e => { e.preventDefault(); setApplied(query.trim()) }} style={{ marginBottom: 14 }}><div className="field" style={{ minWidth: 220 }}><label htmlFor="patient-search">Search patient ID</label><input id="patient-search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search…" /></div><button className="button button-secondary button-small" type="submit"><Search size={14} /> Search</button></form>
      {loading ? <Loading label="Loading patient records…" /> : data?.items.length ? <div className="table-wrap"><table className="data-table"><thead><tr><th>Patient ID</th><th>Age</th><th>Last updated</th><th /></tr></thead><tbody>{data.items.map(p => <tr key={p.patient_id}><td><Link className="patient-link" to={`/app/patients/${encodeURIComponent(p.patient_id)}`}><UserRound size={13} style={{ verticalAlign: 'middle', marginRight: 5 }} />{p.patient_id}</Link></td><td>{p.age ?? '—'}</td><td>{formatDate(p.updated_at)}</td><td><Link className="text-link" to={`/app/patients/${encodeURIComponent(p.patient_id)}`}>View</Link></td></tr>)}</tbody></table></div> : !error && <Empty title="No patients found">Add a patient or create one during a prediction.</Empty>}
    </section>
  </div>
}

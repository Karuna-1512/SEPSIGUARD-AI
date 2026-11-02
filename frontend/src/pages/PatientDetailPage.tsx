import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, UserRound } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { api, formatDate, formatPercent } from '../api'
import type { Observation, Prediction, Patient } from '../types'
import { Empty, ErrorBox, Loading, RiskBadge } from '../components/UI'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type History = { patient: Patient; predictions: Prediction[] }
const measurements = [
  ['heart_rate', 'Heart rate'], ['respiratory_rate', 'Respiratory rate'], ['temperature', 'Temperature'],
  ['systolic_bp', 'Systolic BP'], ['diastolic_bp', 'Diastolic BP'], ['oxygen_saturation', 'Oxygen saturation'],
  ['wbc', 'WBC'], ['lactate', 'Lactate'], ['creatinine', 'Creatinine'], ['platelets', 'Platelets'], ['bilirubin', 'Bilirubin'],
] as const

export default function PatientDetailPage() {
  const { patientId = '' } = useParams()
  const [data, setData] = useState<History | null>(null)
  const [measurement, setMeasurement] = useState<string>('heart_rate')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  async function load() { setLoading(true); setError(''); try { setData(await api<History>(`/patients/${encodeURIComponent(patientId)}/history`)) } catch (e) { setError(e instanceof Error ? e.message : 'Patient history could not be loaded.') } finally { setLoading(false) } }
  useEffect(() => { load() }, [patientId])
  const probabilityTrend = useMemo(() => (data?.predictions || []).slice().reverse().map((p, i) => ({ index: `P${i + 1}`, probability: p.prediction_probability * 100, timestamp: formatDate(p.created_at) })), [data])
  const latest = data?.predictions[0]
  const observations = latest?.input_data?.observations || []
  const featureTrend = observations.map((row: Observation) => ({ step: `T${row.time_step}`, value: row[measurement as keyof Observation] ?? null }))
  if (loading) return <Loading label="Loading patient record…" />
  if (error) return <ErrorBox message={error} onRetry={load} />
  if (!data) return <Empty title="Patient record unavailable" />
  return <div>
    <div className="page-intro"><div><Link to="/app/patients" className="text-link"><ArrowLeft size={13} /> All patients</Link><h2 style={{ marginTop: 9 }}>{data.patient.patient_id}</h2><p>Patient history and saved research outputs.</p></div><Link className="button button-primary" to={`/app/predict?patient=${encodeURIComponent(data.patient.patient_id)}`}>New prediction <ArrowRight size={15} /></Link></div>
    <div className="grid two" style={{ gridTemplateColumns: '1fr 2fr', marginBottom: 14 }}><section className="panel"><div className="panel-heading"><div><h3>Patient information</h3><p>Stored profile details</p></div><span className="model-icon"><UserRound size={18} /></span></div><div className="review-list"><div className="review-item"><span>Patient ID</span><strong>{data.patient.patient_id}</strong></div><div className="review-item"><span>Age</span><strong>{data.patient.age ?? '—'}{data.patient.age != null ? ' years' : ''}</strong></div><div className="review-item"><span>Predictions</span><strong>{data.predictions.length}</strong></div></div></section>
      <section className="panel"><div className="panel-heading"><div><h3>Predicted risk over time</h3><p>Each point represents a saved model output.</p></div></div>{probabilityTrend.length ? <div className="chart-box chart-tall"><ResponsiveContainer width="100%" height="100%"><LineChart data={probabilityTrend} margin={{ left: -17, right: 9, top: 10, bottom: 0 }}><CartesianGrid strokeDasharray="3 4" vertical={false} stroke="var(--line)" /><XAxis dataKey="index" tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><Tooltip formatter={v => [`${Number(v).toFixed(1)}%`, 'Predicted probability']} labelFormatter={(label, payload) => payload?.[0]?.payload.timestamp || label} /><Line dataKey="probability" type="monotone" stroke="#247f74" strokeWidth={2.5} dot={{ r: 4 }} /></LineChart></ResponsiveContainer></div> : <Empty title="No prediction history">Saved predictions will appear here.</Empty>}</section></div>
    {latest && <section className="panel" style={{ marginBottom: 14 }}><div className="panel-heading"><div><h3>Latest clinical sequence</h3><p>Measurements from the most recent prediction record.</p></div><div className="field"><label htmlFor="patient-measurement">Measurement</label><select id="patient-measurement" value={measurement} onChange={e => setMeasurement(e.target.value)}>{measurements.map(([name, label]) => <option key={name} value={name}>{label}</option>)}</select></div></div><div className="chart-box"><ResponsiveContainer width="100%" height="100%"><LineChart data={featureTrend} margin={{ left: -17, right: 9, top: 10, bottom: 0 }}><CartesianGrid strokeDasharray="3 4" vertical={false} stroke="var(--line)" /><XAxis dataKey="step" tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><Tooltip /><Line dataKey="value" connectNulls={false} stroke="#6985ad" strokeWidth={2.2} dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div></section>}
    <section className="panel"><div className="panel-heading"><div><h3>Prediction comparison</h3><p>Compare category, probability, input completeness and model version.</p></div></div>{data.predictions.length ? <div className="table-wrap"><table className="data-table"><thead><tr><th>Timestamp</th><th>Predicted risk</th><th>Probability</th><th>Completeness</th><th>Missing</th><th>Model version</th><th /></tr></thead><tbody>{data.predictions.map(p => <tr key={p.id}><td>{formatDate(p.created_at)}</td><td><RiskBadge category={p.risk_category} /></td><td>{formatPercent(p.prediction_probability)}</td><td>{p.input_completeness.toFixed(1)}%</td><td>{p.missing_values}</td><td>{p.model_version}</td><td><Link className="text-link" to={`/app/predictions/${p.id}`}>Open</Link></td></tr>)}</tbody></table></div> : <Empty title="No prediction history">Create a prediction to begin comparing results.</Empty>}</section>
  </div>
}

import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { ArrowLeft, Info, Trash2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, formatDate, formatPercent } from '../api'
import { useAuth } from '../auth'
import type { Observation, Prediction } from '../types'
import { Empty, ErrorBox, Loading, RiskBadge } from '../components/UI'
import { GenerateReportButton } from '../components/GenerateReportButton'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const measurements = [
  ['heart_rate', 'Heart rate'], ['respiratory_rate', 'Respiratory rate'], ['temperature', 'Temperature'],
  ['systolic_bp', 'Systolic BP'], ['diastolic_bp', 'Diastolic BP'], ['oxygen_saturation', 'Oxygen saturation'],
  ['wbc', 'WBC'], ['lactate', 'Lactate'], ['creatinine', 'Creatinine'], ['platelets', 'Platelets'], ['bilirubin', 'Bilirubin'], ['age', 'Age'],
] as const

export default function PredictionDetailPage() {
  const { predictionId = '' } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [item, setItem] = useState<Prediction | null>(null)
  const [measurement, setMeasurement] = useState<string>('heart_rate')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  useEffect(() => { api<Prediction>(`/predictions/${predictionId}`).then(setItem).catch(e => setError(e instanceof Error ? e.message : 'Prediction could not be loaded.')).finally(() => setLoading(false)) }, [predictionId])
  if (loading) return <Loading label="Loading prediction detail…" />
  if (error && !item) return <ErrorBox message={error} onRetry={() => location.reload()} />
  if (!item) return <Empty title="Prediction record unavailable" />
  async function deletePrediction() {
    if (!window.confirm('Delete this prediction record and its stored measurements?')) return
    setDeleting(true); setError('')
    try { await api(`/predictions/${predictionId}`, { method: 'DELETE' }); navigate('/app/history') }
    catch (e) { setError(e instanceof Error ? e.message : 'Prediction could not be deleted.') } finally { setDeleting(false) }
  }
  const observations = item.input_data?.observations || []
  const series = observations.map((row: Observation) => ({ step: `T${row.time_step}`, value: row[measurement as keyof Observation] ?? null }))
  return <div>
    <div className="page-intro"><div><Link className="text-link" to="/app/history"><ArrowLeft size={13} /> Prediction history</Link><h2 style={{ marginTop: 8 }}>Prediction #{item.id}</h2><p>Patient <Link className="patient-link" to={`/app/patients/${encodeURIComponent(item.patient_id)}`}>{item.patient_id}</Link> · {formatDate(item.created_at)}</p></div><div className="page-actions"><GenerateReportButton predictionId={item.id} />{user?.role === 'administrator' && <button className="button button-danger" disabled={deleting} onClick={deletePrediction}><Trash2 size={14} /> {deleting ? 'Deleting…' : 'Delete record'}</button>}</div></div>
    {error && <ErrorBox message={error} />}
    {item.synthetic_data && <div className="error-box" style={{ marginBottom: 14 }}><strong>Synthetic training data</strong><span>This GRU was trained using synthetic data. Its output is for software testing and has no clinical meaning.</span></div>}
    <section className="panel" style={{ marginBottom: 14 }}><div className="panel-heading"><div><h3>Predicted sepsis risk</h3><p>Prediction output · model version {item.model_version}</p></div><RiskBadge category={item.risk_category} /></div><div className="result-grid"><div className="result-summary"><div className="risk-gauge" style={{ ['--prob' as string]: `${item.prediction_probability * 100}`, ['--gauge-color' as string]: item.risk_category === 'HIGH' ? '#c76565' : item.risk_category === 'MODERATE' ? '#d2a34a' : '#4d9a7b' } as CSSProperties}><div className="gauge-center"><strong>{formatPercent(item.prediction_probability)}</strong><small>probability</small></div></div><h2>{item.risk_category} category</h2><p>Configured thresholds are research parameters and are not clinically validated.</p></div><div><div className="prediction-metadata"><div className="review-item"><span>Patient ID</span><strong>{item.patient_id}</strong></div><div className="review-item"><span>Age</span><strong>{item.age ?? '—'}{item.age != null ? ' years' : ''}</strong></div><div className="review-item"><span>Prediction time</span><strong>{formatDate(item.created_at)}</strong></div><div className="review-item"><span>Model version</span><strong>{item.model_version}</strong></div><div className="review-item"><span>Input completeness</span><strong>{item.input_completeness.toFixed(1)}%</strong></div><div className="review-item"><span>Missing values</span><strong>{item.missing_values}</strong></div><div className="review-item"><span>Input source</span><strong>{item.input_source}</strong></div></div><div className="callout" style={{ marginTop: 12 }}><Info size={15} /><span>{item.explanation ? 'Model explanation is available for this record.' : 'An explanation is unavailable for this record. Model associations do not establish cause.'}</span></div></div></div></section>
    <section className="panel"><div className="panel-heading"><div><h3>Clinical time-series snapshot</h3><p>Values submitted for this prediction.</p></div><div className="field"><label htmlFor="detail-measurement">Measurement</label><select id="detail-measurement" value={measurement} onChange={e => setMeasurement(e.target.value)}>{measurements.map(([name, label]) => <option key={name} value={name}>{label}</option>)}</select></div></div><div className="chart-box chart-tall"><ResponsiveContainer width="100%" height="100%"><LineChart data={series} margin={{ left: -18, right: 9, top: 10, bottom: 0 }}><CartesianGrid strokeDasharray="3 4" vertical={false} stroke="var(--line)" /><XAxis dataKey="step" tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><Tooltip /><Line dataKey="value" name={measurements.find(([key]) => key === measurement)?.[1]} connectNulls={false} stroke="#247f74" strokeWidth={2.5} dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div></section>
  </div>
}

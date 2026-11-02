import { useEffect, useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { AlertCircle, ArrowLeft, ArrowRight, Check, Info, Sparkles } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, formatDate, formatPercent, ApiError } from '../api'
import { ErrorBox, Loading, RiskBadge } from '../components/UI'
import type { Prediction, Schema } from '../types'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { GenerateReportButton } from '../components/GenerateReportButton'

const stepTitles = ['Patient information', 'Vital signs', 'Laboratory values', 'Review & validate', 'Sepsis risk assessment']
const VITAL_NAMES = new Set(['heart_rate', 'respiratory_rate', 'temperature', 'systolic_bp', 'diastolic_bp', 'oxygen_saturation'])
const INPUT_RANGES: Record<string, [number, number]> = {
  heart_rate: [1, 300], respiratory_rate: [1, 100], temperature: [25, 45],
  systolic_bp: [30, 300], diastolic_bp: [10, 200], oxygen_saturation: [0, 100],
  wbc: [0, 500], lactate: [0, 50], creatinine: [0, 100], platelets: [0, 2000], bilirubin: [0, 100],
}
type Profile = { patient_id: string; age: string }

export default function PredictionPage() {
  const [schema, setSchema] = useState<Schema | null>(null)
  const [searchParams] = useSearchParams()
  const [schemaError, setSchemaError] = useState('')
  const [step, setStep] = useState(0)
  const [timeStep, setTimeStep] = useState(0)
  const [profile, setProfile] = useState<Profile>({ patient_id: searchParams.get('patient') || '', age: '' })
  const [matrix, setMatrix] = useState<string[][]>([])
  const [validation, setValidation] = useState<{ missing_values: number; input_completeness: number } | null>(null)
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [selectedMeasurement, setSelectedMeasurement] = useState('heart_rate')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api<Schema>('/model/schema').then(data => {
      setSchema(data)
      setMatrix(Array.from({ length: data.time_steps }, () => Array(data.number_of_features).fill('')))
    }).catch(e => setSchemaError(e instanceof Error ? e.message : 'Clinical schema unavailable.'))
  }, [])

  const definitions = schema?.features || []
  const inputFields = definitions.filter(field => field.name !== 'age')
  const missing = useMemo(() => matrix.reduce((total, row) => total + row.filter((value, index) => definitions[index]?.name !== 'age' && value.trim() === '').length, 0) + (profile.age.trim() ? 0 : 1), [matrix, profile.age, definitions])
  if (!schema && !schemaError) return <Loading label="Loading the clinical input schema…" />
  if (!schema && schemaError) return <ErrorBox message={schemaError} onRetry={() => location.reload()} />

  function setProfileValue(key: keyof Profile, value: string) {
    setValidation(null); setProfile(current => ({ ...current, [key]: value }))
  }
  function setClinicalValue(index: number, value: string) {
    setValidation(null)
    setMatrix(current => current.map((row, rowIndex) => rowIndex === timeStep ? row.map((cell, columnIndex) => columnIndex === index ? value : cell) : row))
  }
  function makePayload() {
    if (!profile.patient_id.trim()) throw new Error('Patient ID is required.')
    if (!profile.age.trim() || !Number.isInteger(Number(profile.age)) || Number(profile.age) < 0 || Number(profile.age) > 120) throw new Error('Enter an age from 0 to 120 years.')
    const observations = matrix.map((row, rowIndex) => {
      const values = inputFields.map(field => {
        const index = definitions.findIndex(item => item.name === field.name)
        const value = row[index]?.trim() ?? ''
        if (!value) throw new Error(`Enter ${field.label} for time step ${rowIndex + 1}.`)
        const number = Number(value)
        if (!Number.isFinite(number)) throw new Error(`${field.label} at time step ${rowIndex + 1} must be a finite number.`)
        const [minimum, maximum] = INPUT_RANGES[field.name]
        if (number < minimum || number > maximum) throw new Error(`${field.label} at time step ${rowIndex + 1} must be between ${minimum} and ${maximum} ${field.unit}.`)
        return number
      })
      return Object.fromEntries([['time_step', rowIndex + 1], ...inputFields.map((field, index) => [field.name, values[index]])])
    })
    return { patient_id: profile.patient_id.trim(), age: Number(profile.age), observations }
  }
  async function validate() {
    setError(''); setBusy(true)
    try {
      const result = await api<{ missing_values: number; input_completeness: number }>('/predict/validate', { method: 'POST', body: JSON.stringify(makePayload()) })
      setValidation(result)
    } catch (e) { setError(e instanceof ApiError || e instanceof Error ? e.message : 'Input validation failed.') }
    finally { setBusy(false) }
  }
  async function runPrediction() {
    setError(''); setBusy(true)
    try {
      const result = await api<{ prediction: Prediction }>('/predict', { method: 'POST', body: JSON.stringify(makePayload()) })
      setPrediction(result.prediction); setStep(4)
    } catch (e) { setError(e instanceof Error ? e.message : 'Prediction could not be completed.') }
    finally { setBusy(false) }
  }
  function next() { setError(''); setStep(current => Math.min(current + 1, 3)) }

  const observations = prediction?.input_data?.observations || []
  const selectedField = definitions.find(field => field.name === selectedMeasurement) || definitions[0]
  const chartData = observations.map(item => ({ step: `T${item.time_step}`, value: item[selectedField?.name as keyof typeof item] ?? null }))
  const categoryColor = prediction?.risk_category === 'HIGH' ? '#c76565' : prediction?.risk_category === 'MODERATE' ? '#d2a34a' : '#4d9a7b'
  const visibleFields = definitions.filter(field => step === 1 ? VITAL_NAMES.has(field.name) : !VITAL_NAMES.has(field.name) && field.name !== 'age')

  return <div>
    <div className="page-intro"><div><h2>New patient prediction</h2><p>Enter the required measurements for each time step, then review the complete sequence.</p></div>{prediction && <Link className="button button-secondary button-small" to={`/app/patients/${encodeURIComponent(prediction.patient_id)}`}>Patient history <ArrowRight size={14} /></Link>}</div>
    {schemaError && <ErrorBox message={schemaError} onRetry={() => location.reload()} />}
    {error && <ErrorBox message={error} />}
    <div className="progress-steps" aria-label="Prediction workflow">{stepTitles.map((title, index) => <div key={title} className={`progress-step ${step === index ? 'active' : step > index ? 'done' : ''}`} aria-current={step === index ? 'step' : undefined}><span>{step > index ? <Check size={13} /> : index + 1}</span>{title}</div>)}</div>

    {step === 0 && <section className="panel"><div className="panel-heading"><div><h3>Patient information</h3><p>Patient ID and age are required for the sequence.</p></div></div><div className="form-grid three"><div className="field"><label htmlFor="patient-id">Patient ID <span className="form-error">*</span></label><input id="patient-id" value={profile.patient_id} maxLength={80} onChange={event => setProfileValue('patient_id', event.target.value)} placeholder="e.g. Research-001" required /></div><div className="field"><label htmlFor="age">Age <span className="form-error">*</span> <small>years</small></label><input id="age" type="number" min="0" max="120" step="1" value={profile.age} onChange={event => setProfileValue('age', event.target.value)} required /></div></div><div className="step-actions"><span /><button className="button button-primary" onClick={next}>Continue <ArrowRight size={15} /></button></div></section>}

    {(step === 1 || step === 2) && <section className="panel"><div className="panel-heading"><div><h3>{step === 1 ? 'Vital signs' : 'Laboratory values'} · Time step {timeStep + 1}</h3><p>All values are required. Enter the clinical units shown for each measurement.</p></div><span className="risk-badge risk-low">{step === 1 ? 'Vital signs' : 'Laboratory values'}</span></div><div className="step-toolbar"><div className="step-tabs" aria-label="Select time step">{Array.from({ length: schema!.time_steps }, (_, index) => <button key={index} className={`step-tab ${timeStep === index ? 'active' : ''}`} onClick={() => setTimeStep(index)} aria-label={`Time step ${index + 1}`} aria-current={timeStep === index ? 'step' : undefined}>{index + 1}</button>)}</div><span className="small-text">Time step {timeStep + 1} of {schema!.time_steps}</span></div><div className="feature-grid">{visibleFields.map(field => { const index = definitions.findIndex(item => item.name === field.name); const [minimum, maximum] = INPUT_RANGES[field.name]; return <div className="feature-field" key={field.name}><label htmlFor={`clinical-${field.name}`}>{field.label}<small>{field.unit} · {minimum}–{maximum}</small></label><input id={`clinical-${field.name}`} type="number" min={minimum} max={maximum} step="any" inputMode="decimal" value={matrix[timeStep]?.[index] || ''} onChange={event => setClinicalValue(index, event.target.value)} aria-label={`${field.label}, time step ${timeStep + 1}`} required /></div> })}</div><div className="step-actions"><button className="button button-secondary" onClick={() => setStep(step - 1)}><ArrowLeft size={15} /> Back</button><button className="button button-primary" onClick={next}>Continue <ArrowRight size={15} /></button></div></section>}

    {step === 3 && <section className="panel"><div className="panel-heading"><div><h3>Review and validate</h3><p>Confirm that every required field is present before requesting a risk assessment.</p></div></div><div className="review-list"><div className="review-item"><span>Patient ID</span><strong>{profile.patient_id || '—'}</strong></div><div className="review-item"><span>Age</span><strong>{profile.age ? `${profile.age} years` : '—'}</strong></div><div className="review-item"><span>Sequence shape</span><strong>{schema!.time_steps} × {schema!.number_of_features}</strong></div><div className="review-item"><span>Missing values</span><strong>{missing}</strong></div><div className="review-item"><span>Clinical measurements</span><strong>{schema!.number_of_features}</strong></div><div className="review-item"><span>Model target</span><strong>sepsis_label</strong></div></div><div className="step-actions"><button className="button button-secondary" onClick={() => setStep(2)}><ArrowLeft size={15} /> Back to values</button><button className="button button-secondary" disabled={busy} onClick={validate}>{busy ? 'Validating…' : 'Validate input'}</button>{validation && <button className="button button-primary" disabled={busy} onClick={runPrediction}>Run risk assessment <Sparkles size={15} /></button>}</div></section>}

    {step === 4 && prediction && <div className="stack"><section className="panel"><div className="panel-heading"><div><h3>Sepsis Risk Assessment</h3><p>Saved prediction · {formatDate(prediction.created_at)}</p></div><RiskBadge category={prediction.risk_category} /></div>{prediction.synthetic_data && <div className="error-box" style={{ marginBottom: 14 }}><strong>Synthetic training data</strong><span>This GRU was trained using synthetic data. Its output is for software testing and has no clinical meaning.</span></div>}<div className="result-grid"><div className="result-summary"><div className="risk-gauge" style={{ ['--prob' as string]: `${prediction.prediction_probability * 100}`, ['--gauge-color' as string]: categoryColor } as CSSProperties}><div className="gauge-center"><strong>{formatPercent(prediction.prediction_probability)}</strong><small>model output</small></div></div><h2>{prediction.prediction}</h2><RiskBadge category={prediction.risk_category} /><p>Research output only · not a diagnosis.</p></div><div><div className="prediction-metadata"><div className="review-item"><span>Patient ID</span><strong>{prediction.patient_id}</strong></div><div className="review-item"><span>Age</span><strong>{prediction.age ?? '—'}{prediction.age != null ? ' years' : ''}</strong></div><div className="review-item"><span>Risk score</span><strong>{prediction.risk_score.toFixed(1)}%</strong></div><div className="review-item"><span>Risk level</span><strong>{prediction.risk_level}</strong></div><div className="review-item"><span>Model version</span><strong>{prediction.model_version}</strong></div><div className="review-item"><span>Time steps</span><strong>{observations.length}</strong></div></div><div className="result-actions"><GenerateReportButton predictionId={prediction.id} /><Link className="button button-secondary" to={`/app/patients/${encodeURIComponent(prediction.patient_id)}`}>Patient history <ArrowRight size={14} /></Link><button className="button button-secondary" onClick={() => { setPrediction(null); setValidation(null); setStep(0); setProfile({ patient_id: '', age: '' }); setMatrix(Array.from({ length: schema!.time_steps }, () => Array(schema!.number_of_features).fill(''))) }}>New prediction</button></div></div></div></section>
      <section className="panel"><div className="panel-heading"><div><h3>Submitted clinical measurements</h3><p>Values in the order used by the GRU model.</p></div><div className="field"><label htmlFor="chart-measurement">Measurement</label><select id="chart-measurement" value={selectedMeasurement} onChange={event => setSelectedMeasurement(event.target.value)}>{definitions.map(field => <option key={field.name} value={field.name}>{field.label}</option>)}</select></div></div><div className="chart-box chart-tall"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData} margin={{ left: -17, right: 10, top: 10, bottom: 0 }}><CartesianGrid strokeDasharray="3 4" vertical={false} stroke="var(--line)" /><XAxis dataKey="step" tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 9, fill: 'var(--muted)' }} axisLine={false} tickLine={false} /><Tooltip /><Line dataKey="value" name={selectedField?.label} connectNulls={false} stroke="#247f74" strokeWidth={2.5} dot={{ r: 3, fill: '#247f74' }} activeDot={{ r: 5 }} /></LineChart></ResponsiveContainer></div><div className="grid two" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>{definitions.map(field => <div className="review-item" key={field.name}><span>{field.label} · {field.unit}</span><strong>{observations[observations.length - 1]?.[field.name as keyof (typeof observations)[number]] ?? '—'}</strong></div>)}</div><div className="callout" style={{ marginTop: 12 }}><Info size={15} /><span>Model contributions are not provided. The measured associations do not establish cause.</span></div></section></div>}
  </div>
}

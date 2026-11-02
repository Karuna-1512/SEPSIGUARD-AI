import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Download, FileUp, Info, RotateCcw, UploadCloud } from 'lucide-react'
import { api, formatDate } from '../api'
import type { Prediction, Schema } from '../types'
import { Empty, ErrorBox, Loading, RiskBadge } from '../components/UI'
import PredictionTable from '../components/PredictionTable'

type Validation = { success: boolean; valid: boolean; errors?: string[]; patient_count?: number; row_count?: number; missing_values?: number; preview: Record<string, unknown>[] }
type Results = { success: boolean; count: number; results: Prediction[] }

function downloadCsv(rows: Prediction[]) {
  const header = ['patient_id', 'prediction_probability', 'risk_category', 'prediction_timestamp', 'model_version']
  const escape = (value: unknown) => `"${String(value ?? '').replace(/"/g, '""')}"`
  const data = [header.join(','), ...rows.map(row => [row.patient_id, row.prediction_probability, row.risk_category, row.created_at, row.model_version].map(escape).join(','))].join('\r\n')
  const url = URL.createObjectURL(new Blob([data], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a'); a.href = url; a.download = 'sepsiguard-batch-results.csv'; a.click(); URL.revokeObjectURL(url)
}

export default function BatchPage() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [schema, setSchema] = useState<Schema | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [validation, setValidation] = useState<Validation | null>(null)
  const [results, setResults] = useState<Results | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)
  useEffect(() => { api<Schema>('/model/schema').then(setSchema).catch(e => setError(e instanceof Error ? e.message : 'Could not load schema.')) }, [])
  function choose(next?: File) { if (!next) return; setError(''); setValidation(null); setResults(null); if (!next.name.toLowerCase().endsWith('.csv')) { setFile(null); setError('Choose a file with the .csv extension.'); return } if (next.size > 10 * 1024 * 1024) { setFile(null); setError('CSV file must be smaller than 10 MB.'); return } setFile(next) }
  async function validate() {
    if (!file) return
    setBusy(true); setError('')
    try { const form = new FormData(); form.append('file', file); const value = await api<Validation>('/predict/batch/validate', { method: 'POST', body: form }); setValidation(value) }
    catch (e) { setError(e instanceof Error ? e.message : 'CSV validation failed.') } finally { setBusy(false) }
  }
  async function run() {
    if (!file) return
    setBusy(true); setError('')
    try { const form = new FormData(); form.append('file', file); const value = await api<Results>('/predict/batch', { method: 'POST', body: form }); setResults(value) }
    catch (e) { setError(e instanceof Error ? e.message : 'Batch predictions could not be completed.') } finally { setBusy(false) }
  }
  const stage = results ? 3 : validation ? 2 : file ? 1 : 0
  if (!schema && !error) return <Loading label="Loading CSV schema…" />
  return <div>
    <div className="page-intro"><div><h2>CSV batch prediction</h2><p>Validate one 12-step sequence per patient, inspect the preview, then save results to prediction history.</p></div></div>
    {error && <ErrorBox message={error} onRetry={file ? validate : undefined} />}
    <div className="batch-flow">{['Upload', 'Validate', 'Preview', 'Results'].map((x, i) => <span key={x} className={stage >= i ? 'active' : ''}>{String(i + 1).padStart(2, '0')} · {x}</span>)}</div>
    <section className="panel"><div className="panel-heading"><div><h3>Upload a clinical time-series CSV</h3><p>Long format: one row per time step, exactly 12 rows per patient.</p></div><span className="small-text">Max 10 MB</span></div>
      {!results && <div className={`upload-zone ${drag ? 'drag' : ''}`} onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); choose(e.dataTransfer.files[0]) }}>
        <input ref={inputRef} type="file" accept=".csv,text/csv" onChange={e => choose(e.target.files?.[0])} aria-label="Choose CSV file" />
        <span className="upload-icon"><UploadCloud size={21} /></span><b>{file ? file.name : 'Drop your CSV here'}</b><p>{file ? `${(file.size / 1024).toFixed(1)} KB · ready to validate` : 'or browse to select a .csv file'}</p><button type="button" className="button button-secondary button-small" onClick={() => inputRef.current?.click()}>{file ? 'Choose another file' : 'Browse files'} <FileUp size={14} /></button>
      </div>}
      {file && !results && <div className="step-actions"><span className="small-text">{validation?.valid ? `${validation.patient_count} patient sequences · ${validation.missing_values} missing cells` : 'No prediction runs until validation succeeds.'}</span><div style={{ display: 'flex', gap: 8 }}><button className="button button-secondary" disabled={busy} onClick={() => { setFile(null); setValidation(null) }}><RotateCcw size={14} /> Reset</button><button className="button button-primary" disabled={busy} onClick={validate}>{busy ? 'Validating…' : 'Validate CSV'} <CheckCircle2 size={14} /></button></div></div>}
      {validation && <div style={{ marginTop: 18 }}>{validation.valid ? <div className="callout"><CheckCircle2 size={16} /><span>CSV valid · {validation.patient_count} patients, {validation.row_count} time-step rows, {validation.missing_values} missing measurement cells.</span></div> : <div className="error-box" role="alert"><strong>CSV validation found issues</strong><span>{validation.errors?.map((issue, i) => <span key={i} style={{ display: 'block' }}>{issue}</span>)}</span></div>}</div>}
      {validation?.valid && !results && <div className="callout" style={{ marginTop: 12 }}><Info size={15} /><span>Preview is limited to the first 20 rows. Every required measurement must be numeric and within range before batch prediction runs.</span></div>}
      {validation?.valid && !results && <div className="table-wrap" style={{ marginTop: 13, maxHeight: 350 }}><table className="data-table"><thead><tr>{Object.keys(validation.preview[0] || {}).map(col => <th key={col}>{col}</th>)}</tr></thead><tbody>{validation.preview.map((row, i) => <tr key={i}>{Object.keys(validation.preview[0] || {}).map(col => <td key={col}>{row[col] === null ? <span className="missing-chip">Missing</span> : String(row[col] ?? '')}</td>)}</tr>)}</tbody></table></div>}
      {validation?.valid && !results && <div className="step-actions"><span className="small-text">Run saves each result in patient history.</span><button className="button button-primary" disabled={busy} onClick={run}>{busy ? 'Predicting…' : 'Run batch prediction'} <FileUp size={15} /></button></div>}
      {results && <div style={{ marginTop: 14 }}><div className="callout"><CheckCircle2 size={16} /><span>Saved {results.count} predictions to history at {formatDate(new Date().toISOString())}.</span></div><div className="step-actions"><button className="button button-primary" onClick={() => downloadCsv(results.results)}><Download size={15} /> Download results CSV</button><button className="button button-secondary" onClick={() => { setFile(null); setValidation(null); setResults(null) }}>Start another batch</button></div><div style={{ marginTop: 14 }}><PredictionTable items={results.results} /></div></div>}
    </section>
    <section className="panel" style={{ marginTop: 15 }}><div className="panel-heading"><div><h3>CSV format</h3><p>Headers must match the backend input schema exactly.</p></div></div><div className="callout"><Info size={15} /><span>Required columns: patient_id, time_step, {schema?.features.map(f => f.name).join(', ')}. Add sepsis_label at the end when the file includes known labels. Each patient requires integer time steps 1–{schema?.time_steps || 12} exactly once. All clinical input cells must be numeric and within the documented validation ranges.</span></div><a className="text-link" href="/data/sepsis_longitudinal_synthetic.csv" download style={{ marginTop: 10 }}>Download the synthetic longitudinal input CSV</a><p className="small-text" style={{ marginTop: 8 }}>This generated dataset and its labels are artificial and must not be used for clinical conclusions.</p></section>
  </div>
}

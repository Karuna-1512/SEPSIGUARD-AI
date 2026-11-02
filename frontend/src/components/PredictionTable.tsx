import { Eye } from 'lucide-react'
import { Link } from 'react-router-dom'
import { formatDate, formatPercent } from '../api'
import type { Prediction } from '../types'
import { Empty, RiskBadge } from './UI'

export default function PredictionTable({ items }: { items: Prediction[] }) {
  if (!items.length) return <Empty title="No prediction records yet">Run a single prediction or validate a CSV batch to start building history.</Empty>
  return <div className="table-wrap"><table className="data-table"><thead><tr><th>Patient</th><th>Risk</th><th>Probability</th><th>Input completeness</th><th>Model</th><th>Timestamp</th><th>Source</th><th /></tr></thead><tbody>{items.map(item => <tr key={item.id}>
    <td><Link className="patient-link" to={`/app/patients/${encodeURIComponent(item.patient_id)}`}>{item.patient_id}</Link>{item.synthetic_data && <small className="small-text"> · synthetic-trained</small>}</td>
    <td><RiskBadge category={item.risk_category} /></td><td><b>{formatPercent(item.prediction_probability)}</b></td><td>{item.input_completeness.toFixed(1)}%</td><td>{item.model_version}</td><td>{formatDate(item.created_at)}</td><td>{item.input_source}</td>
    <td><Link className="icon-button" aria-label={`View prediction ${item.id}`} title="View prediction" to={`/app/predictions/${item.id}`}><Eye size={15} /></Link></td>
  </tr>)}</tbody></table></div>
}

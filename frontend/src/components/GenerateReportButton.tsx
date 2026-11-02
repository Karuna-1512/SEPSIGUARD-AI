import { useState } from 'react'
import { Download } from 'lucide-react'
import { downloadPredictionReport } from '../api'

export function GenerateReportButton({ predictionId }: { predictionId: number }) {
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  async function generate() {
    setGenerating(true)
    setError('')
    try {
      await downloadPredictionReport(predictionId)
    } catch {
      setError('Unable to generate the report. Please try again.')
    } finally {
      setGenerating(false)
    }
  }

  return <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
    <button className="button button-primary" onClick={() => void generate()} disabled={generating}>
      <Download size={15} /> {generating ? 'Generating report...' : 'Generate PDF Report'}
    </button>
    {error && <span className="small-text" role="alert" style={{ color: 'var(--danger)' }}>{error}</span>}
  </div>
}

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockLogin = vi.hoisted(() => vi.fn(async (_email: string, _password: string) => undefined))
const mockApi = vi.hoisted(() => vi.fn())
const mockDownloadReport = vi.hoisted(() => vi.fn(async (_predictionId: number) => undefined))
vi.mock('../../frontend/src/auth', () => ({ useAuth: () => ({ user: null, loading: false, login: mockLogin, logout: vi.fn() }) }))
vi.mock('../../frontend/src/api', () => ({
  api: mockApi,
  downloadPredictionReport: mockDownloadReport,
  ApiError: class ApiError extends Error { status = 400 },
  formatDate: (value?: string) => value || '—',
  formatPercent: (value: number) => `${(value * 100).toFixed(1)}%`,
}))

import Landing from '../../frontend/src/pages/Landing'
import Dashboard from '../../frontend/src/pages/Dashboard'
import PredictionPage from '../../frontend/src/pages/PredictionPage'
import BatchPage from '../../frontend/src/pages/BatchPage'
import PredictionDetailPage from '../../frontend/src/pages/PredictionDetailPage'
import Sidebar from '../../frontend/src/components/Sidebar'

const fieldNames = ['heart_rate', 'respiratory_rate', 'temperature', 'systolic_bp', 'diastolic_bp', 'oxygen_saturation', 'wbc', 'lactate', 'creatinine', 'platelets', 'bilirubin', 'age']
const fields = fieldNames.map(name => ({ name, label: name.replaceAll('_', ' ').replace(/^\w/, value => value.toUpperCase()), unit: 'unit', description: name }))
const schema = { number_of_features: 12, time_steps: 12, features: fields, target: 'sepsis_label', schema_configured: true }
const observation = (time_step: number) => ({ time_step, heart_rate: 82, respiratory_rate: 17, temperature: 36.8, systolic_bp: 122, diastolic_bp: 77, oxygen_saturation: 97, wbc: 7.5, lactate: 1.1, creatinine: 0.9, platelets: 245, bilirubin: 0.7, age: 63 })
const prediction = {
  id: 7, patient_id: 'case-007', age: 63, prediction_probability: 0.68, risk_score: 68,
  prediction: 'Moderate risk of sepsis', risk_level: 'MODERATE', risk_category: 'MODERATE', model_version: 'gru-synthetic-test',
  created_at: '2026-10-03T10:00:00Z', input_source: 'manual', input_completeness: 100, missing_values: 0,
  synthetic_data: true, input_data: { age: 63, observations: [observation(1)] }, explanation: null,
}

function withRouter(node: ReactNode) { return render(<MemoryRouter>{node}</MemoryRouter>) }

describe('SepsiGuard interface', () => {
  beforeEach(() => {
    mockLogin.mockClear()
    mockDownloadReport.mockReset()
    mockDownloadReport.mockResolvedValue(undefined)
    mockApi.mockImplementation((path: string) => {
      if (path === '/model/schema') return Promise.resolve(schema)
      if (path === '/dashboard/summary') return Promise.resolve({ patients_analyzed: 1, high_risk: 0, moderate_risk: 1, low_risk: 0, predictions_today: 1, total_predictions: 1, recent_predictions: [prediction], high_risk_alerts: [] })
      if (path === '/dashboard/risk-distribution') return Promise.resolve({ items: [{ name: 'LOW', value: 0 }, { name: 'MODERATE', value: 1 }, { name: 'HIGH', value: 0 }] })
      if (path === '/dashboard/trends') return Promise.resolve({ items: [] })
      if (path === '/model/status') return Promise.resolve({ status: 'loaded_synthetic', model_name: 'SepsiGuard GRU', model_version: 'gru-synthetic-test', model_path: 'models/sepsis_gru.keras', number_of_features: 12, time_steps: 12, input_features: fieldNames, synthetic_data: true, message: 'Model trained on synthetic data; not clinically validated.' })
      if (path === '/predict/validate') return Promise.resolve({ valid: true, missing_values: 0, input_completeness: 100 })
      if (path === '/predict') return Promise.resolve({ prediction })
      if (path === '/predict/batch/validate') return Promise.resolve({ valid: true, patient_count: 1, row_count: 12, missing_values: 0, preview: [{ patient_id: 'case-007', time_step: 1, heart_rate: 82 }] })
      if (path === '/predict/batch') return Promise.resolve({ count: 1, results: [prediction] })
      if (path === '/predictions/7') return Promise.resolve(prediction)
      return Promise.resolve({})
    })
  })

  it('signs in with account credentials entered by the user', async () => {
    withRouter(<Landing />)
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'researcher@example.org' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'ExampleResearchPassword' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith('researcher@example.org', 'ExampleResearchPassword'))
  })

  it('renders dashboard cards from API data without an evaluation page link', async () => {
    withRouter(<Dashboard />)
    expect(await screen.findByText('Patients analyzed')).toBeInTheDocument()
    expect(screen.getByText('Recent predictions')).toBeInTheDocument()
    expect(screen.getByText(/synthetic data/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /model details/i })).not.toBeInTheDocument()
  })

  it('uses named clinical fields and blocks validation while required measurements are missing', async () => {
    withRouter(<PredictionPage />)
    fireEvent.change(await screen.findByLabelText(/Patient ID/), { target: { value: 'case-007' } })
    fireEvent.change(screen.getByLabelText(/Age/), { target: { value: '63' } })
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(await screen.findByLabelText('Heart rate, time step 1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    fireEvent.click(screen.getByRole('button', { name: 'Validate input' }))
    expect(await screen.findByText(/Enter heart rate for time step 1/i)).toBeInTheDocument()
    expect(mockApi).not.toHaveBeenCalledWith('/predict/validate', expect.anything())
  })

  it('validates and runs a selected CSV batch', async () => {
    withRouter(<BatchPage />)
    const file = new File(['patient_id,time_step,heart_rate'], 'batch.csv', { type: 'text/csv' })
    fireEvent.change(await screen.findByLabelText('Choose CSV file'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: /Validate CSV/ }))
    expect(await screen.findByText(/CSV valid/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Run batch prediction/ }))
    expect(await screen.findByText(/Saved 1 predictions/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Download results CSV/ })).toBeInTheDocument()
  })

  it('shows a saved record with a synthetic-training warning', async () => {
    render(<MemoryRouter initialEntries={['/app/predictions/7']}><Routes><Route path="/app/predictions/:predictionId" element={<PredictionDetailPage />} /></Routes></MemoryRouter>)
    expect(await screen.findByText('Prediction #7')).toBeInTheDocument()
    expect(screen.getByText(/trained using synthetic data/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Generate PDF Report/i })).toBeInTheDocument()
  })

  it('requests a server-generated PDF from a saved prediction', async () => {
    render(<MemoryRouter initialEntries={['/app/predictions/7']}><Routes><Route path="/app/predictions/:predictionId" element={<PredictionDetailPage />} /></Routes></MemoryRouter>)
    await screen.findByText('Prediction #7')
    fireEvent.click(screen.getByRole('button', { name: 'Generate PDF Report' }))
    await waitFor(() => expect(mockDownloadReport).toHaveBeenCalledWith(7))
  })

  it('keeps primary responsive navigation and omits model evaluation', () => {
    withRouter(<Sidebar />)
    const mobile = screen.getByRole('navigation', { name: 'Mobile navigation' })
    expect(mobile).toBeInTheDocument()
    expect(within(mobile).getByRole('link', { name: 'New prediction' })).toBeInTheDocument()
    expect(within(mobile).getByRole('link', { name: 'Prediction history' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Model performance/i })).not.toBeInTheDocument()
  })
})

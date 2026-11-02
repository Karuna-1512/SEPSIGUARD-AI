const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
let csrfToken = ''
export function setCsrfToken(value?: string | null) { csrfToken = value || '' }

export class ApiError extends Error {
  status: number
  details: unknown
  constructor(message: string, status: number, details?: unknown) { super(message); this.status = status; this.details = details }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const method = (init.method || 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && path !== '/auth/login' && csrfToken) headers.set('X-CSRF-Token', csrfToken)
  if (!(init.body instanceof FormData) && init.body !== undefined && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  let response: Response
  try {
    response = await fetch(`${API_BASE}/api${path}`, { ...init, headers, credentials: 'include' })
  } catch {
    throw new ApiError('Could not connect to the API. Check that the backend is running.', 0)
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data?.detail ?? data?.error?.message ?? data?.message ?? 'Request failed.'
    const message = typeof detail === 'string' ? detail : (detail?.message || detail?.issues?.join(' ') || detail?.errors?.join(' ') || 'Request could not be completed.')
    throw new ApiError(message, response.status, detail)
  }
  return data as T
}

export async function downloadPredictionReport(predictionId: number): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/api/predictions/${predictionId}/report`, { credentials: 'include' })
  } catch {
    throw new Error('Unable to generate the report. Please try again.')
  }
  if (!response.ok) throw new Error('Unable to generate the report. Please try again.')

  const disposition = response.headers.get('Content-Disposition') || ''
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || `SepsiGuard_Patient_${predictionId}_Report.pdf`
  const objectUrl = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

export const formatPercent = (n: number) => `${(n * 100).toFixed(1)}%`
export const formatDate = (value?: string | null) => value ? new Date(value).toLocaleString() : '—'

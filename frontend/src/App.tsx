import { Navigate, Route, Routes } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import type { ReactElement } from 'react'
import { useAuth } from './auth'
import AppShell from './components/AppShell'
import { Loading } from './components/UI'

const Landing = lazy(() => import('./pages/Landing'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const PredictionPage = lazy(() => import('./pages/PredictionPage'))
const BatchPage = lazy(() => import('./pages/BatchPage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const PatientsPage = lazy(() => import('./pages/PatientsPage'))
const PatientDetailPage = lazy(() => import('./pages/PatientDetailPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const AboutPage = lazy(() => import('./pages/AboutPage'))
const PredictionDetailPage = lazy(() => import('./pages/PredictionDetailPage'))
const RiskAnalysisPage = lazy(() => import('./pages/RiskAnalysisPage'))

function Protected({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading label="Connecting to SepsiGuard API…" />
  return user ? children : <Navigate to="/" replace />
}

export default function App() {
  return <Suspense fallback={<Loading label="Loading workspace…" />}><Routes>
    <Route path="/" element={<Landing />} />
    <Route path="/app" element={<Protected><AppShell /></Protected>}>
      <Route index element={<Dashboard />} />
      <Route path="risk" element={<RiskAnalysisPage />} />
      <Route path="predict" element={<PredictionPage />} />
      <Route path="batch" element={<BatchPage />} />
      <Route path="history" element={<HistoryPage />} />
      <Route path="predictions/:predictionId" element={<PredictionDetailPage />} />
      <Route path="patients" element={<PatientsPage />} />
      <Route path="patients/:patientId" element={<PatientDetailPage />} />
      <Route path="settings" element={<SettingsPage />} />
      <Route path="about" element={<AboutPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></Suspense>
}

import type { ReactNode } from 'react'
import { AlertTriangle, LoaderCircle } from 'lucide-react'

export function SafetyNotice() {
  return <aside className="safety-notice" role="note"><AlertTriangle size={17} aria-hidden="true" /><p>SepsiGuard AI is a research/decision-support tool and is not a substitute for professional medical judgment. Predictions should be reviewed by qualified healthcare professionals and must not be used alone for diagnosis or treatment.</p></aside>
}
export function Loading({ label = 'Loading…' }: { label?: string }) { return <div className="loading-state" role="status"><LoaderCircle className="spin" size={21} />{label}</div> }
export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) { return <div className="error-box" role="alert"><strong>Something needs attention</strong><span>{message}</span>{onRetry && <button className="button button-small button-quiet" onClick={onRetry}>Try again</button>}</div> }
export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) { return <div className="empty-state"><div className="empty-icon">∅</div><strong>{title}</strong>{children && <p>{children}</p>}{action}</div> }
export function RiskBadge({ category }: { category: string }) { return <span className={`risk-badge risk-${category.toLowerCase()}`}><i />{category}</span> }
export function MetricCard({ label, value, hint, icon, tone = '' }: { label: string; value: string | number; hint?: string; icon: ReactNode; tone?: string }) { return <article className={`metric-card ${tone}`}><div className="metric-top"><span>{label}</span><span className="metric-icon">{icon}</span></div><strong>{value}</strong>{hint && <small>{hint}</small>}</article> }

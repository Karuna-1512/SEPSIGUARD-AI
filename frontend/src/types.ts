export type User = { id: number; email: string; full_name: string; role: string }
export type ClinicalField = { name: string; label: string; unit: string; description?: string }
export type Schema = { number_of_features: 12; time_steps: 12; features: ClinicalField[]; target: 'sepsis_label'; schema_configured: boolean }
export type Observation = {
  time_step: number; heart_rate: number; respiratory_rate: number; temperature: number;
  systolic_bp: number; diastolic_bp: number; oxygen_saturation: number; wbc: number;
  lactate: number; creatinine: number; platelets: number; bilirubin: number; age?: number;
}
export type Prediction = {
  id: number; patient_id: string; age?: number | null; prediction_probability: number; risk_score: number;
  prediction: string; risk_level: 'LOW' | 'MODERATE' | 'HIGH'; risk_category: 'LOW' | 'MODERATE' | 'HIGH';
  model_version: string; created_at: string; input_source: string; input_completeness: number;
  missing_values: number; explanation?: Record<string, unknown> | null;
  synthetic_data?: boolean;
  input_data?: { observations?: Observation[]; age?: number; patient?: Patient };
  patient?: Patient; acknowledged?: boolean; disclaimer?: string;
}
export type Patient = { patient_id: string; age?: number | null; created_at?: string; updated_at?: string }
export type ModelStatus = {
  status: string; model_name: string; model_version: string; model_path: string;
  last_updated?: string | null; number_of_features: number; time_steps: number;
  input_features: string[]; synthetic_data: boolean; error?: string | null; message?: string | null;
}

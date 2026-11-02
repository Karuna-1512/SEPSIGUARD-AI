# API guide

Base API prefix: `/api`. The interactive FastAPI docs are served at `/docs`. Most routes require a signed-in account. Mutating authenticated requests must send the `X-CSRF-Token` returned by login.

## Input schema

The model consumes exactly 12 features, in this order: `heart_rate`, `respiratory_rate`, `temperature`, `systolic_bp`, `diastolic_bp`, `oxygen_saturation`, `wbc`, `lactate`, `creatinine`, `platelets`, `bilirubin`, `age`. Each sequence has at most 12 time steps. `patient_id` and `time_step` are metadata, and `sepsis_label` is the training target.

`GET /api/model/schema` returns the ordered names, units, and target. `GET /api/model/status` reports whether compatible model artifacts are installed, their version and feature dimensions, and whether they were trained using synthetic data. There is no evaluation-metrics API or model-evaluation screen.

## Single prediction

`POST /api/predict/validate` and `POST /api/predict` accept a patient identifier, age, and one or more ordered observations. Every observation requires the 11 time-varying measurements:

```json
{
  "patient_id": "research-001",
  "age": 63,
  "observations": [
    {
      "time_step": 1,
      "heart_rate": 82,
      "respiratory_rate": 17,
      "temperature": 36.8,
      "systolic_bp": 122,
      "diastolic_bp": 77,
      "oxygen_saturation": 97,
      "wbc": 7.5,
      "lactate": 1.1,
      "creatinine": 0.9,
      "platelets": 245,
      "bilirubin": 0.7
    }
  ]
}
```

Provide multiple observations in step order for longitudinal input. The API validates numeric bounds, finite values, and consecutive time-step numbering. If no compatible trained GRU and preprocessing artifacts are installed, prediction requests return a service-unavailable error rather than an estimated score. Prediction output carries a research-purpose disclaimer and does not provide a diagnosis or treatment recommendation.

## CSV batch

Upload a `.csv` in multipart field `file` to `/api/predict/batch/validate` to check the format, then to `/api/predict/batch` to request and store a prediction per patient. Training CSV headers must be exactly:

```text
patient_id,time_step,heart_rate,respiratory_rate,temperature,systolic_bp,diastolic_bp,oxygen_saturation,wbc,lactate,creatinine,platelets,bilirubin,age,sepsis_label
```

For batch inference only, the final `sepsis_label` column may be omitted. Every patient must have exactly one numeric row at each time step 1–12. If labels are present, they must be binary and consistent within each patient. Batch rows are checked against the same clinical measurement bounds as single-prediction inputs.

## Other endpoints

- `GET /api/health` checks API and database availability.
- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` manage authenticated sessions.
- `GET /api/patients` lists identifiers and ages; `GET /api/patients/{id}/history` returns saved prediction history.
- `GET /api/predictions` filters prediction records; `GET /api/predictions/{id}` returns one record with its saved observations.
- `GET /api/settings` returns research threshold values, model artifact status, and application status.

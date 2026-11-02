"""REST API for authentication, model information, patients and predictions."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.ml.csv_service import read_and_validate_csv, sequences_from_frame
from backend.ml.feature_schema import FEATURE_NAMES, NUM_FEATURES, TIME_STEPS, schema_document
from backend.ml.pdf_report import build_prediction_report, report_filename
from backend.ml.predictor import get_predictor
from backend.ml.preprocess import completeness, validate_sequence
from backend.models.entities import AuditLog, ClinicalRecord, ModelVersion, Patient, Prediction, SystemSetting, User
from backend.schemas.api import CreateUserBody, LoginBody, PasswordBody, PatientInfo, PredictBody, ThresholdBody
from backend.utils.audit import record_audit
from backend.utils.security import hash_password, make_session, read_csrf_token, read_session, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

DISCLAIMER = "This system is intended for educational and research purposes and is not a substitute for professional medical judgment."


def _user_view(user: User) -> dict:
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.session_cookie)
    user_id = read_session(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user


def _thresholds(db: Session) -> tuple[float, float]:
    rows = {row.key: row.value for row in db.scalars(select(SystemSetting).where(SystemSetting.key.in_(["low_threshold", "high_threshold"]))).all()}
    return float(rows.get("low_threshold", settings.low_threshold)), float(rows.get("high_threshold", settings.high_threshold))


def _patient_view(patient: Patient) -> dict:
    return {
        "patient_id": patient.id, "age": patient.age,
        "created_at": patient.created_at, "updated_at": patient.updated_at,
    }


def _prediction_view(p: Prediction, include_input: bool = False) -> dict:
    result = {
        "id": p.id, "patient_id": p.patient_id, "prediction_probability": p.prediction_probability,
        "risk_score": round(p.prediction_probability * 100, 1),
        "risk_level": p.risk_category,
        "prediction": f"{p.risk_category.title()} risk of sepsis",
        "risk_category": p.risk_category, "model_version": p.model_version, "created_at": p.created_at,
        "input_source": p.input_source, "input_completeness": p.input_completeness,
        "missing_values": p.missing_values, "explanation": p.explanation,
        "synthetic_data": bool((p.input_data or {}).get("synthetic_data", False)),
        "age": p.patient.age if p.patient else None,
    }
    if include_input:
        result["input_data"] = p.input_data
        result["patient"] = _patient_view(p.patient) if p.patient else {"patient_id": p.patient_id}
    return result


def _upsert_patient(db: Session, patient_id: str, info: PatientInfo | None) -> Patient:
    patient = db.get(Patient, patient_id)
    values = info.model_dump(exclude_unset=True) if info else {}
    if patient is None:
        patient = Patient(id=patient_id, **values)
        db.add(patient)
        db.flush()
    else:
        for key, value in values.items():
            setattr(patient, key, value)
    return patient


def _save_prediction(db: Session, request: PredictBody, user: User, source: str = "manual", commit: bool = True, observed_label: int | None = None) -> dict:
    patient = _upsert_patient(db, request.patient_id, request.patient_info())
    low, high = _thresholds(db)
    sequence_input = request.model_sequence()
    predictor = get_predictor()
    result = predictor.predict(sequence_input, low, high)
    series = result.pop("sequence")
    observations = [
        {"time_step": index, **dict(zip(FEATURE_NAMES, (float(value) for value in row)))}
        for index, row in enumerate(series, start=1)
    ]
    input_data = {"observations": observations, "age": request.age, "synthetic_data": predictor.synthetic_data}
    if observed_label in (0, 1):
        input_data["sepsis_label"] = int(observed_label)
    item = Prediction(
        patient_id=patient.id, prediction_probability=result["prediction_probability"],
        risk_category=result["risk_category"], model_version=result["model_version"],
        input_source=source, user_id=user.id, input_completeness=result["input_completeness"],
        missing_values=result["missing_values"],
        input_data=input_data,
        explanation=result["explanation"],
        simulated=False,
    )
    db.add(item)
    db.flush()
    db.add(ClinicalRecord(patient_id=patient.id, prediction_id=item.id, input_source=source, values={"observations": observations}))
    record_audit(db, "prediction.created", user.id, "prediction", str(item.id), {"source": source, "timesteps": len(observations)})
    if commit:
        db.commit()
    db.refresh(item)
    return _prediction_view(item, include_input=True) | {"disclaimer": DISCLAIMER}


@router.post("/auth/login")
def login(body: LoginBody, response: Response, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password was not recognized.")
    record_audit(db, "auth.login", user.id, "user", str(user.id), {"client": request.client.host if request.client else "unknown"})
    db.commit()
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        settings.session_cookie, make_session(user.id, csrf_token), max_age=settings.session_hours * 3600,
        httponly=True, secure=settings.environment == "production", samesite="none" if settings.environment == "production" else "lax", path="/",
    )
    return {"success": True, "user": _user_view(user), "csrf_token": csrf_token}


@router.post("/auth/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(settings.session_cookie)
    uid = read_session(token) if token else None
    if uid:
        record_audit(db, "auth.logout", uid, "user", str(uid))
        db.commit()
    response.delete_cookie(settings.session_cookie, path="/", httponly=True, samesite="none" if settings.environment == "production" else "lax", secure=settings.environment == "production")
    return {"success": True}


@router.get("/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    token = request.cookies.get(settings.session_cookie, "")
    return {"success": True, "user": _user_view(user), "csrf_token": read_csrf_token(token)}


@router.post("/auth/users")
def create_user(body: CreateUserBody, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    created = User(email=body.email, full_name=body.full_name.strip(), role=body.role, password_hash=hash_password(body.password))
    db.add(created)
    db.flush()
    record_audit(db, "auth.user_created", user.id, "user", str(created.id), {"role": created.role})
    db.commit()
    db.refresh(created)
    return {"success": True, "user": _user_view(created)}


@router.post("/auth/password")
def change_password(body: PasswordBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    record_audit(db, "auth.password_changed", user.id, "user", str(user.id))
    db.commit()
    return {"success": True}


@router.get("/model/schema")
def model_schema(user: User = Depends(current_user)):
    return schema_document(settings.schema_path)


@router.get("/model/status")
def model_status(db: Session = Depends(get_db), user: User = Depends(current_user)):
    predictor = get_predictor()
    state = predictor.status
    return {
        "status": state, "model_name": "SepsiGuard GRU", "model_version": predictor.version,
        "model_path": str(settings.model_path), "last_updated": datetime.fromtimestamp(settings.model_path.stat().st_mtime, timezone.utc).isoformat() if settings.model_path.exists() else None,
        "number_of_features": NUM_FEATURES, "time_steps": TIME_STEPS,
        "input_features": FEATURE_NAMES,
        "synthetic_data": predictor.synthetic_data,
        "error": predictor.load_error,
        "message": "This model was trained on synthetic data for software testing and is not clinically validated." if predictor.synthetic_data else ("Train and install the GRU model artifacts to enable predictions." if state != "loaded" else None),
    }


@router.post("/predict")
def predict(body: PredictBody, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        return {"success": True, "prediction": _save_prediction(db, body, user)}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/predict/validate")
def validate_prediction(body: PredictBody, user: User = Depends(current_user)):
    try:
        _values, missing = validate_sequence(body.model_sequence())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "valid": True, "patient_id": body.patient_id,
            "shape": [len(body.model_sequence()), NUM_FEATURES], "missing_values": missing,
            "input_completeness": completeness(missing)}


async def _csv_content(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a .csv file.")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"CSV must be smaller than {settings.max_upload_bytes // (1024 * 1024)} MB.")
    return content


async def _validated_upload(file: UploadFile):
    content = await _csv_content(file)
    schema_document(settings.schema_path)
    frame, errors = read_and_validate_csv(content)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "CSV validation failed.", "issues": errors})
    sequences = sequences_from_frame(frame)
    missing = int(frame[FEATURE_NAMES].isna().sum().sum())
    return frame, sequences, missing


@router.post("/predict/batch/validate")
async def validate_batch(file: UploadFile = File(...), user: User = Depends(current_user)):
    content = await _csv_content(file)
    schema_document(settings.schema_path)
    frame, errors = read_and_validate_csv(content)
    if errors:
        preview = frame.drop(columns=["sepsis_label"], errors="ignore").head(20)
        return {"success": False, "valid": False, "errors": errors, "preview": preview.astype(object).where(preview.notna(), None).to_dict(orient="records") if not frame.empty else []}
    return {
        "success": True, "valid": True, "patient_count": int(frame["patient_id"].nunique()),
        "row_count": len(frame), "missing_values": int(frame[FEATURE_NAMES].isna().sum().sum()),
        "preview": frame.drop(columns=["sepsis_label"], errors="ignore").head(20).astype(object).where(frame.drop(columns=["sepsis_label"], errors="ignore").head(20).notna(), None).to_dict(orient="records"),
    }


@router.post("/predict/batch")
async def predict_batch(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    _frame, sequences, _missing = await _validated_upload(file)
    saved = []
    try:
        for sample in sequences:
            body = PredictBody(patient_id=sample["patient_id"], age=sample["age"], observations=sample["observations"])
            saved.append(_save_prediction(db, body, user, source="csv", commit=False, observed_label=sample.get("sepsis_label")))
        db.commit()
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=503 if isinstance(exc, RuntimeError) else 422, detail=str(exc)) from exc
    return {"success": True, "count": len(saved), "results": saved, "input_features": FEATURE_NAMES, "disclaimer": DISCLAIMER}


@router.get("/predictions")
def list_predictions(
    risk_category: str | None = Query(default=None), q: str | None = Query(default=None, max_length=80),
    start_date: datetime | None = None, end_date: datetime | None = None,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    stmt = select(Prediction).join(Patient)
    if risk_category and risk_category.upper() in {"LOW", "MODERATE", "HIGH"}:
        stmt = stmt.where(Prediction.risk_category == risk_category.upper())
    if q:
        stmt = stmt.where(Patient.id.ilike(f"%{q.strip()}%"))
    if start_date:
        stmt = stmt.where(Prediction.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Prediction.created_at <= end_date)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Prediction.created_at.desc()).offset(offset).limit(limit)).all()
    return {"items": [_prediction_view(row) for row in rows], "total": total, "offset": offset, "limit": limit}


@router.get("/predictions/{prediction_id}")
def get_prediction(prediction_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Prediction, prediction_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prediction not found.")
    return _prediction_view(item, include_input=True) | {"disclaimer": DISCLAIMER}


@router.get("/predictions/{prediction_id}/report")
def download_prediction_report(prediction_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Prediction, prediction_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prediction not found.")

    input_data = item.input_data or {}
    observations = input_data.get("observations") or []
    if not observations:
        record = db.scalar(
            select(ClinicalRecord)
            .where(ClinicalRecord.prediction_id == item.id)
            .order_by(ClinicalRecord.created_at.desc(), ClinicalRecord.id.desc())
        )
        observations = (record.values or {}).get("observations", []) if record else []
    if not observations:
        raise HTTPException(status_code=409, detail="Complete clinical measurements are not stored for this prediction.")

    created_at = item.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    label = input_data.get("sepsis_label")
    observed_label = int(label) if label in (0, 1) else None
    low_threshold, high_threshold = _thresholds(db)
    try:
        pdf = build_prediction_report(
            patient_id=item.patient_id,
            age=item.patient.age if item.patient else input_data.get("age"),
            observations=observations,
            prediction_probability=item.prediction_probability,
            risk_category=item.risk_category,
            model_version=item.model_version,
            created_at=created_at,
            input_source=item.input_source,
            observed_label=observed_label,
            synthetic_data=bool(input_data.get("synthetic_data", False)),
            explanation=item.explanation,
            low_threshold=low_threshold,
            high_threshold=high_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("PDF report generation failed for prediction %s", prediction_id)
        raise HTTPException(status_code=500, detail="Unable to generate the report. Please try again.") from exc

    filename = report_filename(item.patient_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.post("/predictions/{prediction_id}/acknowledge")
def acknowledge(prediction_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(Prediction, prediction_id):
        raise HTTPException(status_code=404, detail="Prediction not found.")
    exists = db.scalar(select(AuditLog.id).where(AuditLog.action == "alert.acknowledge", AuditLog.resource_id == str(prediction_id), AuditLog.user_id == user.id))
    if not exists:
        record_audit(db, "alert.acknowledge", user.id, "prediction", str(prediction_id))
        db.commit()
    return {"success": True, "acknowledged": True}


@router.delete("/predictions/{prediction_id}")
def delete_prediction(prediction_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    item = db.get(Prediction, prediction_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prediction not found.")
    record_audit(db, "prediction.deleted", user.id, "prediction", str(item.id))
    db.execute(delete(ClinicalRecord).where(ClinicalRecord.prediction_id == item.id))
    db.delete(item)
    db.commit()
    return {"success": True}


@router.post("/patients")
def create_patient(body: PatientInfo, patient_id: str = Query(min_length=1, max_length=80), db: Session = Depends(get_db), user: User = Depends(current_user)):
    patient = db.get(Patient, patient_id)
    if patient:
        raise HTTPException(status_code=409, detail="A patient with this ID already exists.")
    patient = Patient(id=patient_id, **body.model_dump())
    db.add(patient)
    record_audit(db, "patient.created", user.id, "patient", patient_id)
    db.commit()
    db.refresh(patient)
    return _patient_view(patient)


@router.get("/patients")
def list_patients(q: str | None = None, offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Patient)
    if q:
        stmt = stmt.where(Patient.id.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Patient.updated_at.desc()).offset(offset).limit(limit)).all()
    return {"items": [_patient_view(p) for p in items], "total": total, "offset": offset, "limit": limit}


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return _patient_view(patient)


@router.get("/patients/{patient_id}/history")
def patient_history(patient_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    rows = db.scalars(select(Prediction).where(Prediction.patient_id == patient_id).order_by(Prediction.created_at.desc())).all()
    return {"patient": _patient_view(patient), "predictions": [_prediction_view(p, include_input=True) for p in rows]}


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = datetime.now(timezone.utc).date()
    counts = {cat: db.scalar(select(func.count()).select_from(Prediction).where(Prediction.risk_category == cat)) or 0 for cat in ["HIGH", "MODERATE", "LOW"]}
    total = sum(counts.values())
    analyzed = db.scalar(select(func.count(func.distinct(Prediction.patient_id)))) or 0
    today_count = db.scalar(select(func.count()).select_from(Prediction).where(func.date(Prediction.created_at) == today.isoformat())) or 0
    recent = db.scalars(select(Prediction).order_by(Prediction.created_at.desc()).limit(8)).all()
    acknowledged_ids = set(db.scalars(select(AuditLog.resource_id).where(AuditLog.action == "alert.acknowledge", AuditLog.user_id == user.id)).all())
    alerts = db.scalars(select(Prediction).where(Prediction.risk_category == "HIGH").order_by(Prediction.created_at.desc()).limit(8)).all()
    return {
        "patients_analyzed": analyzed, "high_risk": counts["HIGH"], "moderate_risk": counts["MODERATE"],
        "low_risk": counts["LOW"], "predictions_today": today_count, "total_predictions": total,
        "recent_predictions": [_prediction_view(p) for p in recent],
        "high_risk_alerts": [_prediction_view(p) | {"acknowledged": str(p.id) in acknowledged_ids} for p in alerts],
    }


@router.get("/dashboard/risk-distribution")
def risk_distribution(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.execute(select(Prediction.risk_category, func.count()).group_by(Prediction.risk_category)).all()
    counts = dict(rows)
    return {"items": [{"name": category, "value": int(counts.get(category, 0))} for category in ["LOW", "MODERATE", "HIGH"]]}


@router.get("/dashboard/trends")
def dashboard_trends(days: int = Query(default=14, ge=7, le=90), db: Session = Depends(get_db), user: User = Depends(current_user)):
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    rows = db.scalars(select(Prediction).where(Prediction.created_at >= since).order_by(Prediction.created_at)).all()
    by_day: dict[str, dict] = {}
    for offset in range(days):
        day = (since.date() + timedelta(days=offset)).isoformat()
        by_day[day] = {"date": day, "total": 0, "high": 0, "moderate": 0, "low": 0}
    for row in rows:
        key = row.created_at.date().isoformat()
        if key in by_day:
            by_day[key]["total"] += 1
            by_day[key][row.risk_category.lower()] += 1
    return {"items": list(by_day.values())}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    low, high = _thresholds(db)
    predictor = get_predictor()
    return {"prediction": {"low_threshold": low, "high_threshold": high, "missing_value_policy": "Every clinical measurement must be supplied as a finite numeric value."},
            "model": {"name": "SepsiGuard GRU", "version": predictor.version, "status": predictor.status, "path": str(settings.model_path), "number_of_features": NUM_FEATURES, "time_steps": TIME_STEPS},
            "system": {"database": "connected", "api": "online", "environment": settings.environment, "version": "1.0.0"}, "user": _user_view(user)}


@router.put("/settings/prediction")
def update_settings(body: ThresholdBody, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if body.low_threshold >= body.high_threshold:
        raise HTTPException(status_code=422, detail="Low threshold must be lower than high threshold.")
    for key, value in (("low_threshold", body.low_threshold), ("high_threshold", body.high_threshold)):
        setting = db.get(SystemSetting, key)
        if setting:
            setting.value = str(value)
        else:
            db.add(SystemSetting(key=key, value=str(value)))
    record_audit(db, "settings.thresholds_updated", user.id, "settings", "prediction", body.model_dump())
    db.commit()
    return {"success": True, "prediction": {"low_threshold": body.low_threshold, "high_threshold": body.high_threshold}}

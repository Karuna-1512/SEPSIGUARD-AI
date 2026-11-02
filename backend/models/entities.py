"""Database entities for users, patients, predictions, records and audit history."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), default="Research User")
    role: Mapped[str] = mapped_column(String(32), default="researcher")
    password_hash: Mapped[str] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    prediction_probability: Mapped[float] = mapped_column(Float)
    risk_category: Mapped[str] = mapped_column(String(16), index=True)
    model_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    input_source: Mapped[str] = mapped_column(String(32), default="manual")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    input_completeness: Mapped[float] = mapped_column(Float, default=0.0)
    missing_values: Mapped[int] = mapped_column(Integer, default=0)
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Legacy database compatibility: older SQLite databases require this column.
    # Current predictions are never simulator fallbacks; synthetic training is
    # tracked separately in input_data.synthetic_data.
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    patient: Mapped[Patient] = relationship(back_populates="predictions")


Index("ix_predictions_patient_created", Prediction.patient_id, Prediction.created_at)


class ClinicalRecord(Base):
    __tablename__ = "clinical_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    input_source: Mapped[str] = mapped_column(String(32), default="manual")
    values: Mapped[dict] = mapped_column(JSON, default=dict)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(32))
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), default="system")
    resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

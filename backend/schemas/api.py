"""Validated API request bodies for authentication and clinical measurements."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.ml.feature_schema import FEATURE_NAMES, TIME_STEPS


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class CreateUserBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(min_length=1, max_length=160)
    role: str = Field(pattern="^(administrator|doctor_clinician|researcher)$")
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Enter a valid email address.")
        return value


class PatientInfo(BaseModel):
    age: int = Field(ge=0, le=120)


class ClinicalObservation(BaseModel):
    time_step: int = Field(ge=1, le=TIME_STEPS)
    heart_rate: float = Field(ge=1, le=300, allow_inf_nan=False)
    respiratory_rate: float = Field(ge=1, le=100, allow_inf_nan=False)
    temperature: float = Field(ge=25, le=45, allow_inf_nan=False)
    systolic_bp: float = Field(ge=30, le=300, allow_inf_nan=False)
    diastolic_bp: float = Field(ge=10, le=200, allow_inf_nan=False)
    oxygen_saturation: float = Field(ge=0, le=100, allow_inf_nan=False)
    wbc: float = Field(ge=0, le=500, allow_inf_nan=False)
    lactate: float = Field(ge=0, le=50, allow_inf_nan=False)
    creatinine: float = Field(ge=0, le=100, allow_inf_nan=False)
    platelets: float = Field(ge=0, le=2000, allow_inf_nan=False)
    bilirubin: float = Field(ge=0, le=100, allow_inf_nan=False)

    def ordered_values(self, age: int) -> list[float]:
        values = self.model_dump(exclude={"time_step"})
        return [float(values[name]) for name in FEATURE_NAMES[:-1]] + [float(age)]


class PredictBody(BaseModel):
    patient_id: str = Field(min_length=1, max_length=80)
    age: int = Field(ge=0, le=120)
    observations: list[ClinicalObservation] | None = Field(default=None, min_length=1, max_length=TIME_STEPS)
    heart_rate: float | None = Field(default=None, ge=1, le=300, allow_inf_nan=False)
    respiratory_rate: float | None = Field(default=None, ge=1, le=100, allow_inf_nan=False)
    temperature: float | None = Field(default=None, ge=25, le=45, allow_inf_nan=False)
    systolic_bp: float | None = Field(default=None, ge=30, le=300, allow_inf_nan=False)
    diastolic_bp: float | None = Field(default=None, ge=10, le=200, allow_inf_nan=False)
    oxygen_saturation: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    wbc: float | None = Field(default=None, ge=0, le=500, allow_inf_nan=False)
    lactate: float | None = Field(default=None, ge=0, le=50, allow_inf_nan=False)
    creatinine: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    platelets: float | None = Field(default=None, ge=0, le=2000, allow_inf_nan=False)
    bilirubin: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

    @field_validator("patient_id")
    @classmethod
    def normalize_patient_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Patient ID must not be blank.")
        return value

    @model_validator(mode="after")
    def require_input_values(self):
        if self.observations:
            steps = [item.time_step for item in self.observations]
            if steps != list(range(1, len(steps) + 1)):
                raise ValueError("observations must be ordered and have consecutive time_step values starting at 1.")
        elif any(getattr(self, name) is None for name in FEATURE_NAMES[:-1]):
            raise ValueError("Provide all 12 clinical input fields, or provide ordered observations.")
        return self

    def model_sequence(self) -> list[list[float]]:
        if self.observations:
            return [observation.ordered_values(self.age) for observation in self.observations]
        return [[float(getattr(self, name)) for name in FEATURE_NAMES[:-1]] + [float(self.age)]]

    def patient_info(self) -> PatientInfo:
        return PatientInfo(age=self.age)


class ThresholdBody(BaseModel):
    low_threshold: float = Field(ge=0, le=1)
    high_threshold: float = Field(ge=0, le=1)


class PasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)

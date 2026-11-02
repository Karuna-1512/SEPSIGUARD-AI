"""Validation for the longitudinal clinical CSV schema."""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

from backend.ml.feature_schema import DATASET_COLUMNS, FEATURE_NAMES, TARGET_NAME, TIME_STEPS

VALUE_RANGES = {
    "heart_rate": (1, 300), "respiratory_rate": (1, 100), "temperature": (25, 45),
    "systolic_bp": (30, 300), "diastolic_bp": (10, 200), "oxygen_saturation": (0, 100),
    "wbc": (0, 500), "lactate": (0, 50), "creatinine": (0, 100),
    "platelets": (0, 2000), "bilirubin": (0, 100), "age": (0, 120),
}


def read_and_validate_csv(content: bytes, _feature_names: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    try:
        frame = pd.read_csv(io.BytesIO(content), dtype={"patient_id": "string"})
    except Exception as exc:
        return pd.DataFrame(), [f"Could not read CSV: {exc}"]
    if frame.empty:
        return frame, ["CSV contains no data rows."]

    actual = list(frame.columns)
    allowed = [DATASET_COLUMNS[:-1], DATASET_COLUMNS]
    if actual not in allowed:
        expected = ",".join(DATASET_COLUMNS)
        return frame, [f"CSV columns must match the clinical schema: {expected}"]

    frame = frame.copy()
    frame["patient_id"] = frame["patient_id"].astype("string").str.strip()
    errors: list[str] = []
    if frame["patient_id"].isna().any() or (frame["patient_id"].astype(str).str.len() == 0).any():
        errors.append("Every row must include a patient_id.")
    elif (frame["patient_id"].str.len() > 80).any():
        errors.append("patient_id values must be 80 characters or fewer.")

    steps = pd.to_numeric(frame["time_step"], errors="coerce")
    if steps.isna().any() or not np.equal(steps.fillna(-1), steps.fillna(-1).astype(int)).all():
        errors.append("time_step values must be integers from 1 through 12.")
    elif ((steps < 1) | (steps > TIME_STEPS)).any():
        errors.append("time_step values must be integers from 1 through 12.")
    frame["time_step"] = steps
    if frame.duplicated(["patient_id", "time_step"]).any():
        errors.append("Each patient_id/time_step pair must appear only once.")

    for name in FEATURE_NAMES:
        converted = pd.to_numeric(frame[name], errors="coerce")
        if converted.isna().any():
            errors.append(f"{name} is required and must be numeric for every row.")
        if np.isinf(converted.to_numpy(dtype=float, na_value=np.nan)).any():
            errors.append(f"{name} must contain finite numbers.")
        low, high = VALUE_RANGES[name]
        if ((converted < low) | (converted > high)).any():
            errors.append(f"{name} values must be between {low} and {high}.")
        frame[name] = converted

    if TARGET_NAME in frame:
        labels = pd.to_numeric(frame[TARGET_NAME], errors="coerce")
        if labels.isna().any() or not labels.isin([0, 1]).all():
            errors.append("sepsis_label, when present, must contain only 0 or 1.")
        frame[TARGET_NAME] = labels

    if not frame["age"].isna().any() and not np.equal(frame["age"], frame["age"].astype(int)).all():
        errors.append("age values must be whole years from 0 through 120.")

    if not errors:
        for patient_id, group in frame.groupby("patient_id", sort=False):
            actual_steps = sorted(group["time_step"].astype(int).tolist())
            if len(actual_steps) != TIME_STEPS or actual_steps != list(range(1, TIME_STEPS + 1)):
                errors.append(f"Patient {patient_id}: expected time_step 1 through {TIME_STEPS} exactly once.")
            if group["age"].nunique() != 1:
                errors.append(f"Patient {patient_id}: age must be consistent across the sequence.")
            if TARGET_NAME in frame and group[TARGET_NAME].nunique() != 1:
                errors.append(f"Patient {patient_id}: sepsis_label must remain consistent across the sequence.")
    return frame, errors


def sequences_from_frame(frame: pd.DataFrame, _feature_names: list[str] | None = None) -> list[dict]:
    result = []
    for patient_id, group in frame.groupby("patient_id", sort=False):
        group = group.sort_values("time_step")
        result.append({
            "patient_id": str(patient_id),
            "age": int(group["age"].iloc[0]),
            "observations": group[["time_step", *FEATURE_NAMES[:-1], "age"]].to_dict(orient="records"),
            "sepsis_label": int(group["sepsis_label"].iloc[0]) if "sepsis_label" in group.columns else None,
        })
    return result

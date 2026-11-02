"""The sole clinical input schema used by training, inference, and the API."""
from __future__ import annotations

import json
from pathlib import Path

TIME_STEPS = 12
FEATURE_NAMES = [
    "heart_rate",
    "respiratory_rate",
    "temperature",
    "systolic_bp",
    "diastolic_bp",
    "oxygen_saturation",
    "wbc",
    "lactate",
    "creatinine",
    "platelets",
    "bilirubin",
    "age",
]
NUM_FEATURES = len(FEATURE_NAMES)
TARGET_NAME = "sepsis_label"
DATASET_COLUMNS = ["patient_id", "time_step", *FEATURE_NAMES, TARGET_NAME]
FEATURE_METADATA = [
    {"name": "heart_rate", "label": "Heart Rate", "unit": "bpm", "description": "Heart rate"},
    {"name": "respiratory_rate", "label": "Respiratory Rate", "unit": "breaths/min", "description": "Respiratory rate"},
    {"name": "temperature", "label": "Temperature", "unit": "°C", "description": "Body temperature"},
    {"name": "systolic_bp", "label": "Systolic Blood Pressure", "unit": "mmHg", "description": "Systolic blood pressure"},
    {"name": "diastolic_bp", "label": "Diastolic Blood Pressure", "unit": "mmHg", "description": "Diastolic blood pressure"},
    {"name": "oxygen_saturation", "label": "Oxygen Saturation", "unit": "%", "description": "Oxygen saturation"},
    {"name": "wbc", "label": "WBC", "unit": "×10³/µL", "description": "White blood cell count"},
    {"name": "lactate", "label": "Lactate", "unit": "mmol/L", "description": "Lactate concentration"},
    {"name": "creatinine", "label": "Creatinine", "unit": "mg/dL", "description": "Creatinine concentration"},
    {"name": "platelets", "label": "Platelets", "unit": "×10³/µL", "description": "Platelet count"},
    {"name": "bilirubin", "label": "Bilirubin", "unit": "mg/dL", "description": "Bilirubin concentration"},
    {"name": "age", "label": "Age", "unit": "years", "description": "Patient age"},
]


def load_feature_definitions(path: str | Path | None = None) -> list[dict]:
    """Load model metadata and reject any schema that changes the trained order."""
    if path and Path(path).exists():
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        definitions = raw.get("features", []) if isinstance(raw, dict) else raw
        names = [item.get("name") if isinstance(item, dict) else item for item in definitions]
        if names != FEATURE_NAMES:
            raise ValueError("Feature schema must match the configured clinical input order exactly.")
        return [
            {**metadata, **(item if isinstance(item, dict) else {})}
            for metadata, item in zip(FEATURE_METADATA, definitions)
        ]
    return [dict(item) for item in FEATURE_METADATA]


def schema_document(path: str | Path | None = None) -> dict:
    return {
        "number_of_features": NUM_FEATURES,
        "time_steps": TIME_STEPS,
        "features": load_feature_definitions(path),
        "target": TARGET_NAME,
        "schema_configured": True,
    }

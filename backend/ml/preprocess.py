"""Numeric validation and sequence preprocessing helpers."""
from __future__ import annotations

import numpy as np

from backend.ml.feature_schema import FEATURE_NAMES, NUM_FEATURES, TIME_STEPS


def validate_sequence(values) -> tuple[np.ndarray, int]:
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= TIME_STEPS:
        raise ValueError(f"Provide between 1 and {TIME_STEPS} ordered time steps.")
    rows = []
    for step_index, row in enumerate(values, start=1):
        if not isinstance(row, (list, tuple)) or len(row) != NUM_FEATURES:
            raise ValueError(f"Time step {step_index} must contain these {NUM_FEATURES} measurements: {', '.join(FEATURE_NAMES)}.")
        clean_row = []
        for name, value in zip(FEATURE_NAMES, row):
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} is required and must be numeric.") from exc
            if not np.isfinite(number):
                raise ValueError(f"{name} must be a finite number.")
            clean_row.append(number)
        rows.append(clean_row)
    return np.asarray(rows, dtype=np.float32), 0


def completeness(missing: int) -> float:
    return 100.0 if missing == 0 else 0.0

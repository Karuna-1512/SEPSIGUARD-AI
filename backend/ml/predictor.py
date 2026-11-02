"""Load the trained clinical-schema GRU and matching preprocessing artifacts."""
from __future__ import annotations

import json
import logging
from functools import lru_cache

import numpy as np

from backend.config import settings
from backend.ml.feature_schema import FEATURE_NAMES, NUM_FEATURES, TARGET_NAME, TIME_STEPS, load_feature_definitions
from backend.ml.preprocess import completeness, validate_sequence

logger = logging.getLogger(__name__)


class Predictor:
    def __init__(self):
        self.model = None
        self.preprocessor = None
        self.load_error = None
        self.synthetic_data = False
        self._load()

    def _load(self):
        if not settings.model_path.exists():
            self.load_error = "Trained GRU model artifact is missing."
            return
        if not settings.scaler_path.exists():
            self.load_error = "The matching preprocessing artifact is missing."
            return
        if not settings.schema_path.exists():
            self.load_error = "The matching clinical feature schema is missing."
            return
        if not settings.metrics_path.exists():
            self.load_error = "The model training metadata is missing."
            return
        try:
            import joblib
            import tensorflow as tf
            definitions = load_feature_definitions(settings.schema_path)
            if [item["name"] for item in definitions] != FEATURE_NAMES:
                raise ValueError("Model schema does not match the configured clinical feature order.")
            self.model = tf.keras.models.load_model(settings.model_path)
            self.preprocessor = joblib.load(settings.scaler_path)
            if getattr(self.preprocessor, "n_features_in_", NUM_FEATURES) != NUM_FEATURES:
                raise ValueError(f"Preprocessor must accept exactly {NUM_FEATURES} ordered clinical values.")
            input_shape = getattr(self.model, "input_shape", None)
            if input_shape is not None and input_shape[-1] != NUM_FEATURES:
                raise ValueError(f"GRU model must accept {NUM_FEATURES} clinical features per time step.")
            metadata = json.loads(settings.metrics_path.read_text(encoding="utf-8"))
            if metadata.get("input_features") != FEATURE_NAMES or metadata.get("target") != TARGET_NAME:
                raise ValueError("Model metadata does not match the clinical feature schema.")
            self.synthetic_data = bool(metadata.get("synthetic_data", False))
            logger.info("Loaded clinical-schema GRU model from %s", settings.model_path)
        except Exception as exc:
            self.load_error = str(exc)
            self.model = None
            self.preprocessor = None
            logger.exception("Unable to load configured GRU model")

    @property
    def status(self) -> str:
        if self.model is not None and self.preprocessor is not None:
            return "loaded_synthetic" if self.synthetic_data else "loaded"
        if self.load_error:
            return "training_required" if "missing" in self.load_error.lower() else "error"
        return "training_required"

    @property
    def version(self) -> str:
        if self.model is not None and settings.metrics_path.exists():
            try:
                metadata = json.loads(settings.metrics_path.read_text(encoding="utf-8"))
                return str(metadata.get("model_version", "trained-model"))
            except (OSError, json.JSONDecodeError):
                pass
        return "not-trained"

    def predict(self, values, low_threshold: float, high_threshold: float) -> dict:
        if self.model is None or self.preprocessor is None:
            raise RuntimeError(self.load_error or "A trained GRU model is required before predictions can be generated.")
        sequence, missing = validate_sequence(values)
        processed = self.preprocessor.transform(sequence)
        model_input = np.asarray(processed, dtype=np.float32)[None, :, :]
        probability = float(np.asarray(self.model.predict(model_input, verbose=0)).reshape(-1)[0])
        if not np.isfinite(probability):
            raise RuntimeError("The model returned a non-finite prediction.")
        probability = min(max(probability, 0.0), 1.0)
        category = "LOW" if probability < low_threshold else ("MODERATE" if probability < high_threshold else "HIGH")
        return {
            "prediction_probability": probability,
            "risk_score": round(probability * 100, 1),
            "risk_category": category,
            "prediction": f"{category.title()} risk of sepsis",
            "model_version": self.version,
            "missing_values": missing,
            "input_completeness": completeness(missing),
            "explanation": None,
            "sequence": sequence.tolist(),
        }


@lru_cache(maxsize=1)
def get_predictor() -> Predictor:
    return Predictor()

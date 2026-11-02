"""Train and evaluate a patient-grouped GRU with the configured clinical schema."""
from __future__ import annotations

import argparse
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix, f1_score,
                             precision_recall_curve, precision_score, recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from backend.config import PROJECT_ROOT
from backend.ml.csv_service import VALUE_RANGES
from backend.ml.feature_schema import DATASET_COLUMNS, FEATURE_NAMES, NUM_FEATURES, TARGET_NAME, TIME_STEPS, load_feature_definitions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sepsiguard.train")


def _split_indices(groups: np.ndarray, test_size: float, seed: int):
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    train, test = next(splitter.split(np.zeros(len(groups)), groups=groups))
    return train, test


def load_sequences(csv_path: Path):
    frame = pd.read_csv(csv_path, dtype={"patient_id": "string"})
    if list(frame.columns) != DATASET_COLUMNS:
        raise ValueError("Training columns must exactly match the configured clinical dataset schema and order.")
    missing = set(["patient_id", "time_step", TARGET_NAME, *FEATURE_NAMES]) - set(frame.columns)
    if missing:
        raise ValueError("Training data is missing columns: " + ", ".join(sorted(missing)))
    frame = frame[["patient_id", "time_step", *FEATURE_NAMES, TARGET_NAME]].copy()
    frame["patient_id"] = frame["patient_id"].astype("string").str.strip()
    if frame["patient_id"].isna().any() or (frame["patient_id"] == "").any():
        raise ValueError("Training rows must have a non-empty patient_id.")
    frame["time_step"] = pd.to_numeric(frame["time_step"], errors="coerce")
    frame[TARGET_NAME] = pd.to_numeric(frame[TARGET_NAME], errors="coerce")
    for name in FEATURE_NAMES:
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
        low, high = VALUE_RANGES[name]
        if frame[name].isna().any() or ((frame[name] < low) | (frame[name] > high)).any():
            raise ValueError(f"{name} must contain finite numeric values between {low} and {high}.")
    numeric = frame[["time_step", *FEATURE_NAMES, TARGET_NAME]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("Training data must contain finite numeric measurements, time_step values, and labels.")
    if not frame[TARGET_NAME].isin([0, 1]).all():
        raise ValueError("sepsis_label must contain only binary values 0 or 1.")
    if not np.equal(frame["age"], frame["age"].astype(int)).all():
        raise ValueError("age values must be whole years from 0 through 120.")
    if not np.equal(frame["time_step"], frame["time_step"].astype(int)).all():
        raise ValueError("time_step values must be integers.")

    samples, labels, groups = [], [], []
    for patient_id, group in frame.groupby("patient_id", sort=False):
        group = group.sort_values("time_step")
        if len(group) != TIME_STEPS or group["time_step"].astype(int).tolist() != list(range(1, TIME_STEPS + 1)):
            raise ValueError(f"Patient {patient_id} must have exactly time_step 1 through {TIME_STEPS}.")
        if group["age"].nunique() != 1:
            raise ValueError(f"Patient {patient_id} must have one consistent age across the sequence.")
        unique_labels = group[TARGET_NAME].unique()
        if len(unique_labels) != 1:
            raise ValueError(f"Patient {patient_id} must have one consistent {TARGET_NAME}.")
        samples.append(group[FEATURE_NAMES].to_numpy(dtype=np.float32))
        labels.append(int(unique_labels[0]))
        groups.append(str(patient_id))
    if len(samples) < 10:
        raise ValueError("At least 10 patient sequences are required for grouped train/validation/test splits.")
    return np.asarray(samples, dtype=np.float32), np.asarray(labels, dtype=np.int32), np.asarray(groups)


def train(args):
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError("TensorFlow is required for training. Install requirements-ml.txt in the project environment.") from exc
    random.seed(args.seed)
    np.random.seed(args.seed)
    tf.keras.utils.set_random_seed(args.seed)
    load_feature_definitions(args.schema)
    X, y, groups = load_sequences(args.data)
    train_val, test = _split_indices(groups, args.test_size, args.seed)
    train_rel, validation_rel = _split_indices(groups[train_val], args.validation_size, args.seed + 1)
    train_idx, validation_idx = train_val[train_rel], train_val[validation_rel]
    if len(np.unique(y[train_idx])) < 2:
        raise ValueError("Training split must contain both label classes; use a larger or better-balanced dataset.")

    # Fit preprocessing on time points from training patients only.
    preprocessor = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scaler", StandardScaler()),
    ])
    X_train_rows = X[train_idx].reshape(-1, NUM_FEATURES)
    preprocessor.fit(X_train_rows)
    X_train = preprocessor.transform(X_train_rows).reshape(-1, TIME_STEPS, NUM_FEATURES).astype(np.float32)
    X_validation = preprocessor.transform(X[validation_idx].reshape(-1, NUM_FEATURES)).reshape(-1, TIME_STEPS, NUM_FEATURES).astype(np.float32)
    X_test = preprocessor.transform(X[test].reshape(-1, NUM_FEATURES)).reshape(-1, TIME_STEPS, NUM_FEATURES).astype(np.float32)

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(None, NUM_FEATURES)),
        tf.keras.layers.GRU(args.units, return_sequences=True),
        tf.keras.layers.Dropout(args.dropout),
        tf.keras.layers.GRU(max(args.units // 2, 8)),
        tf.keras.layers.Dropout(args.dropout),
        tf.keras.layers.Dense(args.dense_units, activation="relu"),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ], name="sepsiguard_gru")
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=args.learning_rate), loss="binary_crossentropy", metrics=["accuracy"])
    callbacks = [tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=args.patience, restore_best_weights=True)]
    history = model.fit(X_train, y[train_idx], validation_data=(X_validation, y[validation_idx]),
                        epochs=args.epochs, batch_size=args.batch_size, callbacks=callbacks, verbose=2)
    probabilities = model.predict(X_test, verbose=0).reshape(-1)
    predicted = (probabilities >= 0.5).astype(int)
    can_auc = len(np.unique(y[test])) == 2
    fpr, tpr = roc_curve(y[test], probabilities)[:2] if can_auc else ([], [])
    precision_curve, recall_curve = precision_recall_curve(y[test], probabilities)[:2] if can_auc else ([], [])

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save(output_dir / "sepsis_gru.keras")
    joblib.dump(preprocessor, output_dir / "scaler.pkl")
    schema = {
        "number_of_features": NUM_FEATURES,
        "time_steps": TIME_STEPS,
        "features": load_feature_definitions(),
        "target": TARGET_NAME,
        "dataset_columns": ["patient_id", "time_step", *FEATURE_NAMES, TARGET_NAME],
    }
    (output_dir / "feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    metrics = {
        "model_version": "gru-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.data),
        "synthetic_data": bool(args.synthetic_data),
        "dataset_disclaimer": "This model was trained on artificial synthetic records for software pipeline testing only. It is not clinically validated and must not be used for diagnosis or treatment.",
        "input_features": FEATURE_NAMES,
        "target": TARGET_NAME,
        "sequence_timesteps": TIME_STEPS,
        "split": {"patient_level": True, "train_patients": len(train_idx), "validation_patients": len(validation_idx), "test_patients": len(test)},
        "configuration": {"seed": args.seed, "units": args.units, "dense_units": args.dense_units, "dropout": args.dropout,
                          "learning_rate": args.learning_rate, "batch_size": args.batch_size, "epochs_requested": args.epochs,
                          "epochs_completed": len(history.history.get("loss", []))},
        "metrics": {"accuracy": float(accuracy_score(y[test], predicted)),
                    "precision": float(precision_score(y[test], predicted, zero_division=0)),
                    "recall": float(recall_score(y[test], predicted, zero_division=0)),
                    "f1": float(f1_score(y[test], predicted, zero_division=0)),
                    "roc_auc": float(roc_auc_score(y[test], probabilities)) if can_auc else None,
                    "average_precision": float(average_precision_score(y[test], probabilities)) if can_auc else None},
        "confusion_matrix": confusion_matrix(y[test], predicted, labels=[0, 1]).tolist(),
        "roc_curve": {"fpr": np.asarray(fpr).tolist(), "tpr": np.asarray(tpr).tolist()},
        "precision_recall_curve": {"precision": np.asarray(precision_curve).tolist(), "recall": np.asarray(recall_curve).tolist()},
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    logger.info("Training completed. The metrics are specific to the supplied data and do not establish clinical validity.")
    return metrics


def parse_args():
    parser = argparse.ArgumentParser(description="Train a patient-grouped GRU using the SepsiGuard clinical schema.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "sepsis_longitudinal_synthetic.csv")
    parser.add_argument("--schema", type=Path, default=PROJECT_ROOT / "models" / "feature_schema.json")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "models")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--validation-size", type=float, default=0.2)
    parser.add_argument("--units", type=int, default=64)
    parser.add_argument("--dense-units", type=int, default=32)
    parser.add_argument("--dropout", type=float, default=0.25)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--synthetic-data", action="store_true", help="Record that the training data is synthetic and is not clinically valid")
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())

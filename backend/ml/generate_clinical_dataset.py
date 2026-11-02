"""Create a clearly synthetic longitudinal dataset in the SepsiGuard column order."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from backend.ml.feature_schema import DATASET_COLUMNS, TIME_STEPS


def generate_dataset(output: Path, patients: int = 160, seed: int = 17) -> Path:
    if patients < 20:
        raise ValueError("Generate at least 20 patient sequences for a useful grouped training example.")
    rng = np.random.default_rng(seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        for patient_index in range(1, patients + 1):
            patient_id = f"SYN-{patient_index:04d}"
            age = int(rng.integers(18, 91))
            latent_pattern = float(rng.normal(0, 1))
            label = int(latent_pattern > 0.05)
            for time_step in range(1, TIME_STEPS + 1):
                progression = (time_step - 1) / (TIME_STEPS - 1)
                severity = latent_pattern + progression * (0.25 if label else -0.05)
                jitter = lambda scale: float(rng.normal(0, scale))
                row = {
                    "patient_id": patient_id,
                    "time_step": time_step,
                    "heart_rate": round(float(np.clip(82 + severity * 14 + jitter(5), 48, 160)), 2),
                    "respiratory_rate": round(float(np.clip(17 + severity * 3.2 + jitter(1.5), 8, 38)), 2),
                    "temperature": round(float(np.clip(36.8 + severity * 0.55 + jitter(0.2), 35.5, 40.5)), 2),
                    "systolic_bp": round(float(np.clip(122 - severity * 13 + jitter(7), 75, 190)), 2),
                    "diastolic_bp": round(float(np.clip(77 - severity * 8 + jitter(5), 40, 115)), 2),
                    "oxygen_saturation": round(float(np.clip(97 - severity * 2.4 + jitter(1.2), 82, 100)), 2),
                    "wbc": round(float(np.clip(7.5 + severity * 3.3 + jitter(1.5), 1, 30)), 2),
                    "lactate": round(float(np.clip(1.1 + severity * 0.85 + jitter(0.35), 0.3, 8)), 2),
                    "creatinine": round(float(np.clip(0.9 + severity * 0.35 + jitter(0.2), 0.2, 4)), 2),
                    "platelets": round(float(np.clip(245 - severity * 38 + jitter(22), 50, 500)), 2),
                    "bilirubin": round(float(np.clip(0.7 + severity * 0.32 + jitter(0.2), 0.1, 5)), 2),
                    "age": age,
                    "sepsis_label": label,
                }
                writer.writerow(row)
    return output


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic longitudinal rows for software pipeline testing; not clinical data.")
    parser.add_argument("--output", type=Path, default=Path("data/sepsis_longitudinal_synthetic.csv"))
    parser.add_argument("--patients", type=int, default=160)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    path = generate_dataset(args.output, patients=args.patients, seed=args.seed)
    print(f"Generated {path} with {args.patients} synthetic patient sequences and {TIME_STEPS} time steps each.")
    print("The labels and measurements are artificial and do not support clinical conclusions.")


if __name__ == "__main__":
    main()

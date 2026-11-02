# GRU model artifacts

The training command writes a compatible artifact set into this directory:

- `sepsis_gru.keras` — TensorFlow/Keras GRU model
- `scaler.pkl` — training-fitted imputer and standard scaler
- `feature_schema.json` — exact 12-feature order and target name
- `metrics.json` — training configuration, patient-level splits, and test-set software metrics

All four files must come from the same training run. The API requires model, preprocessor, schema, and training metadata to load together and refuses to generate predictions when a required artifact is missing or incompatible.

See the root README for the training command. The included data file is synthetic; any output and metrics from artifacts trained on it are only software pipeline checks and have no clinical meaning.

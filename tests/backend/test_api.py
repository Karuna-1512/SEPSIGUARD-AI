import csv
import io
from pathlib import Path

import numpy as np


FEATURES = [
    "heart_rate", "respiratory_rate", "temperature", "systolic_bp", "diastolic_bp",
    "oxygen_saturation", "wbc", "lactate", "creatinine", "platelets", "bilirubin", "age",
]


def sign_in(client):
    response = client.post("/api/auth/login", json={"email": "test@sepsiguard.local", "password": "TestOnly!LongPassword"})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def observation(step):
    return {
        "time_step": step, "heart_rate": 82, "respiratory_rate": 17, "temperature": 36.8,
        "systolic_bp": 122, "diastolic_bp": 77, "oxygen_saturation": 97, "wbc": 7.5,
        "lactate": 1.1, "creatinine": 0.9, "platelets": 245, "bilirubin": 0.7,
    }


def csv_bytes(with_all_columns=True):
    headers = ["patient_id", "time_step", *FEATURES]
    if with_all_columns:
        headers.append("sepsis_label")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    values = [82, 17, 36.8, 122, 77, 97, 7.5, 1.1, 0.9, 245, 0.7, 63]
    for step in range(1, 13):
        row = ["case-03", step, *values]
        if with_all_columns:
            row.append(1)
        writer.writerow(row)
    return output.getvalue().encode()


def test_health_checks_api_and_database(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_authentication_and_session(client):
    token = sign_in(client)
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "administrator"
    assert me.json()["csrf_token"] == token
    client.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    assert client.get("/api/auth/me").status_code == 401


def test_patient_create_and_database_listing(client):
    token = sign_in(client)
    created = client.post("/api/patients?patient_id=case-01", json={"age": 47}, headers={"X-CSRF-Token": token})
    assert created.status_code == 200
    assert created.json()["patient_id"] == "case-01"
    listing = client.get("/api/patients")
    assert listing.json()["total"] == 1


def test_clinical_schema_names_and_order(client):
    sign_in(client)
    response = client.get("/api/model/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["number_of_features"] == 12
    assert body["time_steps"] == 12
    assert [field["name"] for field in body["features"]] == FEATURES
    assert body["target"] == "sepsis_label"


def test_prediction_input_validation_requires_named_clinical_values(client):
    token = sign_in(client)
    payload = {"patient_id": "case-02", "age": 63, "observations": [observation(step) for step in range(1, 13)]}
    valid = client.post("/api/predict/validate", json=payload, headers={"X-CSRF-Token": token})
    assert valid.status_code == 200
    assert valid.json()["shape"] == [12, 12]
    assert valid.json()["missing_values"] == 0
    assert valid.json()["input_completeness"] == 100.0

    payload["observations"][4]["time_step"] = 3
    invalid = client.post("/api/predict/validate", json=payload, headers={"X-CSRF-Token": token})
    assert invalid.status_code == 422


def test_csv_validation_checks_exact_schema_and_12_rows(client):
    token = sign_in(client)
    valid = client.post("/api/predict/batch/validate", files={"file": ("valid.csv", csv_bytes(), "text/csv")}, headers={"X-CSRF-Token": token})
    assert valid.status_code == 200
    assert valid.json()["valid"] is True
    assert valid.json()["patient_count"] == 1
    assert valid.json()["row_count"] == 12

    content = io.StringIO()
    writer = csv.writer(content)
    writer.writerow(["patient_id", "time_step", *FEATURES[:-1]])
    writer.writerow(["case-04", 1, *([1] * 11)])
    invalid = client.post("/api/predict/batch/validate", files={"file": ("invalid.csv", content.getvalue().encode(), "text/csv")}, headers={"X-CSRF-Token": token})
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False
    assert "columns must match" in invalid.json()["errors"][0]


def test_model_status_reports_artifact_readiness_without_evaluation_values(client):
    sign_in(client)
    status = client.get("/api/model/status").json()
    assert status["status"] in {"training_required", "loaded", "loaded_synthetic", "error"}
    assert status["input_features"] == FEATURES
    assert status["number_of_features"] == 12


def test_model_loader_does_not_accept_missing_preprocessor(client, monkeypatch):
    from backend.config import settings
    from backend.ml.predictor import Predictor

    model = Path(__file__)
    monkeypatch.setattr(settings, "model_path", model)
    missing = Path(__file__).parent / "absent-test-artifact.pkl"
    monkeypatch.setattr(settings, "scaler_path", missing)
    monkeypatch.setattr(settings, "schema_path", missing)
    monkeypatch.setattr(settings, "metrics_path", missing)
    predictor = Predictor()
    assert predictor.status == "training_required"
    assert "preprocessing artifact is missing" in predictor.load_error


def test_prediction_persistence_uses_the_model_and_named_sequence(client, monkeypatch):
    import backend.routes.api as api_module

    class TestPredictor:
        synthetic_data = True

        @property
        def version(self):
            return "test-gru"

        def predict(self, values, _low, _high):
            return {
                "prediction_probability": 0.68, "risk_score": 68.0, "risk_category": "MODERATE",
                "prediction": "Moderate risk of sepsis", "model_version": self.version,
                "missing_values": 0, "input_completeness": 100.0, "explanation": None,
                "sequence": np.asarray(values, dtype=np.float32),
            }

    monkeypatch.setattr(api_module, "get_predictor", lambda: TestPredictor())
    token = sign_in(client)
    body = {"patient_id": "case-04", "age": 55, "observations": [observation(step) for step in range(1, 13)]}
    response = client.post("/api/predict", json=body, headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    item = response.json()["prediction"]
    assert item["synthetic_data"] is True
    assert item["risk_score"] == 68.0
    assert item["input_data"]["observations"][0]["heart_rate"] == 82
    assert len(item["input_data"]["observations"]) == 12
    assert client.get("/api/predictions").json()["total"] == 1
    assert client.get(f"/api/predictions/{item['id']}").json()["patient"]["patient_id"] == "case-04"
    report = client.get(f"/api/predictions/{item['id']}/report")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("application/pdf")
    assert report.headers["content-disposition"] == 'attachment; filename="SepsiGuard_Patient_case-04_Report.pdf"'
    assert report.content.startswith(b"%PDF-")


def test_batch_prediction_preserves_observed_label_and_generates_report(client, monkeypatch):
    import backend.routes.api as api_module

    class TestPredictor:
        synthetic_data = True

        @property
        def version(self):
            return "test-gru"

        def predict(self, values, _low, _high):
            return {
                "prediction_probability": 0.68, "risk_score": 68.0, "risk_category": "MODERATE",
                "prediction": "Moderate risk of sepsis", "model_version": self.version,
                "missing_values": 0, "input_completeness": 100.0, "explanation": None,
                "sequence": np.asarray(values, dtype=np.float32),
            }

    monkeypatch.setattr(api_module, "get_predictor", lambda: TestPredictor())
    token = sign_in(client)
    response = client.post(
        "/api/predict/batch",
        files={"file": ("synthetic.csv", csv_bytes(), "text/csv")},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    prediction = response.json()["results"][0]
    assert prediction["input_data"]["sepsis_label"] == 1
    assert len(prediction["input_data"]["observations"]) == 12
    report = client.get(f"/api/predictions/{prediction['id']}/report")
    assert report.status_code == 200
    assert report.content.startswith(b"%PDF-")

import os

os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-deployment"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "test@sepsiguard.local"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "TestOnly!LongPassword"
os.environ["BOOTSTRAP_ADMIN_NAME"] = "Test Administrator"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as main_module
from backend.database import Base, get_db


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(main_module, "SessionLocal", testing_session)

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_db
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def sign_in(client):
    response = client.post("/api/auth/login", json={"email": "test@sepsiguard.local", "password": "TestOnly!LongPassword"})
    assert response.status_code == 200
    return response.json()["csrf_token"]

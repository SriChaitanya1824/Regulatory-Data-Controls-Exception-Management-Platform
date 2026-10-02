import os

os.environ["DATABASE_URL"]="sqlite:///./test_governance.db"
import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(scope="session",autouse=True)
def database():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    from app.seed import seed
    with SessionLocal() as db: seed(db)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture()
def client(): return TestClient(app)

@pytest.fixture()
def auth(client):
    def login(email="analyst@example.com",password="Governance2026!"):
        r=client.post("/api/auth/login",json={"username":email,"password":password});assert r.status_code==200
        return {"Authorization":f"Bearer {r.json()['access_token']}"}
    return login

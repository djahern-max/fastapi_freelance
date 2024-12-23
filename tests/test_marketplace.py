import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, Base
from app.oauth2 import create_access_token
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import stripe
import os

# Test database setup
SQLALCHEMY_DATABASE_URL = (
    "postgresql://postgres:Guitar0123!@localhost:5432/fastapi_test"
)
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_create_product(test_db, client):
    # Test product creation
    headers = {"Authorization": f"Bearer {create_access_token({'user_id': 1})}"}
    product_data = {
        "name": "Test AI Agent",
        "description": "Test Description",
        "price": 20.00,
        "category": "AUTOMATION",
    }
    response = client.post("/marketplace/products", json=product_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == product_data["name"]

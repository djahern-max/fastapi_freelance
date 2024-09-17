# conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db, SessionLocal
from app import models
from sqlalchemy.orm import sessionmaker

# Create a TestClient for FastAPI app
@pytest.fixture
def client():
    return TestClient(app)

# Fixture to set up the database session
@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Fixture for creating a test user
@pytest.fixture
def test_user(client, session):
    user_data = {
        "email": "test@gmail.com",
        "password": "password123"
    }
    res = client.post("/users/", json=user_data)
    assert res.status_code == 200
    new_user = res.json()
    new_user["password"] = user_data["password"]  # Add password to the user data for future login
    return new_user

# Fixture for creating test posts
@pytest.fixture
def test_posts(session, test_user):
    posts = [
        models.Post(title="First Post", content="First Content", user_id=test_user['id']),
        models.Post(title="Second Post", content="Second Content", user_id=test_user['id']),
    ]
    session.add_all(posts)
    session.commit()
    return posts



import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
import os
from dotenv import load_dotenv

# Load test environment variables
load_dotenv(".env.test")

# Get database configuration from environment variables
DB_HOST = os.getenv("DATABASE_HOSTNAME")
DB_PORT = os.getenv("DATABASE_PORT")
DB_PASS = os.getenv("DATABASE_PASSWORD")
DB_NAME = os.getenv("DATABASE_NAME")
DB_USER = os.getenv("DATABASE_USERNAME")

# Construct database URL
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function")
def client():
    # Setup
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    # Teardown
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_user(client):
    user_data = {
        "username": "testuser",
        "password": "testpassword123!"
    }
    response = client.post("/auth/register", json=user_data)
    assert response.status_code == 200
    return user_data

@pytest.fixture
def test_user2(client):
    user_data = {
        "username": "testuser2",
        "password": "testpassword123!"
    }
    response = client.post("/auth/register", json=user_data)
    assert response.status_code == 200
    return user_data

@pytest.fixture
def token(client, test_user):
    response = client.post(
        "/auth/login",
        json={
            "username": test_user["username"],
            "password": test_user["password"]
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture
def token2(client, test_user2):
    response = client.post(
        "/auth/login",
        json={
            "username": test_user2["username"],
            "password": test_user2["password"]
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture
def test_project(client, token):
    project_data = {
        "name": "Test Project",
        "description": "Test Project Description"
    }
    response = client.post(
        "/projects/",
        json=project_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    return response.json()

@pytest.fixture
def test_note1(client, token, test_project):
    note_data = {
        "title": "Note for User 1",
        "content": "Content for user 1",
        "project_id": test_project["id"],
        "is_public": False
    }
    response = client.post(
        "/notes/",
        json=note_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    return response.json()

@pytest.fixture
def test_note2(client, token2, test_project):
    note_data = {
        "title": "Note for User 2",
        "content": "Content for user 2",
        "project_id": test_project["id"],
        "is_public": False
    }
    response = client.post(
        "/notes/",
        json=note_data,
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert response.status_code == 200
    return response.json()

class TestNoteSharing:

    def test_share_note_flow(self, client, token, token2, test_note1):
        note_id = test_note1["id"]
        
        # Get user2 ID dynamically
        user2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
        user2_id = user2.json()["id"]
        
        # Share the note with user 2
        share_data = {
            "shared_with_user_id": user2_id,
            "can_edit": True
        }
        response = client.post(
            f"/notes/{note_id}/share",
            json=share_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

        # Verify access
        response = client.get(
            f"/notes/{note_id}",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert response.status_code == 200

    def test_remove_note_share(self, client, token, token2, test_note1):
        note_id = test_note1["id"]

        # Get user2 ID dynamically
        user2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
        user2_id = user2.json()["id"]

        # Share the note with user 2
        share_data = {
            "shared_with_user_id": user2_id,
            "can_edit": True
        }
        client.post(
            f"/notes/{note_id}/share",
            json=share_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        # Remove the share
        response = client.delete(
            f"/notes/{note_id}/share/{user2_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

        # Verify that user 2 no longer has access
        response = client.get(
            f"/notes/{note_id}",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert response.status_code == 403  # User 2 should not be able to access the note

    def test_toggle_note_privacy(self, client, token, test_note1):
        note_id = test_note1["id"]

        # Toggle privacy to make the note public
        response = client.put(
            f"/notes/{note_id}/privacy?is_public=true",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_public"] is True

        # Toggle privacy to make the note private again
        response = client.put(
            f"/notes/{note_id}/privacy?is_public=false",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_public"] is False

    def test_get_note_shares(self, client, token, token2, test_note1):
        note_id = test_note1["id"]

        # Get user2 ID dynamically
        user2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
        user2_id = user2.json()["id"]

        # Share the note with user 2
        share_data = {
            "shared_with_user_id": user2_id,
            "can_edit": True
        }
        client.post(
            f"/notes/{note_id}/share",
            json=share_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        # Retrieve all shares of the note
        response = client.get(
            f"/notes/{note_id}/shares",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert len(response.json()) > 0  # At least one share should exist
        assert response.json()[0]["shared_with_user_id"] == user2_id

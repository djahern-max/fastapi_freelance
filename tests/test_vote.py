import pytest
from app import models
import uuid

@pytest.fixture
def test_user(client, session):
    unique_email = f"test_user_{uuid.uuid4()}@example.com"
    user_data = {"email": unique_email, "password": "password123"}
    res = client.post("/users/", json=user_data)
    assert res.status_code == 200
    new_user = res.json()

    return {
        "id": new_user["id"],
        "email": unique_email,
        "password": "password123"
    }

@pytest.fixture(autouse=True)
def reset_database(session):
    session.query(models.Vote).delete()
    session.query(models.User).delete()
    session.commit()

def test_vote_on_post(client, test_user, test_posts):
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    vote_data = {"post_id": test_posts[0].id, "dir": 1}  # Upvote
    response = client.post("/vote/", json=vote_data, headers=headers)
    assert response.status_code == 201
    assert response.json() == {"message": "Vote recorded successfully"}

def test_remove_vote_on_post(client, test_user, test_posts):
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Upvote a post first
    vote_data = {"post_id": test_posts[0].id, "dir": 1}  # Upvote
    response = client.post("/vote/", json=vote_data, headers=headers)
    assert response.status_code == 201
    assert response.json() == {"message": "Vote recorded successfully"}

    # Remove the vote
    vote_data["dir"] = 0  # Remove vote
    response = client.post("/vote/", json=vote_data, headers=headers)
    assert response.status_code == 201
    assert response.json() == {"message": "Vote deleted successfully"}

def test_vote_on_non_existent_post(client, test_user):
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    vote_data = {"post_id": 9999, "dir": 1}  # Upvote on non-existent post
    response = client.post("/vote/", json=vote_data, headers=headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Post with id 9999 does not exist"}

def test_duplicate_vote(client, test_user, test_posts):
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    vote_data = {"post_id": test_posts[0].id, "dir": 1}  # Upvote
    response = client.post("/vote/", json=vote_data, headers=headers)
    assert response.status_code == 201

    # Try to upvote again (should return 409 Conflict)
    response = client.post("/vote/", json=vote_data, headers=headers)
    assert response.status_code == 409
    assert response.json() == {"detail": f"User {test_user['id']} has already voted on post {test_posts[0].id}"}


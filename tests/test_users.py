import pytest
from jose import jwt
from app import schemas
from app.config import settings
import uuid
from jose.exceptions import JWTError
from app import models


@pytest.fixture(autouse=True)
def reset_database(session):
    # Clear the users table before each test to avoid duplicate users
    session.query(models.User).delete()
    session.commit()

@pytest.fixture
def test_user(client, session):
    unique_email = f"test_user_{uuid.uuid4()}@example.com"
    print(f"Creating test user with email: {unique_email}")  # Debug output
    user_data = {"email": unique_email, "password": "password123"}
    res = client.post("/users/", json=user_data)
    assert res.status_code == 200
    new_user = res.json()

    return {
        "id": new_user["id"],
        "email": unique_email,
        "password": "password123"
    }



# Test for creating user
def test_create_user(client):
    unique_email = f"test_{uuid.uuid4()}@gmail.com"  # Ensure a unique email
    res = client.post("/users/", json={"email": unique_email, "password": "123456"})
    new_user = schemas.UserOut(**res.json())
    assert new_user.email == unique_email
    assert res.status_code == 200


# Test for logging in a user
def test_login_user(client, test_user):
    res = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert res.status_code == 200
    login_res = schemas.Token(**res.json())
    try:
        payload = jwt.decode(login_res.access_token, settings.secret_key, settings.algorithm)
        id = int(payload.get('sub'))
        assert id == test_user['id']
    except JWTError:
        assert False, "Token decoding failed"


@pytest.mark.parametrize("email, password, status_code", [
    (f"wrongemail_{uuid.uuid4()}@gmail.com", '123456', 401),  # Invalid email
    (f"test_{uuid.uuid4()}@gmail.com", 'wrongpassword', 401),  # Invalid password
    (f"wrongemail_{uuid.uuid4()}@gmail.com", 'wrongpassword', 401),
    (None, '123456', 401),  # Expecting 401 if None for email
    (f"test_{uuid.uuid4()}@gmail.com", None, 401)  # Expecting 401 if None for password
])
def test_incorrect_login(client, test_user, email, password, status_code):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == status_code













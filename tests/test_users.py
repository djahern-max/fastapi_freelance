import pytest
from jose import jwt
from app import schemas

from app.config import settings
from app.config import settings


# def test_root(client):
#     res = client.get("/")
#     print(res.json().get('message'))
#     assert res.json().get('message') == "Welcome to ryze!"
#     assert res.status_code == 200

# Test for creating user
def test_create_user(client):
    res = client.post("/users/", json={"email": "test@gmail.com", "password": "123456"})
    new_user = schemas.UserOut(**res.json())
    print(res.json())
    assert new_user.email == "test@gmail.com"
    assert res.status_code == 200

def test_login_user(client, test_user):
    res = client.post(
        "/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    login_res = schemas.Token(**res.json())
    payload = jwt.decode(login_res.access_token, settings.secret_key, settings.algorithm)
    id = int(payload.get('sub'))  # Convert the ID from the JWT token to an integer
    assert id == test_user['id']


@pytest.mark.parametrize("email, password, status_code", [
    ('wrongemail@gmail.com', '123456', 401),  # Expecting 401 for incorrect credentials
    ('test@gmail.com', 'wrongpassword', 401),  # Wrong password should return 401
    ('wrongemail@gmail.com', 'wrongpassword', 401),  # Wrong email and password should return 401
    (None, '123456', 422),  # Missing email should return 422 (validation)
    ('test@gmail.com', None, 422)  # Missing password should return 422 (validation)
])
def test_incorrect_login(client, test_user, email, password, status_code):
    res = client.post(
        "/auth/login", data={"username": email, "password": password})
    assert res.status_code == status_code




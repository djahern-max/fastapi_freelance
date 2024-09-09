from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app import models  
from app.database import get_db
from dotenv import load_dotenv
import os

# Load the .env.test file
load_dotenv(dotenv_path=".env.test")

# Dynamically build the SQLALCHEMY_DATABASE_URL from individual components
DATABASE_USERNAME = os.getenv('DATABASE_USERNAME')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
DATABASE_HOST = os.getenv('DATABASE_HOST')
DATABASE_PORT = os.getenv('DATABASE_PORT')
DATABASE_NAME = os.getenv('DATABASE_NAME')

SQLALCHEMY_DATABASE_URL = f'postgresql://{DATABASE_USERNAME}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}'

# Create engine and session
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture()
def session():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create client fixture
@pytest.fixture()
def client(session):
    def override_get_db():
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)

@pytest.fixture
def test_user(client):
    user_data = {"email": "test@gmail.com", "password": "123456"}
    res = client.post("/users/", json=user_data)

    assert res.status_code == 200
    print(res.json())
    new_user = res.json()
    new_user['password'] = user_data['password']
    return new_user

@pytest.fixture
def test_posts(test_user, session):
    posts_data = [{
        "title": "first title",
        "content": "first content",
        "user_id": test_user['id']  # Use user_id, which matches your Post model
    }, {
        "title": "2nd title",
        "content": "2nd content",
        "user_id": test_user['id']  # Use user_id
    },
    {
        "title": "3rd title",
        "content": "3rd content",
        "user_id": test_user['id']  # Use user_id
    }, {
        "title": "4th title",
        "content": "4th content",
        "user_id": test_user['id']  # Use user_id
    }]

    def create_post_model(post):
        return models.Post(**post)

    post_map = map(create_post_model, posts_data)
    posts = list(post_map)

    session.add_all(posts)
    session.commit()

    return session.query(models.Post).all()

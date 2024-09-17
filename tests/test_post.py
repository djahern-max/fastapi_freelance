import pytest
from app import models
import uuid  # For generating unique emails


@pytest.fixture(autouse=True)
def reset_database(session):
    # Drop and recreate all tables before each test
    models.Base.metadata.drop_all(bind=session.bind)
    models.Base.metadata.create_all(bind=session.bind)


def test_get_all_posts(client, test_user, test_posts):
    # Log in the test user to get a token
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Set the authorization header with the token
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Make a request to get all posts
    response = client.get("/posts/", headers=headers)
    assert response.status_code == 200

    # Check that the returned posts match the test posts
    posts = response.json()
    assert len(posts) == len(test_posts)  # Ensure the count matches

    titles = [post["title"] for post in posts]
    contents = [post["content"] for post in posts]

    for post in test_posts:
        assert post.title in titles
        assert post.content in contents


def test_unauthorized_user_cannot_get_posts(client):
    # Attempt to get posts without authorization
    response = client.get("/posts/")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_get_post_by_id(client, test_user, test_posts):
    # Log in the test user to get a token
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Set the authorization header
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Get a post by ID
    post_id = test_posts[0].id
    response = client.get(f"/posts/{post_id}", headers=headers)
    assert response.status_code == 200

    # Check that the post data matches the test post
    post = response.json()
    assert post["title"] == test_posts[0].title
    assert post["content"] == test_posts[0].content
    assert post["id"] == test_posts[0].id


def test_unauthorized_user_cannot_get_non_existent_post(client):
    # Attempt to get a post with a non-existent ID without authorization
    response = client.get("/posts/8888")  
    assert response.status_code == 404  



@pytest.mark.parametrize("title, content, published", [
    ("Test Post", "This is a test post", True),
    ("Another Post", "This is another test post", False),
])
def test_create_post(client, test_user, title, content, published):
    # Log in the test user to get a token
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Create the post
    post_data = {
        "title": title,
        "content": content,
        "published": published
    }

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Send request to create the post
    response = client.post("/posts/", json=post_data, headers=headers)
    assert response.status_code == 201

    # Check the created post
    created_post = response.json()
    assert created_post["title"] == post_data["title"]
    assert created_post["content"] == post_data["content"]
    assert created_post["published"] == post_data["published"]
    print(response.json())


def test_create_post_default_published_true(client, test_user):
    # Log in the test user to get a token
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Create a post without specifying "published"
    post_data = {
        "title": "Test Post",
        "content": "This is a test post",
    }

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Send request to create the post
    response = client.post("/posts/", json=post_data, headers=headers)
    assert response.status_code == 201

    # Check that the "published" field defaults to True
    created_post = response.json()
    assert created_post["title"] == post_data["title"]
    assert created_post["content"] == post_data["content"]
    assert created_post["published"] == True
    print(response.json())


def test_unauthorized_user_create_post(client):
    # Attempt to create a post without authentication
    post_data = {
        "title": "Test Post",
        "content": "This is a test post",
    }

    response = client.post("/posts/", json=post_data)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_unauthorized_user_cannot_delete_post(client, test_posts):
    # Attempt to delete a post without authorization
    post_id = test_posts[0].id
    response = client.delete(f"/posts/{post_id}")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_delete_post(client, test_user, test_posts):
    # Log in the test user to get a token
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Get the post ID from the first test post
    post_id = test_posts[0].id

    # Send request to delete the post
    response = client.delete(f"/posts/{post_id}", headers=headers)
    assert response.status_code == 200

    # Verify that the post is deleted by trying to fetch it
    response = client.get(f"/posts/{post_id}", headers=headers)
    assert response.status_code == 404


def test_user_cannot_delete_another_users_post(client, test_user, test_posts, session):
    # Create a second user who will try to delete the first user's post
    second_user_data = {
        "email": f"seconduser_{uuid.uuid4()}@example.com",  # Ensure unique email
        "password": "password123"
    }
    response = client.post("/users/", json=second_user_data)
    assert response.status_code == 200

    # Log in with the second user
    response = client.post("/auth/login", data={"username": second_user_data['email'], "password": second_user_data['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Re-query the post created by the first user
    post = session.query(models.Post).filter(models.Post.user_id == test_user['id']).first()
    assert post is not None

    post_id = post.id

    # Attempt to delete the post created by the first user
    response = client.delete(f"/posts/{post_id}", headers=headers)

    # Expect 403 Forbidden
    assert response.status_code == 403
    assert response.json() == {"detail": "You are not authorized to delete this post"}


def test_update_post(client, test_user, test_posts):
    # Log in the test user to get a token
    response = client.post("/auth/login", data={"username": test_user['email'], "password": test_user['password']})
    assert response.status_code == 200
    token = response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Get the post ID from the first test post
    post_id = test_posts[0].id

    # Data to update the post with
    updated_post_data = {
        "title": "Updated Title",
        "content": "Updated content",
        "published": True
    }

    # Send request to update the post
    response = client.put(f"/posts/{post_id}", json=updated_post_data, headers=headers)
    assert response.status_code == 200

    # Verify the updated post content
    updated_post = response.json()
    assert updated_post["title"] == updated_post_data["title"]
    assert updated_post["content"] == updated_post_data["content"]
    assert updated_post["published"] == updated_post_data["published"]

    #


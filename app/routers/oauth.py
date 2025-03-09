from fastapi import APIRouter, Depends, HTTPException, Request, status
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from jose import jwt
import os
from app import models, schemas, database, oauth2

router = APIRouter()

oauth = OAuth()

# Register OAuth providers
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    access_token_url="https://oauth2.googleapis.com/token",
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    client_kwargs={"scope": "user:email"},
)

oauth.register(
    name="linkedin",
    client_id=os.getenv("LINKEDIN_CLIENT_ID"),
    client_secret=os.getenv("LINKEDIN_CLIENT_SECRET"),
    authorize_url="https://www.linkedin.com/oauth/v2/authorization",
    access_token_url="https://www.linkedin.com/oauth/v2/accessToken",
    client_kwargs={"scope": "r_liteprofile r_emailaddress"},
)


@router.get("/auth/{provider}")
async def login(provider: str, request: Request):
    redirect_uri = request.url_for("auth_callback", provider=provider)
    return await oauth.create_client(provider).authorize_redirect(request, redirect_uri)


@router.get("/auth/{provider}/callback")
async def auth_callback(
    provider: str, request: Request, db: Session = Depends(database.get_db)
):
    oauth_client = oauth.create_client(provider)
    token = await oauth_client.authorize_access_token(request)

    # Fetch user info based on provider
    if provider == "google":
        user_info = await oauth_client.parse_id_token(request, token)
    elif provider == "github":
        user_info = await oauth_client.get("https://api.github.com/user", token=token)
        user_info = user_info.json()
    elif provider == "linkedin":
        user_info = await oauth_client.get(
            "https://api.linkedin.com/v2/me", token=token
        )
        user_email = await oauth_client.get(
            "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
            token=token,
        )
        user_info = user_info.json()
        user_email = user_email.json()
        user_info["email"] = user_email["elements"][0]["handle~"]["emailAddress"]

    # Extract email and name
    email = user_info.get("email", user_info.get("emailAddress", ""))
    full_name = user_info.get("name", user_info.get("localizedFirstName", ""))

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to retrieve email from OAuth provider",
        )

    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == email).first()

    if not existing_user:
        # Create new user if not found
        new_user = models.User(
            username=email.split("@")[0],  # Use email username as default
            email=email,
            full_name=full_name,
            password=None,  # No password for OAuth users
            user_type="client",  # Default to client, modify as needed
            is_active=True,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        existing_user = new_user

    # Create JWT token
    access_token = oauth2.create_access_token(data={"sub": str(existing_user.id)})

    return {"access_token": access_token, "token_type": "bearer", "user": existing_user}

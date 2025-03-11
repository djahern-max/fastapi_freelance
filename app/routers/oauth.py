from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from jose import jwt
import os
import uuid  # For generating unique state
from app import models, schemas, database, oauth2
import requests
import logging
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User


# Setup logging
logger = logging.getLogger(__name__)

router = APIRouter()

oauth = OAuth()

# Register OAuth providers
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        "prompt": "select_account",
    },
)

oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    client_kwargs={"scope": "user:email"},
)


@router.get("/auth/{provider}")
async def login(provider: str, request: Request):
    """Start OAuth login and ensure fresh session state"""
    redirect_uri = request.url_for("auth_callback", provider=provider)
    logger.info(f"OAuth login initiated for provider: {provider}")
    logger.info(f"Redirect URI: {redirect_uri}")

    # 🔹 Clear old session state before creating a new one
    request.session.clear()

    # 🔹 Generate a unique state value
    unique_state = str(uuid.uuid4())
    request.session["oauth_state"] = unique_state  # Store state in session
    logger.info(f"Generated OAuth state: {unique_state}")

    return await oauth.create_client(provider).authorize_redirect(
        request, redirect_uri, state=unique_state
    )


# Fix for app/routers/oauth.py
# In the auth_callback function, fix the error with dashboard_path variable


@router.get("/auth/{provider}/callback")
async def auth_callback(
    provider: str, request: Request, db: Session = Depends(database.get_db)
):
    """Handle OAuth callback and validate state"""
    # Log incoming request for debugging
    logger.info(f"Handling callback for {provider}")
    logger.info(f"Query params: {dict(request.query_params)}")

    # Get state and code
    received_state = request.query_params.get("state")
    stored_state = request.session.get("oauth_state", None)
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    logger.info(f"Received state: {received_state}, Stored state: {stored_state}")

    if error:
        logger.error(f"OAuth Error: {error}")
        return RedirectResponse(
            url=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/oauth-error?error={error}&provider={provider}"
        )

    if received_state != stored_state:
        logger.warning(
            f"CSRF Warning! State mismatch: received={received_state}, stored={stored_state}"
        )
        return RedirectResponse(
            url=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/oauth-error?error=state_mismatch&provider={provider}"
        )

    if not code:
        logger.error("Missing authorization code")
        return RedirectResponse(
            url=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/oauth-error?error=missing_code&provider={provider}"
        )


@router.get("/auth/github/token")
async def github_token(code: str, db: Session = Depends(database.get_db)):
    """
    Exchange GitHub authorization code for access token and user info
    This endpoint is designed for client-side OAuth flow where the state parameter
    is handled by the frontend.
    """
    logger.info(f"GitHub token exchange initiated with code")

    try:
        # Define frontend URL
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

        # Exchange code for token
        token_data = {
            "client_id": os.getenv("GITHUB_CLIENT_ID"),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
            "code": code,
        }

        # Exchange code for token
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            data=token_data,
            headers={"Accept": "application/json"},
        )

        if token_response.status_code != 200:
            logger.error(f"GitHub token error: {token_response.text}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange GitHub code: {token_response.text}",
            )

        token_json = token_response.json()
        access_token = token_json.get("access_token")

        if not access_token:
            logger.error("No access token in GitHub response")
            raise HTTPException(
                status_code=400, detail="No access token received from GitHub"
            )

        # Rest of the function remains the same as in the previous version...
        # Get user data, create/update user, generate app token, etc.

        # Get user data
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/json",
        }

        # Get user profile
        user_response = requests.get("https://api.github.com/user", headers=headers)
        if user_response.status_code != 200:
            logger.error(f"GitHub user info error: {user_response.text}")
            raise HTTPException(
                status_code=400, detail="Failed to get user info from GitHub"
            )

        user_info = user_response.json()

        # Get user email (might be private)
        email_response = requests.get(
            "https://api.github.com/user/emails", headers=headers
        )
        if email_response.status_code != 200:
            logger.error(f"GitHub email error: {email_response.text}")
            raise HTTPException(
                status_code=400, detail="Failed to get email from GitHub"
            )

        emails = email_response.json()

        # Find primary email
        email = None
        for email_obj in emails:
            if email_obj.get("primary") and email_obj.get("verified"):
                email = email_obj.get("email")
                break

        if not email:
            logger.error("No verified primary email found")
            raise HTTPException(
                status_code=400, detail="No verified email found on GitHub account"
            )

        # Check if user exists
        user = db.query(models.User).filter(models.User.email == email).first()
        is_new_user = False

        if not user:
            is_new_user = True
            logger.info(f"Creating new user for GitHub email: {email}")

            # Generate username
            username = user_info.get("login") or email.split("@")[0]
            base_username = username

            # Check if username exists
            counter = 1
            while (
                db.query(models.User).filter(models.User.username == username).first()
            ):
                username = f"{base_username}{counter}"
                counter += 1

            try:
                new_user = models.User(
                    email=email,
                    username=username,
                    full_name=user_info.get("name", ""),
                    password="",  # No password for OAuth users
                    github_id=str(user_info.get("id")),
                    needs_role_selection=True,
                    is_active=True,
                    terms_accepted=True,  # Assume terms accepted for OAuth
                )

                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                user = new_user

            except Exception as e:
                logger.error(f"Error creating GitHub user: {str(e)}")
                db.rollback()
                raise HTTPException(
                    status_code=500, detail=f"Failed to create user: {str(e)}"
                )
        else:
            # Update GitHub ID if not set
            if not user.github_id:
                user.github_id = str(user_info.get("id"))
                db.commit()

        # Create access token
        app_access_token = oauth2.create_access_token(data={"sub": str(user.id)})

        # Return user data and token
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "user_type": user.user_type,
                "created_at": user.created_at,
                "needs_role_selection": user.needs_role_selection,
            },
            "provider_id": user_info.get("id"),
            "access_token": app_access_token,
            "token_type": "bearer",
        }

    except Exception as e:
        logger.error(f"Exception in GitHub OAuth token exchange: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OAuth error: {str(e)}")

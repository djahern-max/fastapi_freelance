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

    try:
        # Define frontend URL once
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        is_new_user = False

        # --- Google OAuth Processing ---
        if provider == "google":
            # Direct implementation for Google
            token_data = {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": request.url_for("auth_callback", provider=provider),
            }

            logger.info(f"Google token request data: {token_data}")

            # Get token directly from Google
            token_response = requests.post(
                "https://oauth2.googleapis.com/token", data=token_data
            )
            if token_response.status_code != 200:
                logger.error(f"Google token error: {token_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=token_failed&provider={provider}"
                )

            token_json = token_response.json()
            access_token = token_json.get("access_token")

            if not access_token:
                logger.error("No access token in Google response")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=no_access_token&provider={provider}"
                )

            # Get user info from Google
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo", headers=headers
            )

            if user_response.status_code != 200:
                logger.error(f"Google user info error: {user_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=user_info_failed&provider={provider}"
                )

            user_info = user_response.json()
            logger.info(f"Google user info: {user_info}")

            # Extract user details
            email = user_info.get("email")
            if not email:
                logger.error("Could not get email from Google")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=no_email&provider={provider}"
                )

            # Get or create user
            user = db.query(models.User).filter(models.User.email == email).first()
            logger.info(f"User query result: {user}")

            if not user:
                is_new_user = True
                logger.info(f"Creating new user for email: {email}")
                # Generate a username from email
                username = email.split("@")[0]
                base_username = username

                # Check if username already exists
                counter = 1
                while (
                    db.query(models.User)
                    .filter(models.User.username == username)
                    .first()
                ):
                    username = f"{base_username}{counter}"
                    counter += 1

                logger.info(f"Generated username: {username}")

                # Create new user without setting user_type
                try:
                    new_user = models.User(
                        email=email,
                        username=username,
                        full_name=user_info.get("name", ""),
                        password="",  # No password for OAuth users
                        google_id=user_info.get("sub"),
                        needs_role_selection=True,
                        is_active=True,
                        terms_accepted=True,  # Assume terms accepted for OAuth
                    )

                    logger.info(f"User object created: {new_user}")
                    db.add(new_user)
                    db.commit()
                    logger.info("User committed to database")
                    db.refresh(new_user)
                    logger.info(f"User refreshed, id: {new_user.id}")
                    user = new_user

                except Exception as e:
                    logger.error(f"Error creating user: {str(e)}")
                    db.rollback()
                    return RedirectResponse(
                        url=f"{frontend_url}/oauth-error?error=user_creation_failed&provider={provider}"
                    )
            else:
                # If user doesn't have Google ID yet, add it
                if not user.google_id:
                    user.google_id = user_info.get("sub")
                    db.commit()
                    logger.info(f"Updated existing user with Google ID: {user.id}")

            # Verify user has an id before creating token
            if not hasattr(user, "id") or user.id is None:
                logger.error(f"User missing id: {user}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=missing_user_id&provider={provider}"
                )

            # Create access token
            user_id = str(user.id)
            logger.info(f"Creating access token for user id: {user_id}")
            app_access_token = oauth2.create_access_token(data={"sub": user_id})

            # Check if user needs role selection
            if user.needs_role_selection:
                # Redirect to select-role endpoint with token
                redirect_url = (
                    f"{frontend_url}/api/auth/select-role?token={app_access_token}"
                )
            else:
                # Redirect to oauth-success with token
                redirect_url = f"{frontend_url}/oauth-success?token={app_access_token}"

            logger.info(f"Redirecting to: {redirect_url}")
            return RedirectResponse(url=redirect_url)

        # --- GitHub OAuth Processing ---
        elif provider == "github":
            # Implement GitHub OAuth
            token_data = {
                "client_id": os.getenv("GITHUB_CLIENT_ID"),
                "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
                "code": code,
                "redirect_uri": request.url_for("auth_callback", provider=provider),
            }

            # Exchange code for token
            token_response = requests.post(
                "https://github.com/login/oauth/access_token",
                data=token_data,
                headers={"Accept": "application/json"},
            )

            if token_response.status_code != 200:
                logger.error(f"GitHub token error: {token_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=token_failed&provider={provider}"
                )

            token_json = token_response.json()
            access_token = token_json.get("access_token")

            if not access_token:
                logger.error("No access token in GitHub response")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=no_access_token&provider={provider}"
                )

            # Get user data
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/json",
            }

            # Get user profile
            user_response = requests.get("https://api.github.com/user", headers=headers)
            if user_response.status_code != 200:
                logger.error(f"GitHub user info error: {user_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=user_info_failed&provider={provider}"
                )

            user_info = user_response.json()

            # Get user email (might be private)
            email_response = requests.get(
                "https://api.github.com/user/emails", headers=headers
            )
            if email_response.status_code != 200:
                logger.error(f"GitHub email error: {email_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=email_fetch_failed&provider={provider}"
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
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=no_verified_email&provider={provider}"
                )

            # Check if user exists
            user = db.query(models.User).filter(models.User.email == email).first()

            if not user:
                is_new_user = True
                logger.info(f"Creating new user for GitHub email: {email}")

                # Generate username
                username = user_info.get("login") or email.split("@")[0]
                base_username = username

                # Check if username exists
                counter = 1
                while (
                    db.query(models.User)
                    .filter(models.User.username == username)
                    .first()
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
                    return RedirectResponse(
                        url=f"{frontend_url}/oauth-error?error=user_creation_failed&provider={provider}"
                    )
            else:
                # Update GitHub ID if not set
                if not user.github_id:
                    user.github_id = str(user_info.get("id"))
                    db.commit()

            # Create access token
            app_access_token = oauth2.create_access_token(data={"sub": str(user.id)})

            # Check if user needs role selection
            if user.needs_role_selection:
                # Redirect to select-role endpoint with token
                redirect_url = (
                    f"{frontend_url}/api/auth/select-role?token={app_access_token}"
                )
            else:
                # Redirect to oauth-success with token
                redirect_url = f"{frontend_url}/oauth-success?token={app_access_token}"

            logger.info(f"Redirecting to: {redirect_url}")
            return RedirectResponse(url=redirect_url)
        # --- LinkedIn OAuth Processing ---
        elif provider == "linkedin":
            # Direct implementation for LinkedIn
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": request.url_for("auth_callback", provider=provider),
                "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
                "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
            }

            token_response = requests.post(
                "https://www.linkedin.com/oauth/v2/accessToken", data=token_data
            )
            if token_response.status_code != 200:
                logger.error(f"LinkedIn token error: {token_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=token_failed&provider={provider}"
                )

            token_json = token_response.json()
            access_token = token_json.get("access_token")

            if not access_token:
                logger.error("No access token in LinkedIn response")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=no_access_token&provider={provider}"
                )

            # Get user info from LinkedIn
            headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
            }

            # Get profile data
            user_response = requests.get(
                "https://api.linkedin.com/v2/me",
                headers=headers,
                params={"projection": "(id,firstName,lastName,profilePicture)"},
            )
            if user_response.status_code != 200:
                logger.error(f"LinkedIn user info error: {user_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=user_info_failed&provider={provider}"
                )

            user_info = user_response.json()

            # Get email address
            email_response = requests.get(
                "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                headers=headers,
            )
            if email_response.status_code != 200:
                logger.error(f"LinkedIn email error: {email_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=email_fetch_failed&provider={provider}"
                )

            email_data = email_response.json()

            # Extract email from LinkedIn's nested response format
            email = None
            if "elements" in email_data and len(email_data["elements"]) > 0:
                email_element = email_data["elements"][0]
                if (
                    "handle~" in email_element
                    and "emailAddress" in email_element["handle~"]
                ):
                    email = email_element["handle~"]["emailAddress"]

            if not email:
                logger.error("Could not get email from LinkedIn")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=no_email&provider={provider}"
                )

            # Extract name from LinkedIn's locale-aware format
            first_name = ""
            if "firstName" in user_info and "localized" in user_info["firstName"]:
                # Get the first locale value
                locales = list(user_info["firstName"]["localized"].values())
                if locales:
                    first_name = locales[0]

            last_name = ""
            if "lastName" in user_info and "localized" in user_info["lastName"]:
                # Get the first locale value
                locales = list(user_info["lastName"]["localized"].values())
                if locales:
                    last_name = locales[0]

            full_name = f"{first_name} {last_name}".strip()

            # Get or create user
            user = db.query(models.User).filter(models.User.email == email).first()
            logger.info(f"LinkedIn user query result: {user}")

            if not user:
                is_new_user = True
                logger.info(f"Creating new user for LinkedIn email: {email}")
                # Generate a username from email
                username = email.split("@")[0]
                base_username = username

                # Check if username already exists
                counter = 1
                while (
                    db.query(models.User)
                    .filter(models.User.username == username)
                    .first()
                ):
                    username = f"{base_username}{counter}"
                    counter += 1

                try:
                    # Create new user
                    new_user = models.User(
                        email=email,
                        username=username,
                        full_name=full_name,
                        password="",  # No password for OAuth users
                        linkedin_id=user_info.get("id"),
                        needs_role_selection=True,
                        is_active=True,
                        terms_accepted=True,  # Assume terms accepted for OAuth
                    )
                    db.add(new_user)
                    db.commit()
                    db.refresh(new_user)
                    user = new_user

                except Exception as e:
                    logger.error(f"Error creating LinkedIn user: {str(e)}")
                    db.rollback()
                    return RedirectResponse(
                        url=f"{frontend_url}/oauth-error?error=user_creation_failed&provider={provider}"
                    )
            else:
                # Update LinkedIn ID if not set
                if not user.linkedin_id:
                    user.linkedin_id = user_info.get("id")
                    db.commit()

            # Create access token
            app_access_token = oauth2.create_access_token(data={"sub": str(user.id)})

            # Check if user needs role selection
            if user.needs_role_selection:
                # Redirect to select-role endpoint with token
                redirect_url = (
                    f"{frontend_url}/api/auth/select-role?token={app_access_token}"
                )
            else:
                # Redirect to oauth-success with token
                redirect_url = f"{frontend_url}/oauth-success?token={app_access_token}"

            logger.info(f"Redirecting to: {redirect_url}")
            return RedirectResponse(url=redirect_url)

        else:
            logger.error(f"Unsupported provider: {provider}")
            return RedirectResponse(
                url=f"{frontend_url}/oauth-error?error=unsupported_provider&provider={provider}"
            )

    except Exception as e:
        logger.error(f"Exception in {provider} OAuth: {str(e)}")
        return RedirectResponse(
            url=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/oauth-error?error={str(e)}&provider={provider}"
        )


@router.get("/auth/check-role")
def check_role(email: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "needs_role_selection": user.needs_role_selection,
        "user_type": user.user_type,
    }


@router.post("/auth/set-role")
def set_user_role(data: schemas.RoleSelection, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.user_type = data.user_type
    user.needs_role_selection = False
    db.commit()

    return {"message": "Role updated successfully"}


@router.get("/auth/user-by-oauth/{provider}/{provider_id}")
def get_user_by_oauth(provider: str, provider_id: str, db: Session = Depends(get_db)):
    """Retrieve user based on OAuth provider ID"""
    if provider == "google":
        user = db.query(User).filter(User.google_id == provider_id).first()
    elif provider == "github":
        user = db.query(User).filter(User.github_id == provider_id).first()
    elif provider == "linkedin":
        user = db.query(User).filter(User.linkedin_id == provider_id).first()
    else:
        raise HTTPException(status_code=400, detail="Invalid provider")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "user_type": user.user_type,
        "created_at": user.created_at,
        "google_id": user.google_id,
        "github_id": user.github_id,
        "linkedin_id": user.linkedin_id,
        "needs_role_selection": user.needs_role_selection,
    }

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
import datetime

# Setup logging
logger = logging.getLogger(__name__)

router = APIRouter()

oauth = OAuth()


# Add this function at the top of your file
def debug_log(message):
    with open("/home/dane/linkedin_debug.log", "a") as f:
        f.write(f"{datetime.datetime.now()}: {message}\n")


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
    client_kwargs={"scope": "openid profile email"},  # Match what's in the UI
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

    # Define frontend URL for redirects
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Get state and code
    received_state = request.query_params.get("state")
    stored_state = request.session.get("oauth_state", None)
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    logger.info(f"Received state: {received_state}, Stored state: {stored_state}")

    if error:
        logger.error(f"OAuth Error: {error}")
        return RedirectResponse(
            url=f"{frontend_url}/oauth-error?error={error}&provider={provider}"
        )

    if received_state != stored_state:
        logger.warning(
            f"CSRF Warning! State mismatch: received={received_state}, stored={stored_state}"
        )
        return RedirectResponse(
            url=f"{frontend_url}/oauth-error?error=state_mismatch&provider={provider}"
        )

    if not code:
        logger.error("Missing authorization code")
        return RedirectResponse(
            url=f"{frontend_url}/oauth-error?error=missing_code&provider={provider}"
        )

    try:
        # Exchange code for token
        token = await oauth.create_client(provider).authorize_access_token(request)

        # Get user info based on provider
        user_info = None
        email = None
        provider_id = None
        full_name = ""

        if provider == "google":
            user_info = token.get("userinfo", {})
            email = user_info.get("email")
            provider_id = user_info.get("sub")
            full_name = user_info.get("name", "")

        elif provider == "github":
            # Get user data from GitHub
            access_token = token.get("access_token")
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/json",
            }

            # Get user profile
            user_response = requests.get("https://api.github.com/user", headers=headers)
            if user_response.status_code != 200:
                logger.error(f"GitHub user info error: {user_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=profile_failed&provider={provider}"
                )

            user_info = user_response.json()
            provider_id = user_info.get("id")
            full_name = user_info.get("name", "")

            # Get user email
            email_response = requests.get(
                "https://api.github.com/user/emails", headers=headers
            )
            if email_response.status_code != 200:
                logger.error(f"GitHub email error: {email_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=email_failed&provider={provider}"
                )

            emails = email_response.json()
            for email_obj in emails:
                if email_obj.get("primary") and email_obj.get("verified"):
                    email = email_obj.get("email")
                    break

        elif provider == "linkedin":
            debug_log("Starting LinkedIn OAuth flow")
            # Get user data from LinkedIn
            access_token = token.get("access_token")
            debug_log(f"LinkedIn access token: {access_token[:10]}...")
            logger.info(
                f"LinkedIn access token obtained: {access_token[:10]}... (truncated)"
            )

            headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",  # Important for LinkedIn API v2
                "Content-Type": "application/json",
            }

            # Try OpenID Connect userinfo endpoint first
            userinfo_url = "https://api.linkedin.com/v2/userinfo"
            logger.info(f"Requesting LinkedIn userinfo from: {userinfo_url}")

            userinfo_response = requests.get(userinfo_url, headers=headers)
            debug_log(
                f"LinkedIn userinfo response: {userinfo_response.status_code} - {userinfo_response.text}"
            )
            logger.info(
                f"LinkedIn userinfo response status: {userinfo_response.status_code}"
            )
            logger.info(f"LinkedIn userinfo response: {userinfo_response.text}")

            # If userinfo endpoint works, use it
            if userinfo_response.status_code == 200:
                user_info = userinfo_response.json()
                logger.info(f"LinkedIn userinfo data: {user_info}")

                # Extract data from OpenID userinfo response
                email = user_info.get("email")
                provider_id = user_info.get("sub")
                full_name = user_info.get("name", "")
                first_name = user_info.get("given_name", "")
                last_name = user_info.get("family_name", "")

                # If we got what we needed, skip the other API calls
                if email and provider_id:
                    logger.info("Successfully retrieved user info from OpenID endpoint")
                    # Full name fallback if needed
                    if not full_name and first_name and last_name:
                        full_name = f"{first_name} {last_name}".strip()
                else:
                    logger.info(
                        "OpenID endpoint missing email or ID, falling back to API"
                    )
                    # Fall back to API endpoints

            else:
                logger.info("OpenID endpoint failed, falling back to API")

            # If OpenID didn't provide what we need, use the API endpoints
            if not (userinfo_response.status_code == 200 and email and provider_id):
                # Step 1: Get basic profile data
                profile_url = "https://api.linkedin.com/v2/me"
                logger.info(f"Requesting LinkedIn profile from: {profile_url}")

                profile_response = requests.get(profile_url, headers=headers)
                logger.info(
                    f"LinkedIn profile response status: {profile_response.status_code}"
                )

                if profile_response.status_code != 200:
                    logger.error(f"LinkedIn profile error: {profile_response.text}")
                    return RedirectResponse(
                        url=f"{frontend_url}/oauth-error?error=profile_failed&provider={provider}"
                    )

                # Log the full response for debugging
                profile_info = profile_response.json()
                logger.info(f"LinkedIn profile data: {profile_info}")

                # Step 2: Get email address
                email_url = "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))"
                logger.info(f"Requesting LinkedIn email from: {email_url}")

                email_response = requests.get(email_url, headers=headers)
                logger.info(
                    f"LinkedIn email response status: {email_response.status_code}"
                )

                if email_response.status_code != 200:
                    logger.error(f"LinkedIn email error: {email_response.text}")
                    return RedirectResponse(
                        url=f"{frontend_url}/oauth-error?error=email_failed&provider={provider}"
                    )

                # Log the full response for debugging
                email_info = email_response.json()
                logger.info(f"LinkedIn email data: {email_info}")

                # Extract provider ID (should always be available)
                provider_id = profile_info.get("id")
                if not provider_id:
                    logger.error("LinkedIn profile missing ID field")
                    return RedirectResponse(
                        url=f"{frontend_url}/oauth-error?error=no_id&provider={provider}"
                    )

                # Extract email
                email = None
                try:
                    if "elements" in email_info and email_info["elements"]:
                        email_element = email_info["elements"][0]
                        if (
                            "handle~" in email_element
                            and "emailAddress" in email_element["handle~"]
                        ):
                            email = email_element["handle~"]["emailAddress"]
                except Exception as e:
                    logger.error(f"Error extracting LinkedIn email: {str(e)}")

                if not email:
                    logger.error("Failed to extract email from LinkedIn response")
                    return RedirectResponse(
                        url=f"{frontend_url}/oauth-error?error=no_email&provider={provider}"
                    )

                # Extract name fields
                first_name = ""
                last_name = ""

                # Newer LinkedIn API structure (check both possibilities)
                if "localizedFirstName" in profile_info:
                    first_name = profile_info.get("localizedFirstName", "")
                    last_name = profile_info.get("localizedLastName", "")
                # Older LinkedIn API structure
                elif "firstName" in profile_info:
                    if "localized" in profile_info["firstName"]:
                        locales = list(profile_info["firstName"]["localized"].values())
                        if locales:
                            first_name = locales[0]

                    if (
                        "lastName" in profile_info
                        and "localized" in profile_info["lastName"]
                    ):
                        locales = list(profile_info["lastName"]["localized"].values())
                        if locales:
                            last_name = locales[0]

                full_name = f"{first_name} {last_name}".strip()
                logger.info(
                    f"Extracted LinkedIn data - Name: '{full_name}', Email: '{email}', ID: '{provider_id}'"
                )

        # Verify we have required user info
        if not email:
            logger.error(f"Could not get email from {provider}")
            return RedirectResponse(
                url=f"{frontend_url}/oauth-error?error=no_email&provider={provider}"
            )

        if not provider_id:
            logger.error(f"Could not get ID from {provider}")
            return RedirectResponse(
                url=f"{frontend_url}/oauth-error?error=no_id&provider={provider}"
            )

        # Check if user exists
        user = db.query(models.User).filter(models.User.email == email).first()
        is_new_user = False

        if not user:
            is_new_user = True
            logger.info(f"Creating new user for {provider} email: {email}")

            # Generate username
            username = email.split("@")[0]
            base_username = username

            # Ensure username is unique
            counter = 1
            while (
                db.query(models.User).filter(models.User.username == username).first()
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
                    is_active=True,
                    needs_role_selection=True,
                    terms_accepted=True,  # Assume terms accepted for OAuth
                )

                # Set the provider-specific ID
                if provider == "google":
                    new_user.google_id = str(provider_id)
                elif provider == "github":
                    new_user.github_id = str(provider_id)
                elif provider == "linkedin":
                    new_user.linkedin_id = str(provider_id)

                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                user = new_user

            except Exception as e:
                logger.error(f"Error creating {provider} user: {str(e)}")
                db.rollback()
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=user_creation_failed&provider={provider}"
                )
        else:
            # Update provider ID if not set
            if provider == "google" and not user.google_id:
                user.google_id = str(provider_id)
                db.commit()
            elif provider == "github" and not user.github_id:
                user.github_id = str(provider_id)
                db.commit()
            elif provider == "linkedin" and not user.linkedin_id:
                user.linkedin_id = str(provider_id)
                db.commit()

        # Create app access token
        app_access_token = oauth2.create_access_token(data={"sub": str(user.id)})

        # Determine redirect based on role selection
        if user.needs_role_selection:
            redirect_url = f"{frontend_url}/select-role?token={app_access_token}"
        else:
            redirect_url = f"{frontend_url}/oauth-success?token={app_access_token}"

        logger.info(f"{provider} login successful. Redirecting to: {redirect_url}")
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"Exception in {provider} OAuth: {str(e)}")
        return RedirectResponse(
            url=f"{frontend_url}/oauth-error?error=user_info_failed&provider={provider}"
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

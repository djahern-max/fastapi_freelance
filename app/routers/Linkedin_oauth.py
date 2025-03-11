from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from sqlalchemy.orm import Session
import os
import uuid
import requests
import logging
from app.database import get_db
from app import models, oauth2

# Setup logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["linkedin_auth"])

# Create OAuth instance
oauth = OAuth()

# Register LinkedIn OAuth client
oauth.register(
    name="linkedin",
    client_id=os.getenv("LINKEDIN_CLIENT_ID"),
    client_secret=os.getenv("LINKEDIN_CLIENT_SECRET"),
    authorize_url="https://www.linkedin.com/oauth/v2/authorization",
    access_token_url="https://www.linkedin.com/oauth/v2/accessToken",
    client_kwargs={"scope": "openid profile email"},
)


@router.get("/auth/linkedin")
async def linkedin_login(request: Request):
    """
    Initiates LinkedIn OAuth login process.
    Generates a unique state value for CSRF protection.
    """
    # Define the callback URL
    redirect_uri = request.url_for("linkedin_callback")
    logger.info(f"LinkedIn OAuth login initiated")
    logger.info(f"Redirect URI: {redirect_uri}")

    # Clear old session state
    request.session.clear()

    # Generate and store unique state
    unique_state = str(uuid.uuid4())
    request.session["linkedin_oauth_state"] = unique_state
    logger.info(f"Generated LinkedIn OAuth state: {unique_state}")

    # Redirect to LinkedIn authorization page
    return await oauth.linkedin.authorize_redirect(
        request, redirect_uri, state=unique_state
    )


@router.get("/auth/linkedin/callback")
async def linkedin_callback(request: Request, db: Session = Depends(get_db)):
    """
    Handles LinkedIn OAuth callback.
    Validates state, exchanges code for token, gets user info, and creates/updates user.
    """
    # Log incoming request
    logger.info("Handling LinkedIn callback")
    logger.info(f"Query params: {dict(request.query_params)}")

    # Get frontend URL for redirects
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Get state and code
    received_state = request.query_params.get("state")
    stored_state = request.session.get("linkedin_oauth_state")
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    logger.info(f"Received state: {received_state}, Stored state: {stored_state}")

    # Handle errors from LinkedIn
    if error:
        logger.error(f"LinkedIn OAuth Error: {error}")
        return RedirectResponse(
            url=f"{frontend_url}/oauth-error?error={error}&provider=linkedin"
        )

    # Validate state to prevent CSRF
    if received_state != stored_state:
        logger.warning(
            f"CSRF Warning! State mismatch: received={received_state}, stored={stored_state}"
        )
        return RedirectResponse(
            url=f"{frontend_url}/oauth-error?error=state_mismatch&provider=linkedin"
        )

    # Verify we have an authorization code
    if not code:
        logger.error("Missing LinkedIn authorization code")
        return RedirectResponse(
            url=f"{frontend_url}/oauth-error?error=missing_code&provider=linkedin"
        )

    try:
        # Exchange code for token
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": request.url_for("linkedin_callback"),
            "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
            "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
        }

        logger.info(f"LinkedIn token request data: {token_data}")

        token_response = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_response.status_code != 200:
            logger.error(f"LinkedIn token error: {token_response.text}")
            return RedirectResponse(
                url=f"{frontend_url}/oauth-error?error=token_failed&provider=linkedin"
            )

        token_json = token_response.json()
        access_token = token_json.get("access_token")

        if not access_token:
            logger.error("No access token in LinkedIn response")
            return RedirectResponse(
                url=f"{frontend_url}/oauth-error?error=no_access_token&provider=linkedin"
            )

        # Set up headers for API requests
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # Try the OpenID Connect userinfo endpoint first
        user_response = requests.get(
            "https://api.linkedin.com/v2/userinfo", headers=headers
        )

        # Initialize variables
        email = None
        first_name = ""
        last_name = ""
        linkedin_id = None

        # Process response based on which API works
        if user_response.status_code == 200:
            # OpenID Connect format
            user_info = user_response.json()
            logger.info(f"LinkedIn user info from userinfo endpoint: {user_info}")

            email = user_info.get("email")
            first_name = user_info.get("given_name", "")
            last_name = user_info.get("family_name", "")
            linkedin_id = user_info.get("sub")
        else:
            logger.warning(f"LinkedIn userinfo endpoint failed: {user_response.text}")

            # Fall back to profile API
            profile_response = requests.get(
                "https://api.linkedin.com/v2/me?projection=(id,firstName,lastName)",
                headers=headers,
            )

            if profile_response.status_code != 200:
                logger.error(f"LinkedIn profile error: {profile_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=profile_failed&provider=linkedin"
                )

            # Get email address (separate API call)
            email_response = requests.get(
                "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                headers=headers,
            )

            if email_response.status_code != 200:
                logger.error(f"LinkedIn email error: {email_response.text}")
                return RedirectResponse(
                    url=f"{frontend_url}/oauth-error?error=email_failed&provider=linkedin"
                )

            # Parse responses
            profile_info = profile_response.json()
            email_info = email_response.json()

            # Extract LinkedIn ID
            linkedin_id = profile_info.get("id")

            # Extract email from elements
            if "elements" in email_info and email_info["elements"]:
                email_element = email_info["elements"][0]
                if (
                    "handle~" in email_element
                    and "emailAddress" in email_element["handle~"]
                ):
                    email = email_element["handle~"]["emailAddress"]

            # Extract first and last name from localized format
            if "firstName" in profile_info and "localized" in profile_info["firstName"]:
                locales = list(profile_info["firstName"]["localized"].values())
                if locales:
                    first_name = locales[0]

            if "lastName" in profile_info and "localized" in profile_info["lastName"]:
                locales = list(profile_info["lastName"]["localized"].values())
                if locales:
                    last_name = locales[0]

        # Combine first and last name
        full_name = f"{first_name} {last_name}".strip()

        # Verify we have required user info
        if not email:
            logger.error("Could not get email from LinkedIn")
            return RedirectResponse(
                url=f"{frontend_url}/oauth-error?error=no_email&provider=linkedin"
            )

        if not linkedin_id:
            logger.error("Could not get ID from LinkedIn")
            return RedirectResponse(
                url=f"{frontend_url}/oauth-error?error=no_id&provider=linkedin"
            )

        # Check if user exists
        user = db.query(models.User).filter(models.User.email == email).first()
        is_new_user = False

        if not user:
            is_new_user = True
            logger.info(f"Creating new user for LinkedIn email: {email}")

            # Generate username from email
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
                    linkedin_id=linkedin_id,
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
                    url=f"{frontend_url}/oauth-error?error=user_creation_failed&provider=linkedin"
                )
        else:
            # Update existing user's LinkedIn ID if not set
            if not user.linkedin_id:
                user.linkedin_id = linkedin_id
                db.commit()

        # Create app access token
        app_access_token = oauth2.create_access_token(data={"sub": str(user.id)})

        # Determine redirect based on role selection
        if user.needs_role_selection:
            redirect_url = f"{frontend_url}/select-role?token={app_access_token}"
        else:
            redirect_url = f"{frontend_url}/oauth-success?token={app_access_token}"

        logger.info(f"LinkedIn login successful. Redirecting to: {redirect_url}")
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"Exception in LinkedIn OAuth: {str(e)}")
        return RedirectResponse(
            url=f"{frontend_url}/oauth-error?error={str(e)}&provider=linkedin"
        )


@router.get("/auth/linkedin/token")
async def linkedin_token_exchange(
    code: str, redirect_uri: str, db: Session = Depends(get_db)
):
    """
    Dedicated endpoint for client-side LinkedIn OAuth flow.
    Exchanges code for token and returns user information.
    """
    logger.info("LinkedIn token exchange endpoint called")

    try:
        # Exchange code for token
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
            "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
        }

        token_response = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_response.status_code != 200:
            logger.error(f"LinkedIn token error: {token_response.text}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange LinkedIn code: {token_response.text}",
            )

        token_json = token_response.json()
        access_token = token_json.get("access_token")

        if not access_token:
            logger.error("No access token in LinkedIn response")
            raise HTTPException(
                status_code=400, detail="No access token received from LinkedIn"
            )

        # Get user info with the token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # Try the OpenID Connect endpoint first
        user_response = requests.get(
            "https://api.linkedin.com/v2/userinfo", headers=headers
        )

        if user_response.status_code == 200:
            user_info = user_response.json()

            email = user_info.get("email")
            linkedin_id = user_info.get("sub")
            first_name = user_info.get("given_name", "")
            last_name = user_info.get("family_name", "")
            full_name = f"{first_name} {last_name}".strip() or user_info.get("name", "")
        else:
            # Fall back to separate profile and email API calls
            profile_response = requests.get(
                "https://api.linkedin.com/v2/me?projection=(id,firstName,lastName)",
                headers=headers,
            )

            if profile_response.status_code != 200:
                raise HTTPException(
                    status_code=400, detail="Failed to get profile from LinkedIn"
                )

            email_response = requests.get(
                "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                headers=headers,
            )

            if email_response.status_code != 200:
                raise HTTPException(
                    status_code=400, detail="Failed to get email from LinkedIn"
                )

            profile_info = profile_response.json()
            email_info = email_response.json()

            # Extract user details
            linkedin_id = profile_info.get("id")

            # Extract name
            first_name = ""
            if "firstName" in profile_info and "localized" in profile_info["firstName"]:
                locales = list(profile_info["firstName"]["localized"].values())
                if locales:
                    first_name = locales[0]

            last_name = ""
            if "lastName" in profile_info and "localized" in profile_info["lastName"]:
                locales = list(profile_info["lastName"]["localized"].values())
                if locales:
                    last_name = locales[0]

            full_name = f"{first_name} {last_name}".strip()

            # Extract email
            email = None
            if "elements" in email_info and email_info["elements"]:
                email_element = email_info["elements"][0]
                if (
                    "handle~" in email_element
                    and "emailAddress" in email_element["handle~"]
                ):
                    email = email_element["handle~"]["emailAddress"]

        if not email:
            raise HTTPException(
                status_code=400, detail="No email found in LinkedIn account"
            )

        # Get or create user
        user = db.query(models.User).filter(models.User.email == email).first()
        is_new_user = False

        if not user:
            is_new_user = True

            # Generate username
            username = email.split("@")[0]
            base_username = username

            # Ensure unique username
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
                    full_name=full_name,
                    password="",  # No password for OAuth users
                    linkedin_id=linkedin_id,
                    needs_role_selection=True,
                    is_active=True,
                    terms_accepted=True,
                )

                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                user = new_user

            except Exception as e:
                db.rollback()
                raise HTTPException(
                    status_code=500, detail=f"Failed to create user: {str(e)}"
                )
        else:
            # Update LinkedIn ID if not set
            if not user.linkedin_id:
                user.linkedin_id = linkedin_id
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
            "provider_id": linkedin_id,
            "access_token": app_access_token,
            "token_type": "bearer",
            "is_new_user": is_new_user,
        }

    except Exception as e:
        logger.error(f"Exception in LinkedIn token exchange: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LinkedIn OAuth error: {str(e)}")

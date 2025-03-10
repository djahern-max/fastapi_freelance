from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from jose import jwt
import os
import uuid  # For generating unique state
from app import models, schemas, database, oauth2
import requests


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

    # 🔹 Clear old session state before creating a new one
    request.session.clear()

    # 🔹 Generate a unique state value
    unique_state = str(uuid.uuid4())
    request.session["oauth_state"] = unique_state  # Store state in session

    return await oauth.create_client(provider).authorize_redirect(
        request, redirect_uri, state=unique_state
    )


@router.get("/auth/{provider}/callback")
async def auth_callback(
    provider: str, request: Request, db: Session = Depends(database.get_db)
):
    """Handle OAuth callback and validate state"""
    # Log incoming request for debugging
    print(f"DEBUG: Handling callback for {provider}")
    print(f"DEBUG: Query params: {request.query_params}")

    # Get state and code
    received_state = request.query_params.get("state")
    stored_state = request.session.get("oauth_state", None)
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    print(f"DEBUG: Received state: {received_state}, Stored state: {stored_state}")

    if error:
        print(f"DEBUG: OAuth Error: {error}")
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    if received_state != stored_state:
        raise HTTPException(
            status_code=400, detail="CSRF Warning! State mismatch detected."
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:

        if provider == "google":
            # Direct implementation for Google
            token_data = {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": request.url_for("auth_callback", provider=provider),
            }

            print(f"DEBUG: Google token request data: {token_data}")

            # Get token directly from Google
            token_response = requests.post(
                "https://oauth2.googleapis.com/token", data=token_data
            )
            if token_response.status_code != 200:
                print(f"DEBUG: Google token error: {token_response.text}")
                raise HTTPException(
                    status_code=400, detail="Failed to get token from Google"
                )

            token_json = token_response.json()
            access_token = token_json.get("access_token")

            if not access_token:
                print("DEBUG: No access token in Google response")
                raise HTTPException(
                    status_code=400, detail="No access token in response"
                )

            # Get user info from Google
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo", headers=headers
            )

            if user_response.status_code != 200:
                print(f"DEBUG: Google user info error: {user_response.text}")
                raise HTTPException(
                    status_code=400, detail="Failed to get user info from Google"
                )

            user_info = user_response.json()
            print(f"DEBUG: Google user info: {user_info}")

            # Extract user details
            email = user_info.get("email")
            if not email:
                raise HTTPException(
                    status_code=400, detail="Could not get email from Google"
                )

            # Get or create user
            user = db.query(models.User).filter(models.User.email == email).first()
            print(f"DEBUG: User query result: {user}")  # Debug line

            # Track if this is a new user
            is_new_user = False

            if not user:
                is_new_user = True
                print(f"DEBUG: Creating new user for email: {email}")
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

                print(f"DEBUG: Generated username: {username}")

                # Create new user without setting user_type
                try:
                    new_user = models.User(
                        email=email,
                        username=username,
                        full_name=user_info.get("name", ""),
                        password="",  # No password for OAuth users
                        google_id=user_info.get("sub"),
                        # user_type is deliberately left out
                        is_active=True,
                        terms_accepted=True,  # Assume terms accepted for OAuth
                    )

                    print(f"DEBUG: User object created: {new_user}")
                    db.add(new_user)
                    db.commit()
                    print("DEBUG: User committed to database")
                    db.refresh(new_user)
                    print(f"DEBUG: User refreshed, id: {new_user.id}")
                    user = new_user

                    # Don't create a client profile here

                except Exception as e:
                    print(f"DEBUG: Error creating user: {str(e)}")
                    db.rollback()
                    raise HTTPException(
                        status_code=500, detail=f"Error creating user account: {str(e)}"
                    )

            # Verify user has an id before creating token
            if not hasattr(user, "id") or user.id is None:
                print(f"DEBUG: User missing id: {user}")
                raise HTTPException(
                    status_code=500, detail="User account is missing ID"
                )

            # Create access token
            user_id = str(user.id)
            print(f"DEBUG: Creating access token for user id: {user_id}")
            access_token = oauth2.create_access_token(data={"sub": user_id})

            # Redirect to frontend with token
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

            # Check if user needs to select a role
            if is_new_user or user.needs_role_selection:
                redirect_url = (
                    f"{frontend_url}/select-role?token={access_token}&provider=google"
                )
            else:
                redirect_url = (
                    f"{frontend_url}/oauth-success?token={access_token}&provider=google"
                )

            return RedirectResponse(url=redirect_url)

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
                print(f"DEBUG: LinkedIn token error: {token_response.text}")
                raise HTTPException(
                    status_code=400, detail="Failed to get token from LinkedIn"
                )

            token_json = token_response.json()
            access_token = token_json.get("access_token")

            if not access_token:
                print("DEBUG: No access token in LinkedIn response")
                raise HTTPException(
                    status_code=400, detail="No access token in response"
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
                print(f"DEBUG: LinkedIn user info error: {user_response.text}")
                raise HTTPException(
                    status_code=400, detail="Failed to get user info from LinkedIn"
                )

            user_info = user_response.json()

            # Get email address
            email_response = requests.get(
                "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                headers=headers,
            )
            if email_response.status_code != 200:
                print(f"DEBUG: LinkedIn email error: {email_response.text}")
                raise HTTPException(
                    status_code=400, detail="Failed to get email from LinkedIn"
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
                raise HTTPException(
                    status_code=400, detail="Could not get email from LinkedIn"
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
            print(f"DEBUG: LinkedIn user query result: {user}")

            if not user:
                print(f"DEBUG: Creating new user for LinkedIn email: {email}")
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
                        user_type=models.UserType.client,  # Default to client
                        is_active=True,
                        terms_accepted=True,  # Assume terms accepted for OAuth
                    )
                    db.add(new_user)
                    db.commit()
                    db.refresh(new_user)
                    user = new_user

                    # Create a client profile
                    client_profile = models.ClientProfile(
                        user_id=user.id,
                    )
                    db.add(client_profile)
                    db.commit()
                except Exception as e:
                    print(f"DEBUG: Error creating LinkedIn user: {str(e)}")
                    db.rollback()
                    raise HTTPException(
                        status_code=500, detail=f"Error creating user account: {str(e)}"
                    )

            # Verify user has an id before creating token
            if not hasattr(user, "id") or user.id is None:
                print(f"DEBUG: LinkedIn user missing id: {user}")
                raise HTTPException(
                    status_code=500, detail="User account is missing ID"
                )

            # Create access token
            access_token = oauth2.create_access_token(data={"sub": str(user.id)})

            # Redirect to frontend with token
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            redirect_url = (
                f"{frontend_url}/oauth-success?token={access_token}&provider=linkedin"
            )
            return RedirectResponse(url=redirect_url)

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {provider}",
            )

    except HTTPException as http_exc:
        print(f"DEBUG: HTTP Exception in {provider} OAuth: {http_exc.detail}")
        raise http_exc

    except Exception as e:
        print(f"DEBUG: Exception in {provider} OAuth: {str(e)}")
        raise HTTPException(
            status_code=400, detail=f"OAuth authentication failed: {str(e)}"
        )

from fastapi import APIRouter, Depends, HTTPException, Request, status
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from jose import jwt
import os
import uuid  # For generating unique state
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
    oauth_client = oauth.create_client(provider)

    received_state = request.query_params.get("state")
    stored_state = request.session.get("oauth_state", None)

    print(f"DEBUG: Received state: {received_state}, Stored state: {stored_state}")

    if received_state != stored_state:
        raise HTTPException(
            status_code=400, detail="CSRF Warning! State mismatch detected."
        )

    try:
        token = await oauth_client.authorize_access_token(request)
        print("DEBUG: Received token:", token)  # 🔹 Debug OAuth Token
    except Exception as e:
        print("OAuth Error:", e)
        raise HTTPException(status_code=400, detail="OAuth authentication failed")

    # Fetch user info
    user_info = {}

    try:
        if provider == "google":
            user_info = await oauth_client.parse_id_token(request, token)
            print("DEBUG: Google User Info:", user_info)

        elif provider == "github":
            user_info = await oauth_client.get(
                "https://api.github.com/user", token=token
            )
            emails = await oauth_client.get(
                "https://api.github.com/user/emails", token=token
            )

            if user_info.status_code != 200 or emails.status_code != 200:
                raise HTTPException(
                    status_code=400, detail="Error retrieving GitHub user info"
                )

            user_info = user_info.json()
            emails = emails.json()

            # Find the primary verified email
            primary_email = next(
                (
                    email["email"]
                    for email in emails
                    if email["primary"] and email["verified"]
                ),
                None,
            )
            if primary_email:
                user_info["email"] = primary_email
            else:
                raise HTTPException(
                    status_code=400, detail="No verified email found for GitHub account"
                )

            print("DEBUG: GitHub User Info:", user_info)

        elif provider == "linkedin":
            user_info_response = await oauth_client.get(
                "https://api.linkedin.com/v2/me", token=token
            )
            user_email_response = await oauth_client.get(
                "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                token=token,
            )

            if (
                user_info_response.status_code != 200
                or user_email_response.status_code != 200
            ):
                raise HTTPException(
                    status_code=400, detail="Error retrieving LinkedIn user info"
                )

            user_info = user_info_response.json()
            user_email = user_email_response.json()

            # Extract email
            if "elements" in user_email and user_email["elements"]:
                user_info["email"] = user_email["elements"][0]["handle~"][
                    "emailAddress"
                ]
            else:
                raise HTTPException(
                    status_code=400, detail="No email found for LinkedIn account"
                )

            print("DEBUG: LinkedIn User Info:", user_info)

    except Exception as e:
        print(f"DEBUG: OAuth Error ({provider}):", str(e))
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")

    # Extract email and full name
    email = user_info.get("email", user_info.get("emailAddress", ""))
    full_name = user_info.get("name", user_info.get("localizedFirstName", ""))

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to retrieve email from OAuth provider",
        )

    # Check if user exists
    existing_user = db.query(models.User).filter(models.User.email == email).first()

    if not existing_user:
        print(f"DEBUG: Creating new user: {email}")  # 🔹 Debug New User
        new_user = models.User(
            username=email.split("@")[0],
            email=email,
            full_name=full_name,
            password=None,
            user_type="client",
            is_active=True,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        existing_user = new_user
    else:
        print(
            f"DEBUG: User already exists: {existing_user.email}"
        )  # 🔹 Debug Existing User

    # Create JWT token
    access_token = oauth2.create_access_token(data={"sub": str(existing_user.id)})

    return {"access_token": access_token, "token_type": "bearer", "user": existing_user}

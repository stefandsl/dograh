from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from api.constants import (
    ENVIRONMENT,
    PASSWORD_RESET_TOKEN_EXPIRY_MINUTES,
    UI_APP_URL,
)
from api.db import db_client
from api.db.models import UserModel
from api.enums import Environment, PostHogEvent
from api.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    UserResponse,
)
from api.services.auth.depends import create_user_configuration_with_mps_key, get_user
from api.services.email import build_password_reset_email, is_smtp_configured, send_email
from api.services.posthog_client import capture_event
from api.utils.auth import (
    create_jwt_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    # Check if email is already taken
    existing_user = await db_client.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Hash password and create user
    hashed = hash_password(request.password)
    user = await db_client.create_user_with_email(
        email=request.email,
        password_hash=hashed,
        name=request.name,
    )

    # Create organization for the user
    org_provider_id = f"org_{user.provider_id}"
    organization, _ = await db_client.get_or_create_organization_by_provider_id(
        org_provider_id=org_provider_id, user_id=user.id
    )

    # Link user to organization
    await db_client.add_user_to_organization(user.id, organization.id)
    await db_client.update_user_selected_organization(user.id, organization.id)

    # Create default service configuration
    try:
        mps_config = await create_user_configuration_with_mps_key(
            user.id, organization.id, user.provider_id
        )
        if mps_config:
            await db_client.update_user_configuration(user.id, mps_config)
    except Exception:
        logger.warning(
            "Failed to create default configuration for OSS user", exc_info=True
        )

    # Create JWT token
    token = create_jwt_token(user.id, request.email)

    capture_event(
        distinct_id=str(user.provider_id),
        event=PostHogEvent.SIGNED_UP,
        properties={
            "organization_id": organization.id,
            "auth_provider": "local",
        },
    )

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=request.name,
            organization_id=organization.id,
            provider_id=user.provider_id,
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    # Look up user by email
    user = await db_client.get_user_by_email(request.email)
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create JWT token
    token = create_jwt_token(user.id, user.email)

    capture_event(
        distinct_id=str(user.provider_id),
        event=PostHogEvent.SIGNED_IN,
        properties={
            "organization_id": user.selected_organization_id,
            "auth_provider": "local",
        },
    )

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            organization_id=user.selected_organization_id,
            provider_id=user.provider_id,
        ),
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest):
    # Always respond identically whether or not the email exists, so the
    # endpoint can't be used to enumerate registered accounts.
    generic_message = (
        "If an account exists for that email, a password reset link has been sent."
    )

    user = await db_client.get_user_by_email(request.email)
    # Only local accounts (those with a password) can reset a password here.
    if not user or not user.password_hash:
        return MessageResponse(message=generic_message)

    raw_token, token_hash = generate_reset_token()
    expires_at = datetime.now(UTC) + timedelta(
        minutes=PASSWORD_RESET_TOKEN_EXPIRY_MINUTES
    )
    await db_client.create_password_reset_token(
        user_id=user.id, token_hash=token_hash, expires_at=expires_at
    )

    reset_url = f"{UI_APP_URL.rstrip('/')}/auth/reset-password?token={raw_token}"
    text_body, html_body = build_password_reset_email(
        reset_url, PASSWORD_RESET_TOKEN_EXPIRY_MINUTES
    )

    # Result intentionally ignored — surfacing send failures would leak account
    # existence and the user can simply request another link.
    await send_email(
        to_email=user.email,
        subject="Reset your Dograh password",
        text_body=text_body,
        html_body=html_body,
    )

    response = MessageResponse(message=generic_message)
    # Outside production, when no mail server is configured, hand the link back
    # directly so self-hosters aren't locked out. Never do this in production.
    if not is_smtp_configured() and ENVIRONMENT != Environment.PRODUCTION.value:
        response.reset_url = reset_url
        logger.info("Password reset link for {email}: {url}", email=user.email, url=reset_url)

    return response


@router.post("/reset-password", response_model=AuthResponse)
async def reset_password(request: ResetPasswordRequest):
    token_hash = hash_reset_token(request.token)
    token = await db_client.get_valid_password_reset_token(token_hash)
    if not token:
        raise HTTPException(
            status_code=400, detail="Invalid or expired reset token"
        )

    user = await db_client.get_user_by_id(token.user_id)
    if not user:
        raise HTTPException(
            status_code=400, detail="Invalid or expired reset token"
        )

    # Update password and spend the token (single use).
    await db_client.update_user_password(user.id, hash_password(request.password))
    await db_client.mark_password_reset_token_used(token.id)

    # Sign the user in so they land authenticated, mirroring login/signup.
    jwt_token = create_jwt_token(user.id, user.email)

    return AuthResponse(
        token=jwt_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            organization_id=user.selected_organization_id,
            provider_id=user.provider_id,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(user: UserModel = Depends(get_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        organization_id=user.selected_organization_id,
        provider_id=user.provider_id,
    )

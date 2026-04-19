"""
Auth routes — Login, logout, current user, user management (admin only).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth import (
    create_access_token,
    create_user,
    get_current_user,
    get_user_by_email,
    hash_password,
    require_roles,
    verify_password,
)
from app.core.db import get_session
from app.models.auth import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    active: bool
    created_at: datetime


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.reception


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    active: bool | None = None
    password: str | None = None


def _user_response(u: User) -> UserResponse:
    return UserResponse(
        id=str(u.id),
        email=u.email,
        full_name=u.full_name,
        role=u.role.value,
        active=u.active,
        created_at=u.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Authenticate with email + password. Returns JWT Bearer token.
    Front-end: store token in localStorage/httpOnly cookie and send as
    Authorization: Bearer <token> on subsequent requests.
    """
    user = await get_user_by_email(session, form.username)
    if not user or not user.active or not verify_password(form.password, user.hashed_password):
        logger.warning(
            "[AUTH] login_failed email='%s' reason=%s",
            form.username,
            "user_not_found" if not user else "wrong_password_or_inactive",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last_login_at
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(user)
    await session.commit()

    token = create_access_token(user)
    logger.info(
        "[AUTH] login_success user_id='%s' email='%s' role='%s'",
        str(user.id), user.email, user.role.value,
    )

    return TokenResponse(
        access_token=token,
        role=user.role.value,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Return the currently authenticated user's profile."""
    return _user_response(current_user)


@router.post("/logout")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Logout — stateless JWT, so client should discard the token.
    This endpoint exists for audit logging purposes.
    """
    logger.info("[AUTH] logout user_id='%s' email='%s'", str(current_user.id), current_user.email)
    return {"message": "Logout realizado com sucesso"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Issue a fresh access token, extending the session.
    Called by the frontend on each authenticated interaction to keep the session alive.
    """
    logger.info("[AUTH] refresh user_id='%s' email='%s'", str(current_user.id), current_user.email)
    token = create_access_token(current_user)
    return TokenResponse(
        access_token=token,
        role=current_user.role.value,
        full_name=current_user.full_name,
    )


# ── User management (admin only) ──────────────────────────────────────────────

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """List all users. Admin only."""
    result = await session.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [_user_response(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_new_user(
    body: CreateUserRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Create a new user. Admin only."""
    existing = await get_user_by_email(session, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    user = await create_user(
        session,
        email=body.email,
        full_name=body.full_name,
        plain_password=body.password,
        role=body.role,
    )
    logger.info(
        "[AUTH] user_created_by_admin actor='%s' new_user='%s' role='%s'",
        current_user.email, user.email, user.role.value,
    )
    return _user_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Update user fields. Admin only."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.active is not None:
        user.active = body.active
    if body.password:
        user.hashed_password = hash_password(body.password)

    user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(
        "[AUTH] user_updated actor='%s' target='%s'",
        current_user.email, user.email,
    )
    return _user_response(user)

"""
Auth core — JWT generation/validation and FastAPI dependency injection.

Usage:
    from app.core.auth import get_current_user, require_roles
    from app.models.auth import UserRole

    # Any authenticated user
    @router.get("/resource")
    async def endpoint(current_user: User = Depends(get_current_user)):
        ...

    # Role-restricted
    @router.delete("/resource")
    async def delete(current_user: User = Depends(require_roles(UserRole.admin))):
        ...
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.db import get_session
from app.models.auth import User, UserRole

logger = logging.getLogger(__name__)

# ── Password hashing ──────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


# ── Dependencies ──────────────────────────────────────────────────────────────

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Validate JWT and return the authenticated User. Raises 401 on failure."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado — faça login novamente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exc

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.active:
        raise credentials_exc

    return user


def require_roles(*roles: UserRole):
    """
    Dependency factory: enforce that the authenticated user has one of the given roles.

    Example:
        Depends(require_roles(UserRole.admin, UserRole.manager))
    """
    async def _check(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado — perfil '{current_user.role.value}' não autorizado",
            )
        return current_user

    return _check


# ── User repository helpers (used by auth routes + seed) ─────────────────────

async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    email: str,
    full_name: str,
    plain_password: str,
    role: UserRole = UserRole.reception,
) -> User:
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(plain_password),
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(
        "[AUTH] user_created email='%s' role='%s'",
        email, role.value,
    )
    return user


async def seed_default_admin(session: AsyncSession) -> None:
    """
    Create the default admin user on first startup if no users exist.
    Credentials come from ADMIN_DEFAULT_EMAIL / ADMIN_DEFAULT_PASSWORD in .env.
    Change via Admin UI after first login.
    """
    result = await session.execute(select(User).limit(1))
    if result.scalar_one_or_none() is not None:
        return  # Users already exist

    user = await create_user(
        session,
        email=settings.admin_default_email,
        full_name="Administrador",
        plain_password=settings.admin_default_password,
        role=UserRole.admin,
    )
    logger.warning(
        "[AUTH] seed_admin: default admin user created email='%s' — "
        "CHANGE PASSWORD VIA ADMIN UI IMMEDIATELY",
        user.email,
    )

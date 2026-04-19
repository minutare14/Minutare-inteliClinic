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
from sqlalchemy import text
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


def _get_jwt_secret() -> str:
    """Return jwt_secret_key, falling back to app_secret_key if empty."""
    key = settings.jwt_secret_key
    if key:
        return key
    return settings.app_secret_key


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
        _get_jwt_secret(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        _get_jwt_secret(),
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
    Idempotent admin bootstrap based on ADMIN_DEFAULT_EMAIL / ADMIN_DEFAULT_PASSWORD.

    Uses raw SQL to avoid SQLAlchemy ORM type-coercion issues when the User.role
    enum (UserRole) is mapped to a VARCHAR column in PostgreSQL.

    Strategy:
      1. Look up the user by ADMIN_DEFAULT_EMAIL (raw SQL).
      2. If found with role='admin' → sync password (and email if ADMIN_SYNC=true).
         If found with role≠'admin' → log warning, skip.
      3. If not found and any admin exists → log warning, skip (unless ADMIN_SYNC=true).
      4. If no admin exists → create the configured admin.

    Rules:
      - Changing ADMIN_DEFAULT_PASSWORD always syncs (password updated on every startup).
      - Changing ADMIN_DEFAULT_EMAIL only takes effect when no admin exists yet.
      - ADMIN_SYNC=true forces replacement of an existing admin with different email.
    """
    import uuid as _uuid

    target_email = settings.admin_default_email
    target_password = settings.admin_default_password
    sync = getattr(settings, "admin_sync", False)

    # ── Raw SQL helpers (bypass ORM UserRole enum type coercion) ──────────────
    async def _fetchone(sql_str: str, params: dict | None = None) -> dict | None:
        result = await session.execute(text(sql_str), params or {})
        row = result.fetchone()
        if row is None:
            return None
        return {k: v for k, v in zip(result.keys(), row)}

    async def _exec(sql_str: str, params: dict | None = None) -> None:
        await session.execute(text(sql_str), params or {})
        await session.commit()

    # ── Case 1: configured email exists ──────────────────────────────────────
    row = await _fetchone(
        "SELECT id, email, role, hashed_password FROM users WHERE email = :email",
        {"email": target_email},
    )

    if row is not None:
        if row["role"] == "admin":
            new_hash = hash_password(target_password)
            if sync or row["hashed_password"] != new_hash:
                await _exec(
                    "UPDATE users SET hashed_password = :pw, email = :email WHERE id = :id",
                    {"pw": new_hash, "email": target_email, "id": str(row["id"])},
                )
                logger.warning(
                    "[AUTH] seed_admin: password updated for existing admin '%s' (sync=%s)",
                    target_email, sync,
                )
            else:
                logger.info(
                    "[AUTH] seed_admin: admin '%s' already exists with correct password — skipping",
                    target_email,
                )
        else:
            logger.warning(
                "[AUTH] seed_admin: email '%s' is taken by a non-admin user (role='%s') — "
                "skipping. Set ADMIN_SYNC=true to override or change ADMIN_DEFAULT_EMAIL.",
                target_email, row["role"],
            )
        return

    # ── Case 2: configured email not found — check for existing admin ─────────
    existing_admin = await _fetchone(
        "SELECT id, email FROM users WHERE role = 'admin' LIMIT 1",
    )

    if existing_admin is not None:
        if sync:
            logger.warning(
                "[AUTH] seed_admin: ADMIN_SYNC=true — removing old admin '%s' and creating new one",
                existing_admin["email"],
            )
            await _exec("DELETE FROM users WHERE id = :id", {"id": str(existing_admin["id"])})
        else:
            logger.warning(
                "[AUTH] seed_admin: admin with different email already exists ('%s'). "
                "ADMIN_DEFAULT_EMAIL='%s' — skipping. "
                "Set ADMIN_SYNC=true to replace the existing admin, "
                "or update the user directly in the DB.",
                existing_admin["email"], target_email,
            )
            return

    # ── Case 3: no admin exists — create configured admin ────────────────────
    new_hash = hash_password(target_password)
    await _exec(
        "INSERT INTO users (id, email, full_name, hashed_password, role, active, created_at, updated_at) "
        "VALUES (:id, :email, :full_name, :pw, 'admin', true, NOW(), NOW())",
        {
            "id": str(_uuid.uuid4()),
            "email": target_email,
            "full_name": "Administrador",
            "pw": new_hash,
        },
    )
    logger.warning(
        "[AUTH] seed_admin: admin created email='%s' (sync=%s) — "
        "change password via Admin UI after first login",
        target_email, sync,
    )

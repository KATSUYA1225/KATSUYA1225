"""JWT認証 — SQLiteユーザー管理 + bcryptパスワード"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

SECRET_KEY = os.environ.get("SECRET_KEY", "ai-kigyo-os-default-secret-change-in-prod-32chars")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user_id: str, email: str, plan: str) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": user_id, "email": email, "plan": plan, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def new_user_id() -> str:
    return str(uuid.uuid4())

"""Password hashing and token helpers (used across panels and streams)."""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_token(data: dict, expires_minutes: int = 60 * 24) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        return None


def create_stream_token(source_id: int, expires_minutes: int = 240) -> str:
    payload = {
        "sid": source_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.STREAM_TOKEN_SECRET, algorithm=_ALGORITHM)


def decode_stream_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.STREAM_TOKEN_SECRET, algorithms=[_ALGORITHM])
    except JWTError:
        return None

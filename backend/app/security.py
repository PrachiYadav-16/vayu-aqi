import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

ALGO = "HS256"
_DEFAULT_SECRET = "change-me-in-production"
_runtime_secret: str | None = None
log = logging.getLogger(__name__)


def _secret() -> str:
    """The configured JWT secret. A server that is not on local SQLite must never sign
    tokens with the public default: fall back to a random per-process secret (users
    are signed out on restart) and log loudly so the operator sets VAYU_JWT_SECRET."""
    global _runtime_secret
    s = get_settings()
    if s.jwt_secret != _DEFAULT_SECRET or s.database_url.startswith("sqlite"):
        return s.jwt_secret
    if _runtime_secret is None:
        _runtime_secret = secrets.token_urlsafe(48)
        log.error("VAYU_JWT_SECRET is not set; using a temporary random secret")
    return _runtime_secret


class Throttle:
    """In-memory sliding-window limiter. Enough for a single instance; use Redis if
    the API ever runs on several machines."""

    def __init__(self, limit: int, window_s: int) -> None:
        self.limit, self.window = limit, window_s
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                retry = int(self.window - (now - q[0])) + 1
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                    f"Too many attempts. Try again in {max(1, retry // 60)} min.",
                                    headers={"Retry-After": str(retry)})
            q.append(now)
            if len(self.hits) > 10000:  # keep memory bounded
                self.hits.pop(next(iter(self.hits)))

    def reset(self, key: str) -> None:
        with self.lock:
            self.hits.pop(key, None)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, _secret(), algorithm=ALGO)


def current_user(token: str | None = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue",
                        headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise err
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGO])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise err
    user = db.get(User, uid)
    if user is None:
        raise err
    return user

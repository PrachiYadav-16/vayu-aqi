from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import RegisterIn, TokenOut
from app.security import Throttle, client_ip, create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
# Failed sign-ins per account, and sign-ups per network address.
login_failures = Throttle(limit=8, window_s=15 * 60)
signups = Throttle(limit=10, window_s=60 * 60)


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    signups.check(client_ip(request))
    email = body.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password),
                sensitivity=body.sensitivity, language=body.language)
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_token(user.id))


@router.post("/token", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    key = form.username.lower().strip()
    login_failures.check(key)  # raises 429 after too many recent failures
    user = db.scalar(select(User).where(func.lower(User.email) == key))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    login_failures.reset(key)
    return TokenOut(access_token=create_token(user.id))

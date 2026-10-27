from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import RegisterIn, TokenOut
from app.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
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
    user = db.scalar(select(User).where(func.lower(User.email) == form.username.lower()))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    return TokenOut(access_token=create_token(user.id))

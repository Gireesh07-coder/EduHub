import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_SECURE,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database import get_db
from models import LoginAttempt, User
from schemas import ChangePassword, PasswordReset, PasswordResetRequest, UserCreate, UserLogin, UserPublic, UserUpdate

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(name=payload.name, email=email, hashed_password=hash_password(payload.password), email_verified=False)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
    db.refresh(user)
    response.set_cookie(
        "eduhub_token",
        create_access_token(user.id),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return user


@router.post("/auth/login", response_model=UserPublic)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    count = db.scalar(
        select(func.count(LoginAttempt.id)).where(LoginAttempt.email == email, LoginAttempt.attempted_at >= cutoff)
    ) or 0
    if count >= 8:
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        db.add(LoginAttempt(email=email))
        db.commit()
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled. Contact support.")
    db.query(LoginAttempt).filter(LoginAttempt.email == email).delete()
    db.commit()
    response.set_cookie(
        "eduhub_token",
        create_access_token(user.id),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return user


@router.post("/auth/forgot-password")
def forgot_password(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        user.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.commit()
        base_url = str(request.base_url).rstrip("/")
        print(f"[EduHub mock password reset] {base_url}/reset-password.html?token={token}")
    return {"message": "If that email belongs to an account, a password reset link has been sent."}


@router.post("/auth/reset-password")
def reset_password(payload: PasswordReset, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    user = db.scalar(select(User).where(User.reset_token_hash == token_hash))
    now = datetime.now(timezone.utc)
    expires = user.reset_token_expires if user else None
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if user is None or expires is None or expires <= now:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired.")
    user.hashed_password = hash_password(payload.password)
    user.reset_token_hash = None
    user.reset_token_expires = None
    db.commit()
    return {"message": "Password updated. You can now log in."}


@router.post("/auth/change-password")
def change_password(
    payload: ChangePassword,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated."}


@router.post("/auth/verify-email")
def verify_email(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.email_verified = True
    db.commit()
    return {"message": "Your email has been marked as verified for this demo."}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("eduhub_token", httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/")
    return {"message": "You have been logged out."}


@router.get("/me", response_model=UserPublic)
def read_me(user: User = Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserPublic)
def update_me(payload: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.name = payload.name
    user.age = payload.age
    user.phone = payload.phone
    db.commit()
    db.refresh(user)
    return user

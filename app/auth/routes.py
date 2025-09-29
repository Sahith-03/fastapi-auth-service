# app/auth/routes.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import Token,TokenPayload,UserResponse,UserCreate
from app.core import security
from jose import JWTError
from app.redis_client import redis_client
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from app.utils.email import send_email
from app.services.password_reset import create_reset_token, verify_reset_token, delete_reset_token


router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

@router.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1) Find user by email (OAuth2 form uses "username" field)
    user = db.query(User).filter(User.email == form_data.username).first()
    # 2) Check credentials
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 3) Create tokens
    access_token = security.create_access_token({"sub": str(user.id), "email": user.email})
    refresh_token = security.create_refresh_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = security.decode_token(token)
    if not payload or payload.get("scope") != "access":
        raise credentials_exception

    jti = payload.get("jti")
    if not jti:
        raise credentials_exception

    # 🔍 Check Redis for revoked token
    if redis_client.get(f"revoked:{jti}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise credentials_exception

    return user

@router.get("/me")
def read_own_profile(current_user: User = Depends(get_current_user)):
    # returns the ORM object - FastAPI will serialize using pydantic (if response_model used)
    return {"id": current_user.id, "email": current_user.email}

@router.post("/refresh", response_model=Token)
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = security.decode_token(refresh_token)
        if payload.get("scope") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_access_token = security.create_access_token({"sub": str(user.id), "email": user.email})
    return {
        "access_token": new_access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme)
):
    payload = security.decode_token(token)
    if not payload or payload.get("scope") != "access":
        raise HTTPException(status_code=400, detail="Invalid token")

    jti = payload.get("jti")
    exp = payload.get("exp")

    if not jti or not exp:
        raise HTTPException(status_code=400, detail="Token missing jti or exp")

    # Calculate TTL (time until token expires)
    ttl = max(exp - security.get_current_timestamp(), 0)

    # 🚫 Store revoked token in Redis with expiration
    redis_client.setex(f"revoked:{jti}", ttl, "true")

    return {"message": "Successfully logged out"}


@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    # check if user already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # create user
    hashed_pw = security.get_password_hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_pw,username=user.username)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/revoked-tokens")
def list_revoked_tokens():
    keys = redis_client.keys("revoked:*")
    return {"revoked_tokens": [key.encode().decode() for key in keys]}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def update_user_password(db: Session, user_id: int, hashed_pw: str):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.hashed_password = hashed_pw
        db.commit()
        db.refresh(user)
    return user

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = await create_reset_token(user.id)
    reset_link = f"http://localhost:3000/reset-password?token={token}"
    await send_email(
        to=user.email,
        subject="Password Reset",
        body=f"Click here to reset your password: {reset_link}"
    )
    return {"message": "Password reset link sent"}

@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user_id = await verify_reset_token(data.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    hashed_pw = security.get_password_hash(data.new_password)
    update_user_password(db, user_id, hashed_pw)

    await delete_reset_token(data.token)
    return {"message": "Password reset successful"}
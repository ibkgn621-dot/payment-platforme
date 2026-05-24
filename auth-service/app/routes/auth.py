from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import models, schemas
from ..database import get_db
from ..config import settings
from ..dependencies import redis_client, oauth2_scheme, get_current_active_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
limiter = Limiter(key_func=get_remote_address)


# ─────────────────────────────────────────────
# Helpers JWT
# ─────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@router.post("/register", response_model=schemas.UserResponse, status_code=201)
@limiter.limit("5/minute")           # FIX 3 : anti-spam inscription
def register(request: Request, user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    if user_data.phone and db.query(models.User).filter(models.User.phone == user_data.phone).first():
        raise HTTPException(status_code=400, detail="Téléphone déjà utilisé")

    user = models.User(
        email=user_data.email,
        phone=user_data.phone,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        hashed_password=hash_password(user_data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/minute")           # FIX 3 : anti-brute-force
def login(request: Request, user_data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Compte désactivé")

    access_token = create_access_token(
        {"sub": str(user.id), "role": user.role, "email": user.email}
    )
    refresh_token = create_refresh_token({"sub": str(user.id), "role": user.role})

    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(models.Session(user_id=user.id, refresh_token=refresh_token, expires_at=expires_at))
    db.commit()

    return schemas.Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=schemas.Token)
def refresh_token(request: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(
            request.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token invalide")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh token invalide")

    session = db.query(models.Session).filter(
        models.Session.refresh_token == request.refresh_token,
        models.Session.is_active == True,
    ).first()
    if not session:
        raise HTTPException(status_code=401, detail="Session expirée")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")

    # Rotation du refresh token
    session.is_active = False
    db.commit()

    access_token = create_access_token(
        {"sub": str(user.id), "role": user.role, "email": user.email}
    )
    new_refresh = create_refresh_token({"sub": str(user.id), "role": user.role})
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(models.Session(user_id=user.id, refresh_token=new_refresh, expires_at=expires_at))
    db.commit()

    return schemas.Token(access_token=access_token, refresh_token=new_refresh)


@router.post("/logout")
def logout(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp", 0)
        ttl = max(0, exp - int(datetime.utcnow().timestamp()))
        redis_client.setex(f"blacklist:{token}", ttl, "1")
    except JWTError:
        pass
    return {"message": "Déconnexion réussie"}


@router.post("/verify", response_model=schemas.VerifyTokenResponse)
def verify_token(request: schemas.VerifyTokenRequest):
    if redis_client.get(f"blacklist:{request.token}"):
        return schemas.VerifyTokenResponse(valid=False)
    try:
        payload = jwt.decode(
            request.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return schemas.VerifyTokenResponse(
            valid=True,
            user_id=payload.get("sub"),
            role=payload.get("role"),
            email=payload.get("email"),
        )
    except JWTError:
        return schemas.VerifyTokenResponse(valid=False)


@router.post("/change-password")
def change_password(
    request: schemas.ChangePasswordRequest,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    current_user.hashed_password = hash_password(request.new_password)
    db.commit()
    return {"message": "Mot de passe modifié avec succès"}

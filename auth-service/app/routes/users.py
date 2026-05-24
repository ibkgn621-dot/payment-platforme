from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_active_user, require_admin

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_active_user)):
    return current_user

@router.get("/", response_model=List[schemas.UserResponse])
def list_users(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin)
):
    return db.query(models.User).offset(skip).limit(limit).all()

@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return user

@router.patch("/{user_id}/activate")
def activate_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_active = True
    db.commit()
    return {"message": "Utilisateur activé"}

@router.delete("/{user_id}")
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_active = False
    db.commit()
    return {"message": "Utilisateur désactivé"}

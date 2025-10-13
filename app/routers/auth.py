"""Authentication endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional

from app.database import get_db
from app.auth import (
    verify_password, get_password_hash, create_access_token, 
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.models import User, Clinic
from pydantic import BaseModel, EmailStr

router = APIRouter(
    #prefix="/auth",
    tags=["authentication"]
)

# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    clinic_id: str
    clinic_name: str
    specialties: Optional[list] = []

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str
    clinic_id: str
    specialties: Optional[list] = []

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Authenticate user and return JWT token"""
    # Find user by email
    user = db.query(User).filter(
        User.email == form_data.username,
        User.is_active == True
    ).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get clinic info
    clinic = db.query(Clinic).filter(Clinic.id == user.clinic_id).first()
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "clinic_id": user.clinic_id
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "clinic_id": user.clinic_id,
            "clinic_name": clinic.name if clinic else "Unknown",
            "specialties": user.specialties or []
        }
    }

@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Register new user (admin only)"""
    # Only admins can register new users
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can register new users"
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate clinic exists
    clinic = db.query(Clinic).filter(Clinic.id == user_data.clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid clinic ID"
        )
    
    # Validate role
    valid_roles = ["doctor", "helper", "admin", "billing"]
    if user_data.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {valid_roles}"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role,
        clinic_id=user_data.clinic_id,
        specialties=user_data.specialties
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        role=new_user.role,
        clinic_id=new_user.clinic_id,
        clinic_name=clinic.name,
        specialties=new_user.specialties or []
    )

@router.post("/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    # Verify current password
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}

@router.get("/me")
async def get_current_user_info(db: Session = Depends(get_db)):
    """Get current authenticated user info"""
    # Get demo doctor for MVP
    user = db.query(User).filter(User.email == "doctor@reconomed.ro").first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "specialties": user.specialties or ["internal_medicine", "cardiology", "respiratory", "gynecology"],
        "clinic_id": user.clinic_id
    }
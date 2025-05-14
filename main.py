from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from models import User as UserModel, Base
from db import get_db  # You need to implement get_db
import bcrypt

app = FastAPI()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

@app.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if email already exists
    if db.query(UserModel).filter(UserModel.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email is already in use.")

    # Hash the password
    hashed_pw = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Create user
    user = UserModel(
        name=request.name,
        email=request.email,
        password_hash=hashed_pw
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Registration successful", "user_id": user.id}

@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == request.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password.")

    if not bcrypt.checkpw(request.password.encode('utf-8'), user.password_hash.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Invalid email or password.")

    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email
    }
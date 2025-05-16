from fastapi import FastAPI, HTTPException, UploadFile, Depends, File, Form
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from models import User as UserModel, Base
from db import get_db
import bcrypt
from datetime import datetime
import base64
import cv2
import numpy as np
import face_recognition_models
import face_recognition
from models import AttendanceLog
import site
import os

app = FastAPI()


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    email: EmailStr | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


@app.post("/register", status_code=201)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(UserModel).filter(UserModel.email == request.email).first():
        raise HTTPException(status_code=400, detail="Email is already in use.")

    hashed_pw = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    current_year = datetime.now().year

    last_user = db.query(UserModel).filter(
        UserModel.student_number.like(f'{current_year}-AAAAA%')
    ).order_by(UserModel.student_number.desc()).first()

    if last_user and last_user.student_number:
        last_num = int(last_user.student_number.split('-')[1][5:])
        new_num = last_num + 1
    else:
        new_num = 1

    student_number = f"{current_year}-AAAAA{new_num:05d}"

    user = UserModel(
        name=request.name,
        email=request.email,
        password_hash=hashed_pw,
        role="Student",
        student_number=student_number,
        face_image=None  # No image on registration
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "student_number": user.student_number,
        "face_image": None  # No image at registration
    }

@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == request.email).first()
    if not user or not bcrypt.checkpw(request.password.encode('utf-8'), user.password_hash.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Invalid email or password.")

    # Encode face_image as base64 if it exists
    face_image_b64 = (
        base64.b64encode(user.face_image).decode("utf-8") if user.face_image else None
    )

    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "student_number": user.student_number,
        "face_image": face_image_b64  # Now safe for JSON
    }

@app.put("/profile/{user_id}")
async def update_profile(
    user_id: int,
    name: str = Form(...),
    email: EmailStr = Form(...),
    face_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Check for duplicate email
    if db.query(UserModel).filter(UserModel.email == email, UserModel.id != user_id).first():
        raise HTTPException(status_code=400, detail="Email is already in use.")

    user.name = name
    user.email = email

    if face_image is not None:
        user.face_image = await face_image.read()

    db.commit()
    db.refresh(user)

    # Encode face_image as base64 if it exists
    face_image_b64 = (
        base64.b64encode(user.face_image).decode("utf-8") if user.face_image else None
    )

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "student_number": user.student_number,
        "face_image": face_image_b64  # Now safe for JSON
    }


@app.post("/validate_face/{user_id}")
async def validate_face(
    user_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if not user.face_image:
            raise HTTPException(status_code=400, detail="User doesn't have a registered face image.")
        
        # Read uploaded image
        uploaded_bytes = await image.read()
        print(f"Uploaded image size: {len(uploaded_bytes)} bytes")
        
        # Convert to OpenCV format
        try:
            uploaded_np = np.frombuffer(uploaded_bytes, np.uint8)
            uploaded_img = cv2.imdecode(uploaded_np, cv2.IMREAD_COLOR)
            if uploaded_img is None:
                raise HTTPException(status_code=400, detail="Could not decode uploaded image.")
        except Exception as e:
            print(f"Error decoding uploaded image: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error processing uploaded image: {str(e)}")
        
        # Convert stored image
        try:
            stored_np = np.frombuffer(user.face_image, np.uint8)
            stored_img = cv2.imdecode(stored_np, cv2.IMREAD_COLOR)
            if stored_img is None:
                raise HTTPException(status_code=400, detail="Could not decode stored user image.")
        except Exception as e:
            print(f"Error decoding stored image: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing stored face image: {str(e)}")
        
        print("Getting face encodings...")
        # Get face encodings with error handling
        try:
            uploaded_encodings = face_recognition.face_encodings(uploaded_img)
            if not uploaded_encodings:
                raise HTTPException(status_code=400, detail="No face detected in uploaded image.")
                
            stored_encodings = face_recognition.face_encodings(stored_img)
            if not stored_encodings:
                raise HTTPException(status_code=400, detail="No face detected in stored image.")
        except Exception as e:
            print(f"Error in face encoding: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Face recognition error: {str(e)}")
        
        print("Comparing faces...")
        # Compare faces
        match = face_recognition.compare_faces([stored_encodings[0]], uploaded_encodings[0])[0]
        
        if match:
            print("Face match successful!")
            # Save to attendance_logs
            log = AttendanceLog(
                user_id=user.id,
                date=datetime.now(),
                status="Present",
                image=uploaded_bytes
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            return {
                "message": "Face validated and attendance logged.",
                "attendance_id": log.id,
                "timestamp": datetime.now().isoformat()
            }
        else:
            print("Face match failed.")
            raise HTTPException(status_code=401, detail="Face does not match.")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
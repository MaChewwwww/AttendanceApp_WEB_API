from fastapi import FastAPI, HTTPException, UploadFile, Depends, File, Form
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from models import User as UserModel, Student as StudentModel, Base
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
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    first_name: str
    middle_name: str | None = None
    last_name: str
    email: EmailStr
    password: str
    student_number: str


@app.post("/register", status_code=201)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    try:
        # Check if email is already in use
        if db.query(UserModel).filter(UserModel.email == request.email).first():
            raise HTTPException(status_code=400, detail="Email is already in use.")
        
        # Check if student number is already in use
        if db.query(StudentModel).filter(StudentModel.student_number == request.student_number).first():
            raise HTTPException(status_code=400, detail="Student number is already in use.")

        # Hash the password
        hashed_pw = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Create the user
        user = UserModel(
            first_name=request.first_name,
            middle_name=request.middle_name,
            last_name=request.last_name,
            email=request.email,
            password_hash=hashed_pw,
            role="Student",
            face_image=None,  
            status="pending"
        )
        db.add(user)
        db.flush()  # Flush to get the user ID before committing

        # Create the student record without section
        student = StudentModel(
            user_id=user.id,
            student_number=request.student_number,
            # Don't set section at all
        )
        db.add(student)
        
        # Commit both records
        db.commit()
        db.refresh(user)

        return {
            "user_id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "role": user.role,
            "student_number": student.student_number,
            "status": user.status
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error during registration: {str(e)}")

@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == request.email).first()
    if not user or not bcrypt.checkpw(request.password.encode('utf-8'), user.password_hash.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Invalid email or password.")
    
    # Check if it's a student login
    student = db.query(StudentModel).filter(StudentModel.user_id == user.id).first()
    if not student:
        raise HTTPException(status_code=403, detail="Only students can log in to this portal.")

    # Encode face_image as base64 if it exists
    face_image_b64 = (
        base64.b64encode(user.face_image).decode("utf-8") if user.face_image else None
    )

    return {
        "user_id": user.id,
        "first_name": user.first_name,
        "middle_name": user.middle_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
        "student_number": student.student_number,
        "face_image": face_image_b64,
        "status": user.status
    }

@app.get("/profile/{user_id}")
def get_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Get student information
    student = db.query(StudentModel).filter(StudentModel.user_id == user_id).first()
    
    # Encode face_image as base64 if it exists
    face_image_b64 = (
        base64.b64encode(user.face_image).decode("utf-8") if user.face_image else None
    )
    
    return {
        "id": user.id,
        "first_name": user.first_name,
        "middle_name": user.middle_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
        "student_number": student.student_number if student else None,
        "profile_image": user.profile_image,
        "face_image": face_image_b64,
        "status": user.status
    }

@app.put("/profile/update/{user_id}")
async def update_profile(
    user_id: int,
    first_name: str = Form(...),
    middle_name: str = Form(None),
    last_name: str = Form(...),
    email: EmailStr = Form(...),
    profile_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Find the user
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Check for duplicate email
    if db.query(UserModel).filter(UserModel.email == email, UserModel.id != user_id).first():
        raise HTTPException(status_code=400, detail="Email is already in use.")

    # Update basic user information
    user.first_name = first_name
    user.middle_name = middle_name
    user.last_name = last_name
    user.email = email

    # Handle profile image upload
    if profile_image is not None:
        # Read the file content
        file_content = await profile_image.read()
        
        # Get file extension
        file_extension = profile_image.filename.split('.')[-1].lower()
        if file_extension not in ['jpg', 'jpeg', 'png', 'gif']:
            raise HTTPException(status_code=400, detail="Only image files (jpg, jpeg, png, gif) are allowed")
        
        # Generate filename using user id and timestamp
        filename = f"profile_{user_id}_{int(datetime.now().timestamp())}.{file_extension}"
        
        # Save to filesystem
        upload_dir = "uploads/profiles"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Store path in database
        user.profile_image = file_path

    # Save changes
    db.commit()
    db.refresh(user)

    # Get student information
    student = db.query(StudentModel).filter(StudentModel.user_id == user_id).first()
    
    return {
        "id": user.id,
        "first_name": user.first_name,
        "middle_name": user.middle_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
        "student_number": student.student_number if student else None,
        "profile_image": user.profile_image,
        "status": user.status
    }

@app.post("/register-face/{user_id}")
async def register_face(
    user_id: int,
    face_image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Read the uploaded image
    face_data = await face_image.read()
    
    # Verify that the image contains a face
    try:
        img_np = np.frombuffer(face_data, np.uint8)
        img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Could not decode image.")
        
        # Check if a face is detected
        face_encodings = face_recognition.face_encodings(img)
        if not face_encodings:
            raise HTTPException(status_code=400, detail="No face detected in the image.")
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing face image: {str(e)}")
    
    # Store the face image
    user.face_image = face_data
    db.commit()
    
    return {
        "message": "Face registered successfully",
        "user_id": user.id
    }


@app.post("/validate_face/{user_id}")
async def validate_face(
    user_id: int,
    course_id: int = Form(...),
    section_id: int = Form(...),
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
                course_id=course_id,
                section_id=section_id,
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
from fastapi import HTTPException
from sqlalchemy.orm import Session
import bcrypt
from datetime import datetime
from pydantic import BaseModel, EmailStr
from models import User as UserModel, Student as StudentModel
from typing import Optional
import base64

class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    student_number: str
    birthday: str  # Format: "YYYY-MM-DD"
    contact_number: str
    middle_name: str | None = None
    face_image: Optional[str] = None  # Base64 encoded image

def register_student(request: RegisterRequest, db: Session):
    try:
        # Hash password and prepare user data
        hashed_pw = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        birthday_date = datetime.strptime(request.birthday, "%Y-%m-%d").date()

        # Decode face image if provided
        face_image_data = None
        if request.face_image:
            try:
                face_image_data = base64.b64decode(request.face_image)
            except Exception as e:
                print(f"Error decoding face image: {e}")
                raise HTTPException(status_code=400, detail="Invalid face image format")

        # Create user record with fields that exist in the model
        # Check if middle_name is an attribute before setting it
        user_data = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "email": request.email,
            "birthday": birthday_date,
            "password_hash": hashed_pw,
            "contact_number": request.contact_number,
            "role": "Student",
            "status_id": 1,
            "face_image": face_image_data,
            "verified": 0,
            "isDeleted": 0
        }
        
        # Optionally add middle_name if it exists in the model
        try:
            # Create a test instance to check attributes
            test_user = UserModel()
            if hasattr(test_user, 'middle_name'):
                user_data["middle_name"] = request.middle_name
        except:
            # If this fails, just continue without middle_name
            pass
        
        # Create the user with validated fields
        user = UserModel(**user_data)
        db.add(user)
        db.flush()

        # Create student record
        student = StudentModel(
            user_id=user.id,
            student_number=request.student_number,
            section=None
        )
        db.add(student)
        db.commit()
        db.refresh(user)

        print(f"✓ New student registered: {user.first_name} {user.last_name} ({user.email})")
        return {
            "user_id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "role": user.role,
            "student_number": student.student_number,
            "verified": user.verified
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error during registration: {str(e)}")
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

def register_student(request: RegisterRequest, db: Session, is_otp_verified: bool = False):
    try:
        # Check if email is already in use
        existing_user = db.query(UserModel).filter(UserModel.email == request.email).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email is already in use")
            
        # Check if student number is already in use
        existing_student = db.query(StudentModel).filter(StudentModel.student_number == request.student_number).first()
        if existing_student:
            raise HTTPException(status_code=409, detail="Student number is already in use")

        # Hash password and prepare user data
        hashed_pw = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        birthday_date = datetime.strptime(request.birthday, "%Y-%m-%d").date()

        # Handle face image - decode base64 to bytes for database storage
        face_image_data = None
        if request.face_image:
            try:
                face_image_data = base64.b64decode(request.face_image)
            except Exception as e:
                print(f"Error decoding face image: {e}")
                raise HTTPException(status_code=400, detail="Invalid face image format")

        # Use default status_id = 1 (assuming this is the default student status)
        default_status_id = 1

        # Create user record with fields that exist in the model
        user_data = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "email": request.email,
            "birthday": birthday_date,
            "password_hash": hashed_pw,
            "contact_number": request.contact_number,
            "role": "Student",
            "status_id": default_status_id,
            "face_image": face_image_data,  # Now properly decoded to bytes
            "verified": 1 if is_otp_verified else 0,  # Set verified=1 if OTP was used
            "isDeleted": 0
        }
        
        # Optionally add middle_name if it exists in the model
        try:
            test_user = UserModel()
            if hasattr(test_user, 'middle_name'):
                user_data["middle_name"] = request.middle_name
        except:
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

        verification_status = "verified" if is_otp_verified else "pending admin approval"
        print(f"Successfully registered user: {user.email} (ID: {user.id}) - {verification_status} with status ID: {default_status_id}")
        
        # Send welcome email after successful registration
        if is_otp_verified:  # Only send welcome email for OTP-verified users
            try:
                from services.email.service import EmailService
                email_service = EmailService()
                success, message = email_service.send_welcome_email(user.email, user.first_name)
                if success:
                    print(f"✅ Welcome email sent to {user.email}")
                else:
                    print(f"⚠️ Warning: Could not send welcome email to {user.email}: {message}")
            except Exception as email_error:
                print(f"⚠️ Warning: Could not send welcome email: {str(email_error)}")
        
        # Return structure that matches the reference implementation
        return {
            "user_id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "role": user.role,
            "student_number": student.student_number
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error during registration: {str(e)}")
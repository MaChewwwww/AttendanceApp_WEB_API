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

class RegistrationValidationRequest(BaseModel):
    """Request model for validating registration fields"""
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    birthday: Optional[str] = ""  # Format: "YYYY-MM-DD"
    contact_number: Optional[str] = ""
    student_number: Optional[str] = ""
    email: Optional[str] = ""  # Changed from EmailStr to str to allow empty values
    password: Optional[str] = ""

class RegistrationValidationResponse(BaseModel):
    """Response model for registration validation"""
    is_valid: bool
    message: str
    errors: Optional[list] = None

def validate_registration_fields(request: RegistrationValidationRequest, db: Session):
    """
    Validate registration fields before proceeding with face capture
    
    Args:
        request: RegistrationValidationRequest with form data
        db: Database session
        
    Returns:
        RegistrationValidationResponse with validation results
    """
    try:
        import re
        from datetime import datetime, date
        
        print(f"=== VALIDATION REQUEST DEBUG ===")
        print(f"Received request from frontend: {request}")
        print(f"Time: {datetime.now().strftime('%I:%M %p')}")
        print("================================")
        
        errors = []
        
        # 1. First name validation
        if not request.first_name or not request.first_name.strip():
            errors.append("First name is required.")
        
        # 2. Last name validation
        if not request.last_name or not request.last_name.strip():
            errors.append("Last name is required.")
        
        # 3. Birthday validation
        if not request.birthday or not request.birthday.strip():
            errors.append("Birthday is required.")
        else:
            try:
                birthday_date = datetime.strptime(request.birthday, "%Y-%m-%d").date()
                today = date.today()
                age = today.year - birthday_date.year - ((today.month, today.day) < (birthday_date.month, birthday_date.day))
                
                if age < 16:
                    errors.append("You must be at least 16 years old to register.")
            except ValueError:
                errors.append("Invalid birthday format. Please use YYYY-MM-DD format.")
        
        # 4. Contact number validation
        if not request.contact_number or not request.contact_number.strip():
            errors.append("Contact number is required.")
        else:
            # Remove any non-digit characters for validation
            clean_contact = re.sub(r'\D', '', request.contact_number)
            if len(clean_contact) != 11:
                errors.append("Contact number must be exactly 11 digits.")
        
        # 5. Student number validation (required and no duplicates)
        if not request.student_number or not request.student_number.strip():
            errors.append("Student number is required.")
        else:
            try:
                existing_student = db.query(StudentModel).filter(StudentModel.student_number == request.student_number).first()
                if existing_student:
                    errors.append("Student number is already in use.")
            except Exception as e:
                print(f"Error checking student number: {e}")
                errors.append("Database error checking student number.")
        
        # 6. Email validation (required, domain check, no duplicates)
        if not request.email or not request.email.strip():
            errors.append("Email is required.")
        else:
            # Basic email format validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, request.email):
                errors.append("Invalid email format.")
            else:
                # Check PUP domain
                if not request.email.endswith("@iskolarngbayan.pup.edu.ph"):
                    errors.append("Email must be a valid PUP email address (@iskolarngbayan.pup.edu.ph).")
                
                # Check for duplicates
                try:
                    existing_user = db.query(UserModel).filter(UserModel.email == request.email).first()
                    if existing_user:
                        errors.append("Email is already in use.")
                except Exception as e:
                    print(f"Error checking email: {e}")
                    errors.append("Database error checking email.")
        
        # 7. Password validation
        if not request.password or not request.password.strip():
            errors.append("Password is required.")
        else:
            password_errors = []
            
            if len(request.password) < 6:
                password_errors.append("at least 6 characters")
            
            if not re.search(r'[a-z]', request.password):
                password_errors.append("at least 1 lowercase letter")
            
            if not re.search(r'[A-Z]', request.password):
                password_errors.append("at least 1 uppercase letter")
            
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', request.password):
                password_errors.append("at least 1 special character")
            
            if password_errors:
                errors.append(f"Password must contain {', '.join(password_errors)}.")
        
        # Return validation result
        if errors:
            print(f"Validation failed with errors: {errors}")
            return RegistrationValidationResponse(
                is_valid=False,
                message="Validation failed",
                errors=errors
            )
        
        print("All fields are valid")
        return RegistrationValidationResponse(
            is_valid=True,
            message="All fields are valid",
            errors=None
        )
        
    except Exception as e:
        print(f"Unexpected error in validation: {e}")
        return RegistrationValidationResponse(
            is_valid=False,
            message=f"Validation failed: {str(e)}",
            errors=[f"Server error: {str(e)}"]
        )

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
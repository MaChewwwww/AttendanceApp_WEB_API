from fastapi import HTTPException
from sqlalchemy.orm import Session
import bcrypt
from datetime import datetime
from pydantic import BaseModel
from models import User as UserModel, Student as StudentModel
from typing import Optional

class LoginValidationRequest(BaseModel):
    """Request model for validating login fields"""
    email: str
    password: str

class LoginValidationResponse(BaseModel):
    """Response model for login validation"""
    is_valid: bool
    message: str
    errors: Optional[list] = None

def validate_login_fields(request: LoginValidationRequest, db: Session):
    """
    Validate login fields format and requirements
    
    Args:
        request: LoginValidationRequest with email and password
        db: Database session for credential validation
        
    Returns:
        LoginValidationResponse with validation results
    """
    try:
        import re
        
        print(f"=== LOGIN VALIDATION REQUEST DEBUG ===")
        print(f"Validating login fields for email: {request.email}")
        print("=====================================")
        
        errors = []
        
        # 1. Email validation
        if not request.email or not request.email.strip():
            errors.append("Email is required.")
        else:
            # Basic email format validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, request.email):
                errors.append("Invalid email format.")
        
        # 2. Password validation
        if not request.password or not request.password.strip():
            errors.append("Password is required.")
        else:
            if len(request.password) < 6:
                errors.append("Password must be at least 6 characters long.")
        
        # 3. Database validation (if basic validation passes)
        if not errors:
            try:
                # Find user by email
                user = db.query(UserModel).filter(UserModel.email == request.email).first()
                
                if not user:
                    errors.append("Invalid email or password.")
                else:
                    # Check if user is deleted
                    if hasattr(user, 'isDeleted') and user.isDeleted:
                        errors.append("Account not found.")
                    else:
                        # Verify password
                        if not user.password_hash:
                            errors.append("Invalid email or password.")
                        else:
                            try:
                                # Check password using bcrypt
                                password_valid = bcrypt.checkpw(
                                    request.password.encode('utf-8'), 
                                    user.password_hash.encode('utf-8')
                                )
                                if not password_valid:
                                    errors.append("Invalid email or password.")
                                else:
                                    # Check if user is a student
                                    student = db.query(StudentModel).filter(StudentModel.user_id == user.id).first()
                                    if not student:
                                        errors.append("Student account not found.")
                            except Exception as pwd_error:
                                print(f"Password verification error: {pwd_error}")
                                errors.append("Invalid email or password.")
                                
            except Exception as db_error:
                print(f"Database validation error: {db_error}")
                errors.append("Database error during validation.")
        
        # Return validation result
        if errors:
            print(f"Login validation failed with errors: {errors}")
            return LoginValidationResponse(
                is_valid=False,
                message="Validation failed",
                errors=errors
            )
        
        print("Login fields and credentials are valid")
        return LoginValidationResponse(
            is_valid=True,
            message="Login credentials are valid",
            errors=None
        )
        
    except Exception as e:
        print(f"Unexpected error in login validation: {e}")
        return LoginValidationResponse(
            is_valid=False,
            message=f"Validation failed: {str(e)}",
            errors=[f"Server error: {str(e)}"]
        )

# Placeholder for future login methods
def send_login_otp(email: str, db: Session):
    """
    Send OTP for login (to be implemented)
    
    Args:
        email: User email
        db: Database session
        
    Returns:
        tuple: (success, message, otp_id)
    """
    # TODO: Implement OTP-based login
    return False, "OTP login not yet implemented", None

def verify_login_otp_finalize(otp_id: int, otp_code: str, db: Session):
    """
    Verify OTP for login and finalize authentication (to be implemented)
    
    Args:
        otp_id: OTP request ID
        otp_code: OTP code
        db: Database session
        
    Returns:
        tuple: (success, message, user_data, token)
    """
    # TODO: Implement OTP verification for login with token generation
    return False, "OTP verification not yet implemented", None, None

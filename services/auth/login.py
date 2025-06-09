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

class LoginOTPRequest(BaseModel):
    """Request model for sending login OTP"""
    email: str

class LoginOTPResponse(BaseModel):
    """Response model for login OTP"""
    success: bool
    message: str
    otp_id: Optional[int] = None

class LoginOTPVerificationRequest(BaseModel):
    """Request model for verifying login OTP"""
    otp_id: int
    otp_code: str

class LoginOTPVerificationResponse(BaseModel):
    """Response model for login OTP verification"""
    success: bool
    message: str
    user: Optional[dict] = None
    token: Optional[str] = None

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

def send_login_otp(request: LoginOTPRequest, db: Session):
    """
    Send OTP for login
    
    Args:
        request: LoginOTPRequest with email
        db: Database session
        
    Returns:
        LoginOTPResponse with success status and OTP ID
    """
    try:
        import re
        
        print(f"=== SEND LOGIN OTP REQUEST DEBUG ===")
        print(f"Sending login OTP to: {request.email}")
        print("===================================")
        
        # 1. Basic email validation
        if not request.email or not request.email.strip():
            return LoginOTPResponse(
                success=False,
                message="Email is required",
                otp_id=None
            )
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, request.email):
            return LoginOTPResponse(
                success=False,
                message="Invalid email format",
                otp_id=None
            )
        
        # 2. Check if user exists and is a student
        user = db.query(UserModel).filter(UserModel.email == request.email).first()
        
        if not user:
            return LoginOTPResponse(
                success=False,
                message="Email not found",
                otp_id=None
            )
        
        # Check if user is deleted
        if hasattr(user, 'isDeleted') and user.isDeleted:
            return LoginOTPResponse(
                success=False,
                message="Account not found",
                otp_id=None
            )
        
        # Check if user is a student
        student = db.query(StudentModel).filter(StudentModel.user_id == user.id).first()
        if not student:
            return LoginOTPResponse(
                success=False,
                message="Student account not found",
                otp_id=None
            )
        
        # 3. Create and send OTP for login
        from services.otp.service import OTPService
        
        # Prepare login data to store with OTP
        login_data = {
            "user_id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "student_number": student.student_number
        }
        
        success, message, otp_id = OTPService.create_login_otp(
            email=user.email,
            first_name=user.first_name,
            login_data=login_data,
            db=db
        )
        
        if not success:
            return LoginOTPResponse(
                success=False,
                message=message,
                otp_id=None
            )
        
        print(f"✅ Login OTP sent successfully to {user.email} (OTP ID: {otp_id})")
        
        return LoginOTPResponse(
            success=True,
            message="Login OTP sent successfully. Please check your email for the verification code.",
            otp_id=otp_id
        )
        
    except Exception as e:
        print(f"Unexpected error in send_login_otp: {str(e)}")
        import traceback
        traceback.print_exc()
        return LoginOTPResponse(
            success=False,
            message=f"Failed to send login OTP: {str(e)}",
            otp_id=None
        )

def verify_login_otp(request: LoginOTPVerificationRequest, db: Session):
    """
    Verify OTP for login and finalize authentication
    
    Args:
        request: LoginOTPVerificationRequest with OTP ID and code
        db: Database session
        
    Returns:
        LoginOTPVerificationResponse with success status, user data, and token
    """
    try:
        print(f"=== VERIFY LOGIN OTP REQUEST DEBUG ===")
        print(f"Verifying login OTP ID: {request.otp_id}, Code: {request.otp_code}")
        print("=====================================")
        
        # Verify OTP and get login data
        from services.otp.service import OTPService
        
        is_valid, message_or_data, login_data = OTPService.verify_otp(
            otp_id=request.otp_id,
            otp_code=request.otp_code,
            db=db
        )
        
        if not is_valid:
            print(f"OTP verification failed: {message_or_data}")
            return LoginOTPVerificationResponse(
                success=False,
                message=message_or_data,
                user=None,
                token=None
            )
        
        if not login_data:
            print("No login data found")
            return LoginOTPVerificationResponse(
                success=False,
                message="Login data not found",
                user=None,
                token=None
            )
        
        print(f"OTP verified successfully, proceeding with login")
        
        # Get user information from the database
        user_id = login_data.get('user_id')
        if not user_id:
            return LoginOTPVerificationResponse(
                success=False,
                message="Invalid login data",
                user=None,
                token=None
            )
        
        # Fetch fresh user data from database
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return LoginOTPVerificationResponse(
                success=False,
                message="User not found",
                user=None,
                token=None
            )
        
        # Check if user is still active
        if hasattr(user, 'isDeleted') and user.isDeleted:
            return LoginOTPVerificationResponse(
                success=False,
                message="Account not found",
                user=None,
                token=None
            )
        
        # Get student information
        student = db.query(StudentModel).filter(StudentModel.user_id == user.id).first()
        if not student:
            return LoginOTPVerificationResponse(
                success=False,
                message="Student account not found",
                user=None,
                token=None
            )
        
        # Prepare user data for response
        user_data = {
            "user_id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "role": user.role,
            "student_number": student.student_number,
            "verified": getattr(user, 'verified', 0),
            "status_id": getattr(user, 'status_id', 1)
        }
        
        # Add middle name if it exists
        if hasattr(user, 'middle_name') and user.middle_name:
            user_data["middle_name"] = user.middle_name
        
        # Generate JWT token using the new JWT service
        from services.auth.jwt_service import JWTService
        try:
            auth_token = JWTService.generate_token(user_data)
        except Exception as token_error:
            print(f"Error generating JWT token: {token_error}")
            return LoginOTPVerificationResponse(
                success=False,
                message="Failed to generate authentication token",
                user=None,
                token=None
            )
        
        print(f"✅ Login successful for: {user.email} (ID: {user.id})")
        
        return LoginOTPVerificationResponse(
            success=True,
            message="Login successful",
            user=user_data,
            token=auth_token
        )
        
    except Exception as e:
        print(f"Unexpected error in verify_login_otp: {str(e)}")
        import traceback
        traceback.print_exc()
        return LoginOTPVerificationResponse(
            success=False,
            message=f"Login verification failed: {str(e)}",
            user=None,
            token=None
        )

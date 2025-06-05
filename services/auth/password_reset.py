from fastapi import HTTPException
from sqlalchemy.orm import Session
import bcrypt
from datetime import datetime
from pydantic import BaseModel
from models import User as UserModel, Student as StudentModel
from typing import Optional

class ForgotPasswordValidationRequest(BaseModel):
    """Request model for validating forgot password email"""
    email: str

class ForgotPasswordValidationResponse(BaseModel):
    """Response model for forgot password validation"""
    is_valid: bool
    message: str
    errors: Optional[list] = None

class ForgotPasswordOTPRequest(BaseModel):
    """Request model for sending forgot password OTP"""
    email: str

class ForgotPasswordOTPResponse(BaseModel):
    """Response model for forgot password OTP"""
    success: bool
    message: str
    otp_id: Optional[int] = None

class PasswordResetOTPVerificationRequest(BaseModel):
    """Request model for verifying password reset OTP"""
    otp_id: int
    otp_code: str

class PasswordResetOTPVerificationResponse(BaseModel):
    """Response model for password reset OTP verification"""
    success: bool
    message: str
    reset_token: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    """Request model for resetting password"""
    reset_token: str
    new_password: str

class ResetPasswordResponse(BaseModel):
    """Response model for password reset"""
    success: bool
    message: str

def validate_forgot_password_email(request: ForgotPasswordValidationRequest, db: Session):
    """
    Validate email for forgot password functionality
    
    Args:
        request: ForgotPasswordValidationRequest with email
        db: Database session for email validation
        
    Returns:
        ForgotPasswordValidationResponse with validation results
    """
    try:
        import re
        
        print(f"=== FORGOT PASSWORD VALIDATION REQUEST DEBUG ===")
        print(f"Validating email for forgot password: {request.email}")
        print("===============================================")
        
        errors = []
        
        # 1. Email validation
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
        
        # 2. Database validation (if basic validation passes)
        if not errors:
            try:
                # Find user by email
                user = db.query(UserModel).filter(UserModel.email == request.email).first()
                
                if not user:
                    errors.append("Email not found in our system.")
                else:
                    # Check if user is deleted
                    if hasattr(user, 'isDeleted') and user.isDeleted:
                        errors.append("Account not found.")
                    else:
                        # Check if user is a student
                        student = db.query(StudentModel).filter(StudentModel.user_id == user.id).first()
                        if not student:
                            errors.append("Student account not found.")
                        else:
                            # Check if account is verified
                            if hasattr(user, 'verified') and not user.verified:
                                errors.append("Account is not verified. Please complete registration first.")
                                
            except Exception as db_error:
                print(f"Database validation error: {db_error}")
                errors.append("Database error during validation.")
        
        # Return validation result
        if errors:
            print(f"Forgot password validation failed with errors: {errors}")
            return ForgotPasswordValidationResponse(
                is_valid=False,
                message="Validation failed",
                errors=errors
            )
        
        print("Email is valid for password reset")
        return ForgotPasswordValidationResponse(
            is_valid=True,
            message="Email is valid for password reset",
            errors=None
        )
        
    except Exception as e:
        print(f"Unexpected error in forgot password validation: {e}")
        return ForgotPasswordValidationResponse(
            is_valid=False,
            message=f"Validation failed: {str(e)}",
            errors=[f"Server error: {str(e)}"]
        )

def send_forgot_password_otp(request: ForgotPasswordOTPRequest, db: Session):
    """
    Send OTP for forgot password
    
    Args:
        request: ForgotPasswordOTPRequest with email
        db: Database session
        
    Returns:
        ForgotPasswordOTPResponse with success status and OTP ID
    """
    try:
        import re
        
        print(f"=== SEND FORGOT PASSWORD OTP REQUEST DEBUG ===")
        print(f"Sending forgot password OTP to: {request.email}")
        print("=============================================")
        
        # 1. Basic email validation
        if not request.email or not request.email.strip():
            return ForgotPasswordOTPResponse(
                success=False,
                message="Email is required",
                otp_id=None
            )
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, request.email):
            return ForgotPasswordOTPResponse(
                success=False,
                message="Invalid email format",
                otp_id=None
            )
        
        # Check PUP domain
        if not request.email.endswith("@iskolarngbayan.pup.edu.ph"):
            return ForgotPasswordOTPResponse(
                success=False,
                message="Email must be a valid PUP email address (@iskolarngbayan.pup.edu.ph)",
                otp_id=None
            )
        
        # 2. Check if user exists and is a valid student
        user = db.query(UserModel).filter(UserModel.email == request.email).first()
        
        if not user:
            return ForgotPasswordOTPResponse(
                success=False,
                message="Email not found in our system",
                otp_id=None
            )
        
        # Check if user is deleted
        if hasattr(user, 'isDeleted') and user.isDeleted:
            return ForgotPasswordOTPResponse(
                success=False,
                message="Account not found",
                otp_id=None
            )
        
        # Check if user is a student
        student = db.query(StudentModel).filter(StudentModel.user_id == user.id).first()
        if not student:
            return ForgotPasswordOTPResponse(
                success=False,
                message="Student account not found",
                otp_id=None
            )
        
        # Check if account is verified
        if hasattr(user, 'verified') and not user.verified:
            return ForgotPasswordOTPResponse(
                success=False,
                message="Account is not verified. Please complete registration first",
                otp_id=None
            )
        
        # 3. Create and send OTP for password reset
        from services.otp.service import OTPService
        
        # Prepare password reset data to store with OTP
        password_reset_data = {
            "user_id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "student_number": student.student_number
        }
        
        success, message, otp_id = OTPService.create_password_reset_otp(
            email=user.email,
            first_name=user.first_name,
            password_reset_data=password_reset_data,
            db=db
        )
        
        if not success:
            return ForgotPasswordOTPResponse(
                success=False,
                message=message,
                otp_id=None
            )
        
        print(f"✅ Forgot password OTP sent successfully to {user.email} (OTP ID: {otp_id})")
        
        return ForgotPasswordOTPResponse(
            success=True,
            message="Password reset OTP sent successfully. Please check your email for the verification code.",
            otp_id=otp_id
        )
        
    except Exception as e:
        print(f"Unexpected error in send_forgot_password_otp: {str(e)}")
        import traceback
        traceback.print_exc()
        return ForgotPasswordOTPResponse(
            success=False,
            message=f"Failed to send password reset OTP: {str(e)}",
            otp_id=None
        )

def verify_password_reset_otp(request: PasswordResetOTPVerificationRequest, db: Session):
    """
    Verify OTP for password reset
    
    Args:
        request: PasswordResetOTPVerificationRequest with OTP ID and code
        db: Database session
        
    Returns:
        PasswordResetOTPVerificationResponse with success status and reset token
    """
    try:
        print(f"=== VERIFY PASSWORD RESET OTP REQUEST DEBUG ===")
        print(f"Verifying password reset OTP ID: {request.otp_id}, Code: {request.otp_code}")
        print("==============================================")
        
        # Verify OTP and get password reset data
        from services.otp.service import OTPService
        
        is_valid, message_or_data, password_reset_data = OTPService.verify_otp(
            otp_id=request.otp_id,
            otp_code=request.otp_code,
            db=db
        )
        
        if not is_valid:
            print(f"OTP verification failed: {message_or_data}")
            return PasswordResetOTPVerificationResponse(
                success=False,
                message=message_or_data,
                reset_token=None
            )
        
        if not password_reset_data:
            print("No password reset data found")
            return PasswordResetOTPVerificationResponse(
                success=False,
                message="Password reset data not found",
                reset_token=None
            )
        
        print(f"OTP verified successfully, generating reset token")
        
        # Get user information from the stored data
        user_id = password_reset_data.get('user_id')
        email = password_reset_data.get('email')
        
        if not user_id or not email:
            return PasswordResetOTPVerificationResponse(
                success=False,
                message="Invalid password reset data",
                reset_token=None
            )
        
        # Verify user still exists and is valid
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return PasswordResetOTPVerificationResponse(
                success=False,
                message="User not found",
                reset_token=None
            )
        
        # Check if user is still active
        if hasattr(user, 'isDeleted') and user.isDeleted:
            return PasswordResetOTPVerificationResponse(
                success=False,
                message="Account not found",
                reset_token=None
            )
        
        # Check if user is still a student
        student = db.query(StudentModel).filter(StudentModel.user_id == user.id).first()
        if not student:
            return PasswordResetOTPVerificationResponse(
                success=False,
                message="Student account not found",
                reset_token=None
            )
        
        # Generate a secure reset token
        import secrets
        import time
        reset_token = f"reset_{user.id}_{int(time.time())}_{secrets.token_urlsafe(32)}"
        
        # Store the reset token temporarily (using the same temp storage approach)
        # In a production environment, you might want to use Redis or a dedicated table
        from services.otp.service import OTPService
        OTPService._reset_tokens = getattr(OTPService, '_reset_tokens', {})
        
        # Store token with expiry (15 minutes like OTP)
        from datetime import datetime, timedelta
        token_expiry = datetime.now() + timedelta(minutes=15)
        
        OTPService._reset_tokens[reset_token] = {
            "user_id": user.id,
            "email": user.email,
            "expires_at": token_expiry,
            "used": False
        }
        
        print(f"✅ Password reset token generated for: {user.email} (ID: {user.id})")
        
        return PasswordResetOTPVerificationResponse(
            success=True,
            message="OTP verified successfully. You can now reset your password.",
            reset_token=reset_token
        )
        
    except Exception as e:
        print(f"Unexpected error in verify_password_reset_otp: {str(e)}")
        import traceback
        traceback.print_exc()
        return PasswordResetOTPVerificationResponse(
            success=False,
            message=f"Password reset OTP verification failed: {str(e)}",
            reset_token=None
        )

def reset_password(request: ResetPasswordRequest, db: Session):
    """
    Reset password with reset token
    
    Args:
        request: ResetPasswordRequest with reset token and new password
        db: Database session
        
    Returns:
        ResetPasswordResponse with success status
    """
    try:
        print(f"=== RESET PASSWORD REQUEST DEBUG ===")
        print(f"Resetting password with token: {request.reset_token[:20]}...")
        print("===================================")
        
        # 1. Validate reset token
        from services.otp.service import OTPService
        reset_tokens = getattr(OTPService, '_reset_tokens', {})
        
        if request.reset_token not in reset_tokens:
            return ResetPasswordResponse(
                success=False,
                message="Invalid or expired reset token"
            )
        
        token_data = reset_tokens[request.reset_token]
        
        # Check if token is expired
        if datetime.now() > token_data["expires_at"]:
            # Clean up expired token
            del reset_tokens[request.reset_token]
            return ResetPasswordResponse(
                success=False,
                message="Reset token has expired"
            )
        
        # Check if token has already been used
        if token_data["used"]:
            return ResetPasswordResponse(
                success=False,
                message="Reset token has already been used"
            )
        
        # 2. Validate new password requirements
        password_errors = []
        
        if not request.new_password:
            password_errors.append("Password is required")
        elif len(request.new_password) < 6:
            password_errors.append("Password must be at least 6 characters long")
        else:
            # Check password complexity
            import re
            if not re.search(r'[A-Z]', request.new_password):
                password_errors.append("Password must contain at least one uppercase letter")
            if not re.search(r'[a-z]', request.new_password):
                password_errors.append("Password must contain at least one lowercase letter")
            if not re.search(r'\d', request.new_password):
                password_errors.append("Password must contain at least one number")
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', request.new_password):
                password_errors.append("Password must contain at least one special character")
        
        if password_errors:
            return ResetPasswordResponse(
                success=False,
                message="Password validation failed: " + "; ".join(password_errors)
            )
        
        # 3. Get user and update password
        user_id = token_data["user_id"]
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        
        if not user:
            return ResetPasswordResponse(
                success=False,
                message="User not found"
            )
        
        # Check if user is still active
        if hasattr(user, 'isDeleted') and user.isDeleted:
            return ResetPasswordResponse(
                success=False,
                message="Account not found"
            )
        
        # Hash the new password
        hashed_password = bcrypt.hashpw(request.new_password.encode('utf-8'), bcrypt.gensalt())
        
        # Update user password
        user.password = hashed_password.decode('utf-8')
        user.updated_at = datetime.now()
        
        db.commit()
        
        # 4. Mark token as used and clean up
        token_data["used"] = True
        
        # Send password reset success email
        try:
            from services.email.service import EmailService
            email_service = EmailService()
            email_service.send_password_reset_success_email(user.email, user.first_name)
        except Exception as email_error:
            print(f"Failed to send password reset success email: {email_error}")
            # Don't fail the password reset if email fails
        
        print(f"✅ Password reset successfully for user: {user.email} (ID: {user.id})")
        
        return ResetPasswordResponse(
            success=True,
            message="Password reset successfully. You can now log in with your new password."
        )
        
    except Exception as e:
        print(f"Unexpected error in reset_password: {str(e)}")
        import traceback
        traceback.print_exc()
        return ResetPasswordResponse(
            success=False,
            message=f"Password reset failed: {str(e)}"
        )

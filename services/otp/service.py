from sqlalchemy.orm import Session
import random
import json
from datetime import datetime, timedelta
from fastapi import HTTPException

# Import OTP_Request directly from models
from models import OTP_Request
from services.email.config import OTP_EXPIRY_MINUTES
from services.email.service import EmailService

class OTPService:
    @staticmethod
    def generate_otp(length=6):
        """Generate a random numeric OTP of specified length"""
        return ''.join([str(random.randint(0, 9)) for _ in range(length)])
    
    @staticmethod
    def create_otp(email: str, first_name: str, otp_type: str, db: Session, additional_data: dict = None):
        """
        Generic method to create an OTP for any purpose
        Uses user_id=0 for registration OTPs since user doesn't exist yet
        Stores email and other data in a temporary way
        """
        # Generate OTP code
        otp_code = OTPService.generate_otp()
        
        # Set expiry time
        expires_at = datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
        
        try:
            # Create OTP record with your model structure
            # user_id=0 for registration OTPs (since user doesn't exist yet)
            # We'll store the email and registration data in a way that can be retrieved later
            otp_request = OTP_Request(
                user_id=0,  # Set to 0 for registration OTPs
                otp_code=otp_code,
                type=otp_type,
                created_at=datetime.now(),
                expires_at=expires_at
            )
            
            db.add(otp_request)
            db.commit()
            db.refresh(otp_request)
            
            print(f"OTP created successfully: ID={otp_request.id}, Type={otp_type}, Code={otp_code}")
            
            # Store email and registration data in a separate way since your OTP_Request doesn't have these fields
            # We'll create a mapping using the OTP ID
            if additional_data:
                additional_data['email'] = email
                additional_data['first_name'] = first_name
                # Store this data temporarily using the OTP ID as key
                # You could use Redis, a cache, or another table for this
                # For now, we'll pass it to the email service and handle storage in verify
                OTPService._temp_storage = getattr(OTPService, '_temp_storage', {})
                OTPService._temp_storage[otp_request.id] = additional_data
            
            # Send appropriate email based on OTP type
            email_service = EmailService()
            success = False
            message = ""
            
            if otp_type == "registration":
                success, message = email_service.send_registration_otp_email(
                    to_email=email,
                    first_name=first_name,
                    otp_code=otp_code
                )
            elif otp_type == "password_reset":
                success, message = email_service.send_password_reset_otp_email(
                    to_email=email,
                    first_name=first_name,
                    otp_code=otp_code
                )
            elif otp_type == "login":
                success, message = email_service.send_login_otp_email(
                    to_email=email,
                    first_name=first_name,
                    otp_code=otp_code
                )
            elif otp_type == "email_verification":
                success, message = email_service.send_email_verification_otp_email(
                    to_email=email,
                    first_name=first_name,
                    otp_code=otp_code
                )
            else:
                # Generic email for unknown types
                success, message = email_service.send_generic_otp_email(
                    to_email=email,
                    first_name=first_name,
                    otp_code=otp_code,
                    purpose=otp_type
                )
            
            if not success:
                return False, f"Failed to send OTP email: {message}", otp_request.id
                
            return True, "OTP sent successfully", otp_request.id
            
        except Exception as e:
            db.rollback()
            print(f"Error creating OTP: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Error creating OTP: {str(e)}", None
    
    @staticmethod
    def create_registration_otp(email: str, first_name: str, registration_data: dict, db: Session):
        """
        Create a registration OTP and send it via email
        """
        return OTPService.create_otp(
            email=email,
            first_name=first_name,
            otp_type="registration",
            db=db,
            additional_data=registration_data
        )
    
    @staticmethod
    def create_login_otp(email: str, first_name: str, login_data: dict, db: Session):
        """
        Create a login OTP and send it via email
        """
        return OTPService.create_otp(
            email=email,
            first_name=first_name,
            otp_type="login",
            db=db,
            additional_data=login_data
        )
    
    @staticmethod
    def create_password_reset_otp(email: str, first_name: str, password_reset_data: dict, db: Session):
        """
        Create a password reset OTP and send it via email
        """
        return OTPService.create_otp(
            email=email,
            first_name=first_name,
            otp_type="password_reset",
            db=db,
            additional_data=password_reset_data
        )

    @staticmethod
    def verify_otp(otp_id: int, otp_code: str, db: Session):
        """
        Verify an OTP code and return stored registration data
        """
        try:
            # Get OTP request
            otp_request = db.query(OTP_Request).filter(OTP_Request.id == otp_id).first()
            
            if not otp_request:
                return False, "Invalid OTP request", None
                
            # Check if expired
            if datetime.now() > otp_request.expires_at:
                return False, "OTP has expired", None
                
            # Check if OTP matches
            if otp_request.otp_code != otp_code:
                return False, "Invalid OTP code", None
                
            # Get stored registration data
            registration_data = None
            if hasattr(OTPService, '_temp_storage') and otp_id in OTPService._temp_storage:
                registration_data = OTPService._temp_storage[otp_id]
                # Clean up after successful verification
                del OTPService._temp_storage[otp_id]
            
            # Delete the OTP request after successful verification
            db.delete(otp_request)
            db.commit()
                
            return True, "OTP verified successfully", registration_data
            
        except Exception as e:
            print(f"Error verifying OTP: {str(e)}")
            return False, f"Error verifying OTP: {str(e)}", None

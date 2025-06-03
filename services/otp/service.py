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
    def create_registration_otp(email: str, first_name: str, registration_data: dict, db: Session):
        """
        Create a registration OTP and send it via email
        
        Args:
            email (str): User's email
            first_name (str): User's first name
            registration_data (dict): User registration data
            db (Session): Database session
            
        Returns:
            tuple: (success, message, otp_id)
        """
        # Generate OTP code
        otp_code = OTPService.generate_otp()
        
        # Set expiry time
        expires_at = datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
        
        # Store registration data as JSON
        registration_json = json.dumps(registration_data)
        
        try:
            # Create OTP record using your existing OTP_Request model
            otp_request = OTP_Request(
                email=email,
                otp_code=otp_code,
                type="registration",
                expires_at=expires_at,
                registration_data=registration_json
            )
            
            db.add(otp_request)
            db.commit()
            db.refresh(otp_request)
            
            # Send OTP email
            email_service = EmailService()
            success, message = email_service.send_registration_otp_email(
                to_email=email,
                first_name=first_name,
                otp_code=otp_code
            )
            
            if not success:
                return False, f"Failed to send OTP email: {message}", otp_request.id
                
            return True, "OTP sent successfully", otp_request.id
            
        except Exception as e:
            db.rollback()
            return False, f"Error creating OTP: {str(e)}", None
    
    @staticmethod
    def verify_otp(otp_id: int, otp_code: str, db: Session):
        """
        Verify an OTP code
        
        Args:
            otp_id (int): OTP request ID
            otp_code (str): OTP code to verify
            db (Session): Database session
            
        Returns:
            tuple: (is_valid, message, registration_data)
        """
        try:
            # Get OTP request
            otp_request = db.query(OTP_Request).filter(OTP_Request.id == otp_id).first()
            
            if not otp_request:
                return False, "Invalid OTP request", None
                
            # Check if already verified
            if otp_request.verified == 1:
                return False, "OTP already used", None
                
            # Check if expired
            if datetime.now() > otp_request.expires_at:
                return False, "OTP has expired", None
                
            # Check if OTP matches
            if otp_request.otp_code != otp_code:
                return False, "Invalid OTP code", None
                
            # Mark as verified
            otp_request.verified = 1
            db.commit()
            
            # Parse registration data
            registration_data = None
            if otp_request.registration_data:
                registration_data = json.loads(otp_request.registration_data)
                
            return True, "OTP verified successfully", registration_data
            
        except Exception as e:
            return False, f"Error verifying OTP: {str(e)}", None

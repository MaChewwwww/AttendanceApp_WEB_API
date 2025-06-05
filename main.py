import traceback
from fastapi import FastAPI, Depends, Security, HTTPException, File, UploadFile, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from pydantic import BaseModel, EmailStr
import base64
from typing import Optional
import numpy as np
import cv2
import json
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import database components
from db import get_db, engine
from models import Base, User, Student, OTP_Request
from services.auth.register import (
    register_student, RegisterRequest,
    validate_registration_fields, RegistrationValidationRequest, RegistrationValidationResponse
)
from services.auth.login import (
    validate_login_fields, LoginValidationRequest, LoginValidationResponse
)
from services.security.api_key import get_api_key
from services.face.validator import validate_face_image
from services.otp.service import OTPService
from services.otp.cleanup import start_cleanup_service, stop_cleanup_service

#------------------------------------------------------------
# FastAPI Application Setup
#------------------------------------------------------------

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    try:
        # Database connection is verified just by creating the app
        print("✓ Database connection established")
        
        # Start OTP cleanup service
        print("🚀 Starting OTP cleanup service...")
        cleanup_task = await start_cleanup_service()
        print("✓ OTP cleanup service started (runs every 15 minutes)")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        traceback.print_exc()
    
    print("✓ AttendanceApp API is ready to accept requests")
    yield
    
    # Cleanup code (when shutting down)
    print("🛑 Shutting down API...")
    try:
        print("🧹 Stopping OTP cleanup service...")
        await stop_cleanup_service()
        print("✓ OTP cleanup service stopped")
    except Exception as e:
        print(f"Error stopping cleanup service: {e}")
    
    print("👋 API shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="AttendanceApp API",
    description="API for the AttendanceApp attendance tracking system",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*", 
        "https://localhost:*",
        "https://127.0.0.1:*"
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

#------------------------------------------------------------
# Exception Handlers
#------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    """Custom handler for HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "code": exc.status_code
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Custom handler for validation errors"""
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Invalid request parameters",
            "errors": [{"field": error["loc"][1], "message": error["msg"]} 
                      for error in exc.errors() if len(error["loc"]) > 1]
        },
    )

#------------------------------------------------------------
# Data Models
#------------------------------------------------------------

# Face image validation model
class FaceValidationRequest(BaseModel):
    face_image: str  # Base64 encoded image

class FaceValidationResponse(BaseModel):
    is_valid: bool
    message: str

# OTP Models
class InitRegistrationRequest(BaseModel):
    """Initial registration request with face validation"""
    registration_data: RegisterRequest
    face_image: Optional[str] = None  # Base64 encoded image

class OTPVerificationRequest(BaseModel):
    """OTP verification request"""
    otp_id: int
    otp_code: str

class OTPResponse(BaseModel):
    """OTP response"""
    success: bool
    message: str
    otp_id: Optional[int] = None

# Face validation for registration
class RegistrationFaceValidationRequest(BaseModel):
    """Request model for validating face during registration"""
    face_image: str  # Base64 encoded image

# Login validation model
class LoginValidationRequest(BaseModel):
    """Request model for validating login fields"""
    email: str
    password: str

class LoginValidationResponse(BaseModel):
    """Response model for login validation"""
    is_valid: bool
    message: str
    errors: Optional[list] = None

#------------------------------------------------------------
# Health Check
#------------------------------------------------------------

# Health check endpoint - no API key required
@app.get("/health", status_code=200)
def health_check():
    """Health check endpoint to verify API is running"""
    return {"status": "healthy", "message": "API is running"}

#------------------------------------------------------------
# Face Validation
#------------------------------------------------------------

# Face validation endpoint
@app.post("/validate-face", response_model=FaceValidationResponse)
def validate_face_endpoint(
    request: FaceValidationRequest,
    api_key: str = Security(get_api_key)
):
    """Validate if the provided image contains a properly visible face"""
    try:
        is_valid, message = validate_face_image(request.face_image)
        return {"is_valid": is_valid, "message": message}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error validating face: {str(e)}")

#============================================================
# STUDENT REGISTRATION ENDPOINTS
#============================================================

#------------------------------------------------------------
# Multi-Step Registration Flow (Recommended)
#------------------------------------------------------------

# Step 0: Validate registration fields
@app.post("/registerStudent/validate-fields", response_model=RegistrationValidationResponse)
def validate_registration_fields_endpoint(
    request: RegistrationValidationRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Validate registration fields before proceeding with face capture:
    1. Validate all required fields
    2. Check business rules (age, email domain, password strength, etc.)
    3. Check for existing email and student number
    4. Return validation result
    """
    return validate_registration_fields(request, db)

# Step 1: Validate face image for registration
@app.post("/registerStudent/validate-face", response_model=FaceValidationResponse)
def validate_registration_face(
    request: RegistrationFaceValidationRequest,
    api_key: str = Security(get_api_key)
):
    """
    Validate face image for registration:
    1. Check if the provided image contains a properly visible face
    2. Ensure face quality meets requirements
    3. Return validation result
    
    Note: Field validation should be done via /registerStudent/validate-fields first
    """
    try:
        print(f"=== FACE VALIDATION REQUEST DEBUG ===")
        print(f"Received face validation request for registration")
        print("====================================")
        
        is_valid, message = validate_face_image(request.face_image)
        
        print(f"Face validation result: {is_valid} - {message}")
        
        return {"is_valid": is_valid, "message": message}
    except Exception as e:
        print(f"Face validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error validating face: {str(e)}")

# Step 2: Send OTP for registration
@app.post("/registerStudent/send-otp", response_model=OTPResponse)
def send_registration_otp(
    request: InitRegistrationRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Send OTP for registration:
    1. Send OTP to user's email
    2. Store registration data temporarily
    3. Return OTP ID for verification
    
    Note: Field and face validation should be completed before this step
    """
    try:
        print(f"=== SEND OTP REQUEST DEBUG ===")
        print(f"Sending OTP to: {request.registration_data.email}")
        print("=============================")
        
        # Convert registration data to dict for storage
        reg_dict = request.registration_data.dict()
        
        # If face image is provided, include it in registration data
        if request.face_image:
            reg_dict["face_image"] = request.face_image
        
        # Create and send OTP for registration with better error handling
        try:
            success, message, otp_id = OTPService.create_registration_otp(
                email=request.registration_data.email,
                first_name=request.registration_data.first_name,
                registration_data=reg_dict,
                db=db
            )
            
            print(f"OTP Service result: success={success}, message={message}, otp_id={otp_id}")
            
        except Exception as otp_error:
            print(f"OTP Service error: {str(otp_error)}")
            raise HTTPException(status_code=500, detail=f"OTP creation failed: {str(otp_error)}")
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
        
        return {
            "success": True,
            "message": "OTP sent successfully. Please check your email for the verification code.",
            "otp_id": otp_id
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in send_registration_otp: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")

# Step 3: Verify OTP and complete registration
@app.post("/registerStudent/verify", status_code=201)
def verify_registration(
    request: OTPVerificationRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Verify OTP and complete the registration process:
    1. Verify the provided OTP code
    2. If valid, proceed with student registration
    3. Return the registered student information
    """
    try:
        print(f"=== VERIFY REGISTRATION DEBUG ===")
        print(f"Verifying OTP ID: {request.otp_id}, Code: {request.otp_code}")
        print("================================")
        
        # Verify OTP and get registration data
        is_valid, message_or_data, registration_data = OTPService.verify_otp(
            otp_id=request.otp_id,
            otp_code=request.otp_code,
            db=db
        )
        
        if not is_valid:
            print(f"OTP verification failed: {message_or_data}")
            raise HTTPException(status_code=400, detail=message_or_data)
        
        if not registration_data:
            print("No registration data found")
            raise HTTPException(status_code=400, detail="Registration data not found")
        
        print(f"OTP verified successfully, proceeding with registration")
        
        # Check if the message_or_data contains user info (already registered case)
        if isinstance(message_or_data, dict) and 'user_id' in message_or_data:
            print(f"User already registered, returning existing info")
            return {
                "status": "success",
                "message": "Registration completed successfully",
                "user": message_or_data
            }
        
        # Convert back to RegisterRequest for registration
        try:
            register_request = RegisterRequest(**registration_data)
            print(f"Converted registration data for user: {register_request.email}")
        except Exception as conversion_error:
            print(f"Error converting registration data: {conversion_error}")
            raise HTTPException(status_code=400, detail="Invalid registration data format")
        
        # Register the student in the main database
        try:
            # Pass is_otp_verified=True since this is after successful OTP verification
            result = register_student(register_request, db, is_otp_verified=True)
            print(f"Student registered successfully: {result}")
            
            # Log successful registration with welcome email sent
            print(f"🎉 Registration completed for {result['email']} - Welcome email should have been sent")
            
            # Return the result with the correct structure
            return {
                "status": "success", 
                "message": "Registration completed successfully! Welcome email has been sent to your inbox.",
                "user": result
            }
                
        except Exception as reg_error:
            print(f"Registration failed: {str(reg_error)}")
            # Check if it's a duplicate error
            if "already in use" in str(reg_error).lower():
                raise HTTPException(status_code=409, detail=str(reg_error))
            else:
                raise HTTPException(status_code=500, detail=f"Registration failed: {str(reg_error)}")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in verify_registration: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Registration verification failed: {str(e)}")


# Step 3: Verify OTP and complete registration (alternative endpoint name)
@app.post("/registerStudent/verify-registration", status_code=201)
def verify_registration_alt(
    request: OTPVerificationRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Alternative endpoint name for OTP verification and registration completion
    (calls the same logic as /registerStudent/verify)
    """
    return verify_registration(request, db, api_key)

#------------------------------------------------------------
# Legacy/Direct Registration Methods (For Backward Compatibility)
#------------------------------------------------------------

# Direct registration endpoint
@app.post("/registerStudent", status_code=201)
def register_student_endpoint(
    request: RegisterRequest, 
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Register a new student in the system (legacy method)"""
    return register_student(request, db)

# Direct registration with face validation endpoint
@app.post("/register-student-with-face", status_code=201)
def register_with_face_endpoint(
    registration_data: RegisterRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """Register a student with face validation (legacy method)"""
    # Validate the face image if provided
    if registration_data.face_image:
        is_valid, message = validate_face_image(registration_data.face_image)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
    
    # Process the registration
    return register_student(registration_data, db)

#============================================================
# STUDENT LOGIN ENDPOINTS
#============================================================

#------------------------------------------------------------
# Multi-Step Login Flow (Recommended)
#------------------------------------------------------------

# Step 1: Validate login fields and credentials
@app.post("/loginStudent/validate-fields", response_model=LoginValidationResponse)
def validate_login_fields_endpoint(
    request: LoginValidationRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Validate login fields and credentials:
    1. Check email format
    2. Check password requirements
    3. Validate email and password against database
    4. Return validation result
    """
    return validate_login_fields(request, db)

# TODO: Step 2: Send OTP for login
# @app.post("/loginStudent/send-login-otp")
# def send_login_otp_endpoint():
#     """
#     Send OTP for login:
#     1. Generate and send OTP to user's email
#     2. Return OTP ID for verification
#     """
#     pass

# TODO: Step 3: Verify OTP and finalize login
# @app.post("/loginStudent/verify-login-otp-finalize")
# def verify_login_otp_finalize_endpoint():
#     """
#     Verify OTP and complete login:
#     1. Verify the provided OTP code
#     2. Generate authentication token
#     3. Return user data and token
#     """
#     pass

#------------------------------------------------------------
# Legacy/Direct Login Methods (For Future Implementation)
#------------------------------------------------------------

# TODO: Direct login endpoint (if needed)
# @app.post("/login")
# def direct_login_endpoint():
#     """Direct login with email and password (legacy method)"""
#     pass
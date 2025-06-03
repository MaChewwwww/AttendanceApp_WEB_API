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
from services.auth.register import register_student, RegisterRequest
from services.security.api_key import get_api_key
from services.face.validator import validate_face_image
from services.otp.service import OTPService

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
    except Exception as e:
        print(f"Database initialization error: {e}")
        traceback.print_exc()
    
    print("✓ AttendanceApp API is ready to accept requests")
    yield
    
    # Cleanup code (when shutting down)
    print("Shutting down API...")

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
    allow_origins=["*"],  # Allows all origins
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

#------------------------------------------------------------
# Registration Flow
#------------------------------------------------------------

# 1. OTP-based Registration Flow (Recommended)
# Step 1: Initialize registration and send OTP
@app.post("/register/init", response_model=OTPResponse)
def init_registration(
    request: InitRegistrationRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Initialize the registration process:
    1. Validate face image if provided
    2. Send OTP to user's email
    3. Return OTP ID for verification
    """
    try:
        # Validate face image if provided
        if request.face_image:
            is_valid, message = validate_face_image(request.face_image)
            if not is_valid:
                raise HTTPException(status_code=400, detail=message)
        
        # Convert registration data to dict for storage
        reg_dict = request.registration_data.dict()
        
        # If face image is provided, include it in registration data
        if request.face_image:
            reg_dict["face_image"] = request.face_image
        
        # Create and send OTP for registration
        success, message, otp_id = OTPService.create_registration_otp(
            email=request.registration_data.email,
            first_name=request.registration_data.first_name,
            registration_data=reg_dict,
            db=db
        )
        
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
        raise HTTPException(status_code=500, detail=f"Registration initialization failed: {str(e)}")

# Step 2: Verify OTP and complete registration
@app.post("/register/verify", status_code=201)
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
        # Verify OTP using the main database
        is_valid, message, registration_data = OTPService.verify_otp(
            otp_id=request.otp_id,
            otp_code=request.otp_code,
            db=db
        )
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
        
        if not registration_data:
            raise HTTPException(status_code=400, detail="Registration data not found")
        
        # Convert back to RegisterRequest
        register_request = RegisterRequest(**registration_data)
        
        # Register the student in the main database
        result = register_student(register_request, db)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration verification failed: {str(e)}")

# 2. Legacy/Direct Registration Methods (For Backward Compatibility)

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
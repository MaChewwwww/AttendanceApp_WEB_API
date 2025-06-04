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

# Registration validation model
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

# Face validation for registration
class RegistrationFaceValidationRequest(BaseModel):
    """Request model for validating face during registration"""
    face_image: str  # Base64 encoded image

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
# Registration Flow for Students
#------------------------------------------------------------

# Step 0: Validate registration fields
@app.post("/registerStudent/validate-fields", response_model=RegistrationValidationResponse)
def validate_registration_fields(
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
    try:
        import re
        from datetime import datetime, date
        
        print(f"=== VALIDATION REQUEST DEBUG ===")
        print(f"Received request from frontend: {request}")
        print(f"Request headers received")
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
                existing_student = db.query(Student).filter(Student.student_number == request.student_number).first()
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
                    existing_user = db.query(User).filter(User.email == request.email).first()
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
            return {
                "is_valid": False,
                "message": "Validation failed",
                "errors": errors
            }
        
        print("All fields are valid")
        return {
            "is_valid": True,
            "message": "All fields are valid",
            "errors": None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in validation: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

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
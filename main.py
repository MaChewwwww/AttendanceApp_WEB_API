import traceback
from fastapi import FastAPI, Depends, Security, HTTPException, File, UploadFile, Form, Body, Header
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from pydantic import BaseModel, EmailStr
import base64
from typing import Optional, Dict, Any, List
import numpy as np
import cv2
import json
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import database components
from db import get_db, engine
from models import Base, User, Student, OTP_Request, Program, Section, Course, Assigned_Course, Assigned_Course_Approval

from services.auth.register import (
    register_student, RegisterRequest,
    validate_registration_fields, RegistrationValidationRequest, RegistrationValidationResponse
)
from services.auth.login import (
    validate_login_fields, LoginValidationRequest, LoginValidationResponse,
    send_login_otp, LoginOTPRequest, LoginOTPResponse,
    verify_login_otp, LoginOTPVerificationRequest, LoginOTPVerificationResponse
)
from services.security.api_key import get_api_key
from services.face.validator import validate_face_image
from services.otp.service import OTPService
from services.otp.cleanup import start_cleanup_service, stop_cleanup_service
from services.auth.password_reset import (
    validate_forgot_password_email, ForgotPasswordValidationRequest, ForgotPasswordValidationResponse,
    send_forgot_password_otp, ForgotPasswordOTPRequest, ForgotPasswordOTPResponse,
    verify_password_reset_otp, PasswordResetOTPVerificationRequest, PasswordResetOTPVerificationResponse,
    reset_password, ResetPasswordRequest, ResetPasswordResponse
)
from services.auth.onboarding import (
    OnboardingCheckResponse
)
from services.auth.jwt_service import (
    JWTService, get_current_user, get_current_student
)
from services.database import db_query
from services.database.create_db import assign_student_to_section

#------------------------------------------------------------
# FastAPI Application Setup
#------------------------------------------------------------

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    try:
        # Database connection is verified just by creating the app
        print("[OK] Database connection established")
        
        # Start OTP cleanup service
        print("[STARTING] OTP cleanup service...")
        cleanup_task = await start_cleanup_service()
        print("[OK] OTP cleanup service started (runs every 15 minutes)")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        traceback.print_exc()
    
    print("[OK] AttendanceApp API is ready to accept requests")
    yield
    
    # Cleanup code (when shutting down)
    print("[SHUTDOWN] Shutting down API...")
    try:
        print("[CLEANUP] Stopping OTP cleanup service...")
        await stop_cleanup_service()
        print("[OK] OTP cleanup service stopped")
    except Exception as e:
        print(f"Error stopping cleanup service: {e}")
    
    print("[DONE] API shutdown complete")

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

# Onboarding Models
class AvailableSectionsResponse(BaseModel):
    """Response model for available sections"""
    sections: list

class AvailableProgramsResponse(BaseModel):
    """Response model for available programs"""
    programs: list

class AvailableCoursesResponse(BaseModel):
    """Response model for available assigned courses"""
    courses: list

class SectionAssignmentRequest(BaseModel):
    """Request model for assigning student to section"""
    section_id: int

class SectionAssignmentResponse(BaseModel):
    """Response model for section assignment"""
    success: bool
    message: str
    student_id: Optional[int] = None
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    assigned_courses_count: Optional[int] = None
    approval_records_created: Optional[int] = None

# Student Courses Models
class StudentCourseInfo(BaseModel):
    """Model for individual course information"""
    assigned_course_id: int
    course_id: int
    course_name: str
    course_code: Optional[str] = None
    course_description: Optional[str] = None
    faculty_id: int
    faculty_name: str
    faculty_email: str
    section_id: int
    section_name: str
    program_id: int
    program_name: str
    program_acronym: str
    academic_year: Optional[str] = None
    semester: Optional[str] = None
    room: Optional[str] = None
    enrollment_status: str  # From assigned_course_approval
    rejection_reason: Optional[str] = None
    course_type: str  # "current" or "previous"
    approval_created_at: Optional[str] = None  # When approval was created
    approval_updated_at: Optional[str] = None  # When approval was last updated
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class StudentCoursesResponse(BaseModel):
    """Response model for student courses"""
    success: bool
    message: str
    student_info: Dict[str, Any]
    current_courses: List[StudentCourseInfo]
    previous_courses: List[StudentCourseInfo]
    total_current: int
    total_previous: int
    enrollment_summary: Dict[str, int]
    academic_year_summary: Optional[Dict[str, int]] = None

# Course Students Models
class CourseStudentInfo(BaseModel):
    """Model for individual student information in a course"""
    student_id: int
    user_id: int
    student_number: str
    name: str
    email: str
    enrollment_status: str  # From assigned_course_approval
    rejection_reason: Optional[str] = None
    enrollment_created_at: Optional[str] = None
    enrollment_updated_at: Optional[str] = None
    latest_attendance_date: Optional[str] = None
    latest_attendance_status: Optional[str] = None
    total_attendance_sessions: int
    present_count: int
    absent_count: int
    late_count: int
    attendance_percentage: float

class CourseStudentsResponse(BaseModel):
    """Response model for course students"""
    success: bool
    message: str
    course_info: Dict[str, Any]
    students: List[CourseStudentInfo]
    total_students: int
    enrollment_summary: Dict[str, int]
    attendance_summary: Dict[str, Any]

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

# Step 2: Send OTP for login
@app.post("/loginStudent/send-login-otp", response_model=LoginOTPResponse)
def send_login_otp_endpoint(
    request: LoginOTPRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Send OTP for login:
    1. Validate email exists in database
    2. Check if user is a valid student
    3. Generate and send OTP to user's email
    4. Return OTP ID for verification
    """
    return send_login_otp(request, db)

# Step 3: Verify OTP and finalize login
@app.post("/loginStudent/verify-login-otp", response_model=LoginOTPVerificationResponse)
def verify_login_otp_endpoint(
    request: LoginOTPVerificationRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Verify OTP and complete login:
    1. Verify the provided OTP code
    2. Authenticate the user
    3. Generate authentication token
    4. Return user data and token
    """
    return verify_login_otp(request, db)

#------------------------------------------------------------
# STUDENT PASSWORD RESET ENDPOINTS
#============================================================

#------------------------------------------------------------
# Multi-Step Password Reset Flow
#------------------------------------------------------------

# Step 1: Validate email for password reset
@app.post("/forgotPassword/validate-email", response_model=ForgotPasswordValidationResponse)
def validate_forgot_password_email_endpoint(
    request: ForgotPasswordValidationRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Validate email for forgot password:
    1. Check email format
    2. Validate PUP domain
    3. Check if email exists in database
    4. Verify account is active and verified
    5. Return validation result
    """
    return validate_forgot_password_email(request, db)

# Step 2: Send OTP for password reset
@app.post("/forgotPassword/send-reset-otp", response_model=ForgotPasswordOTPResponse)
def send_forgot_password_otp_endpoint(
    request: ForgotPasswordOTPRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Send OTP for password reset:
    1. Validate email exists in database
    2. Check if user is a valid verified student
    3. Generate and send OTP to user's email
    4. Return OTP ID for verification
    """
    return send_forgot_password_otp(request, db)

# Step 3: Verify OTP for password reset
@app.post("/forgotPassword/verify-otp", response_model=PasswordResetOTPVerificationResponse)
def verify_password_reset_otp_endpoint(
    request: PasswordResetOTPVerificationRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Verify OTP for password reset:
    1. Verify the provided OTP code
    2. Generate a reset token for password change
    3. Return reset token for next step
    """
    return verify_password_reset_otp(request, db)

# Step 4: Reset password with token
@app.post("/forgotPassword/reset-password", response_model=ResetPasswordResponse)
def reset_password_endpoint(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Reset password with reset token:
    1. Validate reset token
    2. Validate new password requirements
    3. Update user password
    4. Return success status
    """
    return reset_password(request, db)

#------------------------------------------------------------
# JWT Helper Dependencies
#------------------------------------------------------------

# Helper function to create proper JWT dependencies
def get_jwt_student_dependency():
    """Create a proper JWT student dependency that works with FastAPI"""
    def jwt_student_dep(
        credentials: HTTPAuthorizationCredentials = Depends(JWTService.security),
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        if not credentials:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        user_data = JWTService.get_current_user_from_token(credentials.credentials, db)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        
        # Check if user is a student
        if user_data.get("role") != "Student":
            raise HTTPException(status_code=403, detail="Student access required")
        
        # Check if student number exists (confirms it's a student)
        if not user_data.get("student_number"):
            raise HTTPException(status_code=403, detail="Student account not found")
        
        return user_data
    
    return jwt_student_dep

#============================================================
# STUDENT ONBOARDING ENDPOINTS
#============================================================

#------------------------------------------------------------
# Student Onboarding Flow
#------------------------------------------------------------

# Step 1 : Check student onboarding status (using proper JWT dependency)
@app.get("/student/onboarding/status", response_model=OnboardingCheckResponse)
def check_student_onboarding_status(
    current_student: Dict[str, Any] = Depends(get_jwt_student_dependency()),
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Check student onboarding status using JWT authentication:
    1. Validate JWT token automatically
    2. Check if student has section assigned
    3. Return onboarding status and student info
    
    Requires: Authorization header with Bearer JWT token
    """
    # The current_student is already validated by the dependency
    has_section = current_student.get("has_section", False)
    
    # Prepare response
    student_info = {
        "user_id": current_student["user_id"],
        "name": current_student["name"],
        "email": current_student["email"],
        "student_number": current_student["student_number"],
        "section_id": current_student.get("section_id"),
        "has_section": has_section,
        "verified": current_student.get("verified", 0),
        "status_id": current_student.get("status_id", 1)
    }
    
    
    if not has_section:
        return OnboardingCheckResponse(
            is_onboarded=False,
            message="Student onboarding incomplete: section not assigned",
            has_section=False,
            student_info=student_info
        )
    else:
        return OnboardingCheckResponse(
        is_onboarded=True,
        message="Student onboarding complete",
        has_section=True,
        student_info=student_info
    )

# Step 2 : Getting all the available programs where isDeleted = 0
@app.get("/student/onboarding/programs", response_model=AvailableProgramsResponse)
def get_available_programs(
    current_student: Dict[str, Any] = Depends(get_jwt_student_dependency()),
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Get list of all available programs using JWT authentication:
    1. Validate JWT token automatically
    2. Return list of active programs (isDeleted = 0)
    
    Requires: Authorization header with Bearer JWT token
    """
    try:
        programs = db_query.get_active_programs(db)
        return AvailableProgramsResponse(programs=programs)
        
    except Exception as e:
        print(f"Error getting available programs: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching programs: {str(e)}")

# Step 3a: Getting all the available sections using program_id where isDeleted = 0
@app.get("/student/onboarding/sections/{program_id}", response_model=AvailableSectionsResponse)
def get_available_sections_by_program(
    program_id: int,
    current_student: Dict[str, Any] = Depends(get_jwt_student_dependency()),
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Get list of available sections for a specific program using JWT authentication:
    1. Validate JWT token automatically
    2. Return list of active sections for the given program_id (isDeleted = 0)
    
    Requires: Authorization header with Bearer JWT token
    """
    try:
        sections = db_query.get_sections_by_program(db, program_id)
        return AvailableSectionsResponse(sections=sections)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Error getting available sections for program {program_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching sections: {str(e)}")

# Step 3b: Getting all the assigned_courses using section_id where isDeleted = 0
@app.get("/student/onboarding/courses/{section_id}", response_model=AvailableCoursesResponse)
def get_available_assigned_courses_by_section(
    section_id: int,
    current_student: Dict[str, Any] = Depends(get_jwt_student_dependency()),
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Get list of assigned courses for a specific section using JWT authentication:
    1. Validate JWT token automatically
    2. Return list of active assigned courses for the given section_id (isDeleted = 0)
    
    Requires: Authorization header with Bearer JWT token
    """
    try:
        courses = db_query.get_assigned_courses_by_section(db, section_id)
        return AvailableCoursesResponse(courses=courses)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Error getting assigned courses for section {section_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching assigned courses: {str(e)}")
    
# Step 4: Assign student to Section and create Assigned_Course_Approval
@app.post("/student/onboarding/assign-section", response_model=SectionAssignmentResponse)
def assign_student_to_section_endpoint(
    request: SectionAssignmentRequest,
    current_student: Dict[str, Any] = Depends(get_jwt_student_dependency()),
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Assign student to a section and create Assigned_Course_Approval records:
    1. Validate JWT token automatically
    2. Verify section exists and is active
    3. Update student's section assignment
    4. Create pending approval records for all assigned courses in that section
    
    Requires: Authorization header with Bearer JWT token
    """
    try:
        result = assign_student_to_section(db, current_student, request.section_id)
        return SectionAssignmentResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Error assigning student to section: {e}")
        raise HTTPException(status_code=500, detail=f"Error assigning section: {str(e)}")
    

#============================================================
# STUDENT COURSES ENDPOINTS
#============================================================
# Uses the JWT dependency to ensure the student is authenticated and authorized

# 1A. Current courses: Latest academic year courses (if not graduated)
# 1B. Previous courses: All courses from previous academic years
# 1C. Map the status from assigned_course_approval table
@app.get("/student/courses", response_model=StudentCoursesResponse)
def get_student_courses(
    current_student: Dict[str, Any] = Depends(get_jwt_student_dependency()),
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Get all courses for the authenticated student with academic year-based filtering:
    1A. Current courses: Latest academic year courses (empty if graduated)
    1B. Previous courses: All courses from previous academic years
    1C. Enrollment status from assigned_course_approval table
    
    Important Validations:
    - If user status = "Graduated", no current courses are returned
    - Student number format (2023-AAA) determines enrollment year filter
    - Only courses from enrollment year onwards are included
    
    Requires: Authorization header with Bearer JWT token
    """
    try:
        # Get student courses using the database service
        courses_data = db_query.get_student_courses(db, current_student)
        
        return StudentCoursesResponse(**courses_data)
        
    except Exception as e:
        print(f"Error getting student courses: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching student courses: {str(e)}")


# 2A. Get all the student on a certain course by passing the assigned_course_id and mapping it to assigned_course_approval
# 2B. Return the student information along with their enrollment status
# 2C. Get the latest attendance record for each student in the course
# 2D. Summarize attendance data for each student
# 2E. Return the course information along with the student list and attendance summary
@app.get("/student/courses/{assigned_course_id}/students", response_model=CourseStudentsResponse)
def get_course_students(
    assigned_course_id: int,
    current_student: Dict[str, Any] = Depends(get_jwt_student_dependency()),
    db: Session = Depends(get_db),
    api_key: str = Security(get_api_key)
):
    """
    Get all students enrolled in a specific course:
    2A. Get all students for the given assigned_course_id
    2B. Return student information with enrollment status
    2C. Get latest attendance record for each student in the course
    2D. Summarize attendance data for each student
    2E. Return course information along with student list and attendance summary
    
    Requires: Authorization header with Bearer JWT token
    """
    try:
        course_students_data = db_query.get_course_students(db, assigned_course_id)
        return CourseStudentsResponse(**course_students_data)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Error getting course students: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching course students: {str(e)}")

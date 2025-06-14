from fastapi import HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models import User as UserModel, Student as StudentModel
from typing import Optional
import re

class OnboardingCheckRequest(BaseModel):
    """Request model for checking student onboarding status"""
    pass  # No body needed, auth token comes from header

class OnboardingCheckResponse(BaseModel):
    """Response model for student onboarding status"""
    is_onboarded: bool
    message: str
    has_section: bool
    student_info: Optional[dict] = None

def validate_auth_token(auth_token: str) -> Optional[int]:
    """
    Validate JWT authentication token and extract user ID
    
    Args:
        auth_token: The JWT authentication token from request header
        
    Returns:
        user_id if token is valid, None otherwise
    """
    try:
        from services.auth.jwt_service import JWTService
        
        # Use JWT service to validate token and extract user ID
        user_id = JWTService.extract_user_id(auth_token)
        return user_id
        
    except Exception as e:
        print(f"Error validating auth token: {e}")
        return None

def check_student_onboarding(
    auth_token: Optional[str],
    db: Session
) -> OnboardingCheckResponse:
    """
    Check if student has completed onboarding (has section assigned)
    
    Args:
        auth_token: JWT authentication token from request header
        db: Database session
        
    Returns:
        OnboardingCheckResponse with onboarding status
    """
    try:
        print(f"=== STUDENT ONBOARDING CHECK DEBUG ===")
        print(f"Checking onboarding status with JWT token...")
        print("=====================================")
        
        # 1. Validate authentication token
        if not auth_token:
            return OnboardingCheckResponse(
                is_onboarded=False,
                message="Authentication token is required",
                has_section=False,
                student_info=None
            )
        
        # Use JWT service to get current user data with database verification
        from services.auth.jwt_service import JWTService
        user_data = JWTService.get_current_user_from_token(auth_token, db)
        
        if not user_data:
            return OnboardingCheckResponse(
                is_onboarded=False,
                message="Invalid authentication token",
                has_section=False,
                student_info=None
            )
        
        print(f"Token validated for user ID: {user_data['user_id']}")
        
        # 2. Check if user is a student (should be handled by JWT validation, but double-check)
        if user_data.get("role") != "Student":
            return OnboardingCheckResponse(
                is_onboarded=False,
                message="Student access required",
                has_section=False,
                student_info=None
            )
        
        if not user_data.get("student_number"):
            return OnboardingCheckResponse(
                is_onboarded=False,
                message="Student account not found",
                has_section=False,
                student_info=None
            )
        
        # 3. Check if student has a section assigned
        has_section = user_data.get("has_section", False)
        
        # Prepare student info from JWT data
        student_info = {
            "user_id": user_data["user_id"],
            "name": user_data["name"],
            "email": user_data["email"],
            "student_number": user_data["student_number"],
            "section_id": user_data.get("section_id"),
            "has_section": has_section,
            "verified": user_data.get("verified", 0),
            "status_id": user_data.get("status_id", 1)
        }    
        
        # 4. Determine onboarding status
        if not has_section:
            print(f"Student {user_data['email']} has no section assigned - onboarding incomplete")
            return OnboardingCheckResponse(
                is_onboarded=False,
                message="Student onboarding incomplete: section not assigned",
                has_section=False,
                student_info=student_info
            )
        
        print(f"Student {user_data['email']} has section assigned - onboarding complete")
        return OnboardingCheckResponse(
            is_onboarded=True,
            message="Student onboarding complete",
            has_section=True,
            student_info=student_info
        )
        
    except Exception as e:
        print(f"Error checking student onboarding: {e}")
        return OnboardingCheckResponse(
            is_onboarded=False,
            message=f"Error checking onboarding status: {str(e)}",
            has_section=False,
            student_info=None
        )

# Additional helper function for reusable JWT validation
def get_current_student_from_token(auth_token: str, db: Session) -> Optional[dict]:
    """
    Reusable function to get current student from JWT token
    
    Args:
        auth_token: JWT authentication token
        db: Database session
        
    Returns:
        Student data if valid, None otherwise
    """
    try:
        from services.auth.jwt_service import JWTService
        user_data = JWTService.get_current_user_from_token(auth_token, db)
        
        if not user_data:
            return None
        
        # Verify it's a student
        if user_data.get("role") != "Student" or not user_data.get("student_number"):
            return None
        
        return user_data
        
    except Exception as e:
        print(f"Error getting current student from token: {e}")
        return None

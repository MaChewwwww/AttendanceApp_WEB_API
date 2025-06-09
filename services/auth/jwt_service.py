import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class JWTService:
    """Service for JWT token generation and validation"""
    
    # JWT Configuration from environment variables
    SECRET_KEY = os.getenv("JWT_SECRET_KEY", "attendify_jwt_fallback_secret_key_change_this_in_production")
    ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_HOURS", "24"))
    
    security = HTTPBearer()
    
    @classmethod
    def generate_token(cls, user_data: Dict[str, Any]) -> str:
        """
        Generate JWT access token for user
        
        Args:
            user_data: Dictionary containing user information
            
        Returns:
            JWT token string
        """
        try:
            # Set token expiration
            expire = datetime.utcnow() + timedelta(hours=cls.ACCESS_TOKEN_EXPIRE_HOURS)
            
            # Create token payload
            payload = {
                "user_id": user_data.get("user_id"),
                "email": user_data.get("email"),
                "role": user_data.get("role", "Student"),
                "student_number": user_data.get("student_number"),
                "exp": expire,
                "iat": datetime.utcnow(),
                "type": "access_token"
            }
            
            # Add optional fields if they exist
            if user_data.get("name"):
                payload["name"] = user_data["name"]
            if user_data.get("verified") is not None:
                payload["verified"] = user_data["verified"]
            if user_data.get("status_id"):
                payload["status_id"] = user_data["status_id"]
            
            # Generate token
            token = jwt.encode(payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
            
            print(f"✅ JWT token generated for user {user_data.get('email')} (expires in {cls.ACCESS_TOKEN_EXPIRE_HOURS} hours)")
            
            return token
            
        except Exception as e:
            print(f"Error generating JWT token: {e}")
            raise HTTPException(status_code=500, detail="Could not generate authentication token")
    
    @classmethod
    def validate_token(cls, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token and extract payload
        
        Args:
            token: JWT token string
            
        Returns:
            Token payload if valid, None if invalid
        """
        try:
            # Decode and validate token
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            
            # Check if token type is correct
            if payload.get("type") != "access_token":
                print(f"Invalid token type: {payload.get('type')}")
                return None
            
            # Check if token has required fields
            required_fields = ["user_id", "email", "exp"]
            for field in required_fields:
                if field not in payload:
                    print(f"Missing required field in token: {field}")
                    return None
            
            # Token is valid
            print(f"✅ JWT token validated for user {payload.get('email')} (ID: {payload.get('user_id')})")
            return payload
            
        except jwt.ExpiredSignatureError:
            print("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            print(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            print(f"Error validating JWT token: {e}")
            return None
    
    @classmethod
    def extract_user_id(cls, token: str) -> Optional[int]:
        """
        Extract user ID from JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            User ID if token is valid, None otherwise
        """
        payload = cls.validate_token(token)
        if payload:
            return payload.get("user_id")
        return None
    
    @classmethod
    def extract_token_from_header(cls, authorization: Optional[str]) -> Optional[str]:
        """
        Extract JWT token from Authorization header
        
        Args:
            authorization: Authorization header value
            
        Returns:
            Token string if found, None otherwise
        """
        if not authorization:
            return None
        
        # Handle Bearer token format
        if authorization.startswith("Bearer "):
            return authorization[7:]  # Remove "Bearer " prefix
        
        # Handle direct token (backward compatibility)
        return authorization
    
    @classmethod
    def get_current_user_from_token(cls, token: str, db: Session) -> Optional[Dict[str, Any]]:
        """
        Get current user data from JWT token with database verification
        
        Args:
            token: JWT token string
            db: Database session
            
        Returns:
            User data if valid, None otherwise
        """
        try:
            # Validate token
            payload = cls.validate_token(token)
            if not payload:
                return None
            
            user_id = payload.get("user_id")
            if not user_id:
                return None
            
            # Verify user still exists in database
            from models import User as UserModel, Student as StudentModel
            
            user = db.query(UserModel).filter(UserModel.id == user_id).first()
            if not user:
                print(f"User {user_id} not found in database")
                return None
            
            # Check if user is deleted
            if hasattr(user, 'isDeleted') and user.isDeleted:
                print(f"User {user_id} is deleted")
                return None
            
            # Get student data if user is a student
            student = db.query(StudentModel).filter(StudentModel.user_id == user.id).first()
            
            # Prepare user data
            user_data = {
                "user_id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "name": f"{user.first_name} {user.last_name}",
                "role": user.role,
                "verified": getattr(user, 'verified', 0),
                "status_id": getattr(user, 'status_id', 1)
            }
            
            # Add middle name if exists
            if hasattr(user, 'middle_name') and user.middle_name:
                user_data["middle_name"] = user.middle_name
            
            # Add student-specific data
            if student:
                user_data["student_number"] = student.student_number
                user_data["section_id"] = student.section
                user_data["has_section"] = student.section is not None
            
            return user_data
            
        except Exception as e:
            print(f"Error getting current user from token: {e}")
            return None

# Create properly configured dependency functions
def create_get_current_user_dependency():
    """Factory function to create get_current_user dependency with proper db injection"""
    def get_current_user_inner(
        credentials: HTTPAuthorizationCredentials = Depends(JWTService.security)
    ):
        # This is a closure that will capture the db when the dependency is used
        def get_current_user_with_db(db: Session):
            if not credentials:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            user_data = JWTService.get_current_user_from_token(credentials.credentials, db)
            if not user_data:
                raise HTTPException(status_code=401, detail="Invalid authentication token")
            
            return user_data
        
        return get_current_user_with_db
    
    return get_current_user_inner

def create_get_current_student_dependency():
    """Factory function to create get_current_student dependency with proper db injection"""
    def get_current_student_inner(
        credentials: HTTPAuthorizationCredentials = Depends(JWTService.security)
    ):
        # This is a closure that will capture the db when the dependency is used
        def get_current_student_with_db(db: Session):
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
        
        return get_current_student_with_db
    
    return get_current_student_inner

# Simple dependency functions for FastAPI (alternative approach)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(JWTService.security),
    db: Session = Depends(None)  # This will be properly injected when used
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_data = JWTService.get_current_user_from_token(credentials.credentials, db)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    return user_data

def get_current_student(
    credentials: HTTPAuthorizationCredentials = Depends(JWTService.security),
    db: Session = Depends(None)  # This will be properly injected when used
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated student
    """
    user_data = get_current_user(credentials, db)
    
    # Check if user is a student
    if user_data.get("role") != "Student":
        raise HTTPException(status_code=403, detail="Student access required")
    
    # Check if student number exists (confirms it's a student)
    if not user_data.get("student_number"):
        raise HTTPException(status_code=403, detail="Student account not found")
    
    return user_data

def validate_auth_token_header(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Simple function to extract and validate token from Authorization header
    (for backward compatibility with existing endpoints)
    
    Args:
        authorization: Authorization header value
        
    Returns:
        Token string if valid, None otherwise
    """
    if not authorization:
        return None
    
    token = JWTService.extract_token_from_header(authorization)
    if not token:
        return None
    
    # Just validate token format, don't verify content
    payload = JWTService.validate_token(token)
    return token if payload else None

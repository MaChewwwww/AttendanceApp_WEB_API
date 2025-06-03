from fastapi import Security, HTTPException, Depends, status
from fastapi.security.api_key import APIKeyHeader
from dotenv import load_dotenv
import os
from typing import Optional

# Load environment variables
load_dotenv()

# Get API key configuration from environment
API_KEY = os.getenv("API_KEY")
API_KEY_NAME = os.getenv("API_KEY_NAME", "AttendanceApp-API-Key")

if not API_KEY:
    print("Warning: API_KEY environment variable not set. API endpoints won't be protected!")

# Create API key header requirement
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(
    api_key_header: str = Security(api_key_header),
) -> Optional[str]:
    """Validate the API key provided in the header."""
    if not API_KEY:
        # If no API key is configured in environment, don't enforce it
        return None
        
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key missing. Please provide a valid API key in the AttendanceApp-API-Key header.",
            headers={"WWW-Authenticate": "AttendanceApp-API-Key"},
        )
        
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key. The provided key is not recognized.",
            headers={"WWW-Authenticate": "AttendanceApp-API-Key"},
        )
        
    return api_key_header

# Create an empty init file for the security module
with open(os.path.join(os.path.dirname(__file__), '__init__.py'), 'a'):
    pass

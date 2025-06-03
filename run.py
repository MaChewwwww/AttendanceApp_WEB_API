import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables with override=True to ensure consistency
load_dotenv(override=True)

# Get host and port from environment variables
host = os.getenv("API_HOST", "127.0.0.1")
port = int(os.getenv("API_PORT", "8000"))
env = os.getenv("ENVIRONMENT", "development")
api_key = os.getenv("API_KEY", "")
api_key_name = os.getenv("API_KEY_NAME", "AttendanceApp-API-Key")

# Determine reload setting based on environment
reload_enabled = env.lower() == "development"

if __name__ == "__main__":
    print("────────────────────────────────────────────────────")
    print(f"✓ Environment: {env}")
    print(f"✓ API server: http://{host}:{port}")
    print(f"✓ Documentation: http://{host}:{port}/docs")
    print(f"✓ Validation endpoint: http://{host}:{port}/registerStudent/validate-fields")
    
    if api_key:
        print(f"✓ API Key authentication enabled ({api_key_name})")
        # Only show API key in development mode
        if env.lower() == "development":
            masked_key = api_key[:4] + '*' * (len(api_key) - 4) if len(api_key) > 4 else '****'
            print(f"  API Key (masked): {masked_key}")
    else:
        print("⚠ Warning: API Key not configured. All endpoints are unprotected!")
        
    print("────────────────────────────────────────────────────")
    
    uvicorn.run(
        "main:app", 
        host=host, 
        port=port, 
        reload=reload_enabled,
        log_level="info"  # Changed to info to see more details
    )

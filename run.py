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
    print(f"✓ Registration Flow:")
    print(f"  • Step 1: http://{host}:{port}/registerStudent/validate-fields")
    print(f"  • Step 2: http://{host}:{port}/registerStudent/validate-face")
    print(f"  • Step 3: http://{host}:{port}/registerStudent/send-otp")
    print(f"  • Step 4: http://{host}:{port}/registerStudent/verify")
    print(f"✓ Login Flow:")
    print(f"  • Step 1: http://{host}:{port}/loginStudent/validate-fields")
    print(f"  • Step 2: http://{host}:{port}/loginStudent/send-login-otp")
    print(f"  • Step 3: http://{host}:{port}/loginStudent/verify-login-otp")
    print(f"✓ Password Reset Flow:")
    print(f"  • Step 1: http://{host}:{port}/forgotPassword/validate-email")
    print(f"  • Step 2: http://{host}:{port}/forgotPassword/send-reset-otp")
    print(f"  • Step 3: http://{host}:{port}/forgotPassword/verify-otp")
    print(f"  • Step 4: http://{host}:{port}/forgotPassword/reset-password (TODO)")
    print(f"🧹 OTP Cleanup: Automatic every 15 minutes")
    print(f"📁 Cleanup logs: logs/otp_cleanup.log")
    
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
        "main:app",  # Keep as lowercase main:app
        host=host, 
        port=port, 
        reload=reload_enabled,
        log_level="info"
    )

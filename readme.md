# AttendanceApp API

A FastAPI-based web API for the AttendanceApp, providing REST endpoints for attendance tracking functions.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
```

Edit your `.env` file to add your API key and other settings:

```properties
API_KEY=your-secret-api-key-here
API_KEY_NAME=X-API-Key  # Header name for the API key
```

```bash
# Run the API
python run.py
```

The API will be available at http://127.0.0.1:8000 with documentation at http://127.0.0.1:8000/docs

## Using the API

All protected endpoints require an API key to be passed in the header:

```
X-API-Key: your-secret-api-key-here
```

### Example with curl:

```bash
curl -X POST "http://127.0.0.1:8000/registerStudent" \
  -H "X-API-Key: your-secret-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"first_name": "John", "last_name": "Doe", ...}'
```

## Features

- Student registration with OTP verification
- Password reset and recovery system
- Face validation for registration
- Health check endpoint
- Database integration with AttendanceApp desktop application
- API key authentication
- Professional email notifications

## API Endpoints

### Health Check
- `GET /health` - Check if the API is running

### Student Registration
- `POST /registerStudent` - Register a new student (legacy)
- `POST /validate-face` - Validate if an image contains a properly visible face
- `POST /register-student-with-face` - Register a student with face validation
- `POST /registerStudent/validate-fields` - Validate registration fields
- `POST /registerStudent/validate-face` - Validate face image for registration
- `POST /registerStudent/send-otp` - Send registration OTP
- `POST /registerStudent/verify` - Complete registration with OTP verification

### Student Login
- `POST /loginStudent/validate-fields` - Validate login credentials
- `POST /loginStudent/send-login-otp` - Send login OTP
- `POST /loginStudent/verify-login-otp` - Verify OTP and complete login

### Password Reset
- `POST /forgotPassword/validate-email` - Validate email for password reset
- `POST /forgotPassword/send-reset-otp` - Send password reset OTP
- `POST /forgotPassword/verify-otp` - Verify OTP and get reset token
- `POST /forgotPassword/reset-password` - Reset password with token

## Registration Flow with OTP Verification

The API now supports a secure registration flow with OTP verification:

1. Client submits registration data and face image to `/register/init`
2. API validates the face image
3. API generates an OTP, stores registration data, and sends OTP via email
4. Client receives OTP ID in the response
5. User enters the OTP code received via email
6. Client submits OTP ID and code to `/register/verify`
7. API verifies the OTP and completes registration
8. Client receives the registration confirmation

### Example Registration Flow

#### Step 1: Initialize Registration

```bash
POST /register/init
Content-Type: application/json
AttendanceApp-API-Key: your-api-key

{
  "registration_data": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "password": "SecurePassword123",
    "student_number": "2023-12345",
    "birthday": "2000-01-15",
    "contact_number": "09123456789"
  },
  "face_image": "base64_encoded_image_data"
}
```

Response:
```json
{
  "success": true,
  "message": "OTP sent successfully. Please check your email for the verification code.",
  "otp_id": 123
}
```

#### Step 2: Verify OTP and Complete Registration

```bash
POST /register/verify
Content-Type: application/json
AttendanceApp-API-Key: your-api-key

{
  "otp_id": 123,
  "otp_code": "123456"
}
```

Response:
```json
{
  "user_id": 456,
  "name": "John Doe",
  "email": "john.doe@example.com",
  "role": "Student",
  "student_number": "2023-12345",
  "verified": 0
}
```

## Student Login Flow

The API provides a secure multi-step login system:

1. Client validates credentials with `/loginStudent/validate-fields`
2. Client requests login OTP with `/loginStudent/send-login-otp`
3. User receives OTP via email
4. Client verifies OTP with `/loginStudent/verify-login-otp` to complete login
5. Client receives user data and authentication token

### Example Login Flow

#### Step 1: Validate Credentials

```bash
POST /loginStudent/validate-fields
Content-Type: application/json
X-API-Key: your-api-key

{
  "email": "student@iskolarngbayan.pup.edu.ph",
  "password": "UserPassword123!"
}
```

Response:
```json
{
  "is_valid": true,
  "message": "Login credentials are valid",
  "errors": null
}
```

#### Step 2: Send Login OTP

```bash
POST /loginStudent/send-login-otp
Content-Type: application/json
X-API-Key: your-api-key

{
  "email": "student@iskolarngbayan.pup.edu.ph"
}
```

Response:
```json
{
  "success": true,
  "message": "Login OTP sent successfully. Please check your email for the verification code.",
  "otp_id": 456
}
```

#### Step 3: Verify OTP and Complete Login

```bash
POST /loginStudent/verify-login-otp
Content-Type: application/json
X-API-Key: your-api-key

{
  "otp_id": 456,
  "otp_code": "789012"
}
```

Response:
```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "user_id": 17,
    "name": "John Doe",
    "email": "student@iskolarngbayan.pup.edu.ph",
    "role": "Student",
    "student_number": "2023-12345",
    "verified": 1,
    "status_id": 1
  },
  "token": "temp_token_17_1749230269.123"
}
```

## Password Reset Flow

The API provides a secure password reset system:

1. Client validates email eligibility with `/forgotPassword/validate`
2. Client requests OTP with `/forgotPassword/send-otp`
3. User receives OTP via email
4. Client verifies OTP with `/forgotPassword/verify-otp` to get reset token
5. Client resets password with `/forgotPassword/reset-password`

### Example Password Reset Flow

#### Step 1: Validate Email

```bash
POST /forgotPassword/validate-email
Content-Type: application/json
X-API-Key: your-api-key

{
  "email": "student@iskolarngbayan.pup.edu.ph"
}
```

#### Step 2: Send Reset OTP

```bash
POST /forgotPassword/send-reset-otp
Content-Type: application/json
X-API-Key: your-api-key

{
  "email": "student@iskolarngbayan.pup.edu.ph"
}
```

#### Step 3: Verify OTP

```bash
POST /forgotPassword/verify-otp
Content-Type: application/json
X-API-Key: your-api-key

{
  "otp_id": 123,
  "otp_code": "654321"
}
```

#### Step 4: Reset Password

```bash
POST /forgotPassword/reset-password
Content-Type: application/json
X-API-Key: your-api-key

{
  "reset_token": "reset_17_1749230269_abc123...",
  "new_password": "NewSecurePassword123!"
}
```

## Face Validation

The API provides face validation functionality to ensure that:
- A single face is clearly visible
- Both eyes are visible (i.e., not wearing sunglasses)
- No multiple faces in the image

Example request for face validation:

```json
{
  "face_image": "base64_encoded_image_data"
}
```

Example response:

```json
{
  "is_valid": true,
  "message": "Face validation successful"
}
```

## Development

This API connects to the database from the AttendanceApp desktop application, reusing its models and database schema.

### File Structure

```
AttendanceApp_WEB_API/
├── main.py              # Main FastAPI application
├── db.py                # Database connection handling
├── models.py            # Model bridging to desktop app
├── run.py               # Helper to run the application
├── .env                 # Environment variables
├── requirements.txt     # Python dependencies
├── services/            # API services by functionality
│   ├── auth/           # Authentication-related endpoints
│   │   └── password_reset.py  # Password reset service
│   ├── email/          # Email services
│   ├── otp/            # OTP management
│   └── security/       # Security services (API key, etc.)
└── version_updates_log/ # Version history
    ├── attendify_v1.0.0.md
    └── attendify_v1.1.0.md
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

- `DB_PATH`: Path to SQLite database
- `API_HOST`: Host to bind API server
- `API_PORT`: Port for API server
- `ENVIRONMENT`: "development" or "production"
- `API_KEY`: Your secret API key
- `API_KEY_NAME`: Header name for the API key

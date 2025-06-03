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

- Student registration
- Health check endpoint
- Database integration with AttendanceApp desktop application
- API key authentication

## API Endpoints

### Health Check
- `GET /health` - Check if the API is running

### Student Registration
- `POST /registerStudent` - Register a new student
- `POST /validate-face` - Validate if an image contains a properly visible face
- `POST /register-student-with-face` - Register a student with face validation

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
├── main.py          # Main FastAPI application
├── db.py            # Database connection handling
├── models.py        # Model bridging to desktop app
├── run.py           # Helper to run the application
├── .env             # Environment variables
├── requirements.txt # Python dependencies
└── services/        # API services by functionality
    ├── auth/        # Authentication-related endpoints
    └── security/    # Security services (API key, etc.)
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

- `DB_PATH`: Path to SQLite database
- `API_HOST`: Host to bind API server
- `API_PORT`: Port for API server
- `ENVIRONMENT`: "development" or "production"
- `API_KEY`: Your secret API key
- `API_KEY_NAME`: Header name for the API key

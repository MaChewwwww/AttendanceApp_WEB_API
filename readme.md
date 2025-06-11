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

### JWT Authentication (New in v1.2.0)

Most student-specific endpoints now use JWT token authentication. After login, include the token in the Authorization header:

```
Authorization: Bearer your-jwt-token-here
```

### Example with curl:

```bash
# API Key protected endpoint
curl -X POST "http://127.0.0.1:8000/registerStudent" \
  -H "X-API-Key: your-secret-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"first_name": "John", "last_name": "Doe", ...}'

# JWT protected endpoint
curl -X GET "http://127.0.0.1:8000/student/courses" \
  -H "X-API-Key: your-secret-api-key-here" \
  -H "Authorization: Bearer your-jwt-token-here"
```

## Features

- Student registration with OTP verification
- Password reset and recovery system
- Face validation for registration
- JWT-based authentication system
- Student onboarding with section assignment
- Course management and enrollment tracking
- Attendance history and analytics
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

### Student Onboarding (🆕 v1.2.0)
- `GET /student/onboarding/status` - Check student onboarding completion status
- `GET /student/onboarding/programs` - Get available programs for selection
- `GET /student/onboarding/sections/{program_id}` - Get sections for a program
- `GET /student/onboarding/courses/{section_id}` - Get courses for a section
- `POST /student/onboarding/assign-section` - Assign student to a section

### Course Management (🆕 v1.2.0)
- `GET /student/courses` - Get student's current and previous courses
- `GET /student/courses/{assigned_course_id}/students` - Get students in a course

### Attendance Tracking (🆕 v1.2.0)
- `GET /student/attendance` - Get complete attendance history for student

## Registration Flow with OTP Verification

The API now supports a secure registration flow with OTP verification:

1. Client submits registration data and face image to `/registerStudent/send-otp`
2. API validates the face image
3. API generates an OTP, stores registration data, and sends OTP via email
4. Client receives OTP ID in the response
5. User enters the OTP code received via email
6. Client submits OTP ID and code to `/registerStudent/verify`
7. API verifies the OTP and completes registration
8. Client receives the registration confirmation

### Example Registration Flow

#### Step 1: Initialize Registration

```bash
POST /registerStudent/send-otp
Content-Type: application/json
X-API-Key: your-api-key

{
  "registration_data": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@iskolarngbayan.pup.edu.ph",
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
POST /registerStudent/verify
Content-Type: application/json
X-API-Key: your-api-key

{
  "otp_id": 123,
  "otp_code": "123456"
}
```

Response:
```json
{
  "status": "success",
  "message": "Registration completed successfully! Welcome email has been sent to your inbox.",
  "user": {
    "user_id": 456,
    "name": "John Doe",
    "email": "john.doe@iskolarngbayan.pup.edu.ph",
    "role": "Student",
    "student_number": "2023-12345",
    "verified": 1
  }
}
```

## Student Login Flow

The API provides a secure multi-step login system:

1. Client validates credentials with `/loginStudent/validate-fields`
2. Client requests login OTP with `/loginStudent/send-login-otp`
3. User receives OTP via email
4. Client verifies OTP with `/loginStudent/verify-login-otp` to complete login
5. Client receives user data and JWT authentication token

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
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

## Student Onboarding Flow (🆕 v1.2.0)

After successful registration and login, students complete onboarding by selecting their section:

### Example Onboarding Flow

#### Step 1: Check Onboarding Status

```bash
GET /student/onboarding/status
X-API-Key: your-api-key
Authorization: Bearer your-jwt-token
```

Response:
```json
{
  "is_onboarded": false,
  "message": "Student onboarding incomplete: section not assigned",
  "has_section": false,
  "student_info": {
    "user_id": 17,
    "name": "John Doe",
    "email": "student@iskolarngbayan.pup.edu.ph",
    "student_number": "2023-12345",
    "section_id": null,
    "has_section": false
  }
}
```

#### Step 2: Get Available Programs

```bash
GET /student/onboarding/programs
X-API-Key: your-api-key
Authorization: Bearer your-jwt-token
```

#### Step 3: Get Sections for Selected Program

```bash
GET /student/onboarding/sections/1
X-API-Key: your-api-key
Authorization: Bearer your-jwt-token
```

#### Step 4: Assign Student to Section

```bash
POST /student/onboarding/assign-section
Content-Type: application/json
X-API-Key: your-api-key
Authorization: Bearer your-jwt-token

{
  "section_id": 5
}
```

Response:
```json
{
  "success": true,
  "message": "Student successfully assigned to section Computer Science A",
  "student_id": 12,
  "section_id": 5,
  "section_name": "Computer Science A",
  "assigned_courses_count": 8,
  "approval_records_created": 8
}
```

## Course Management (🆕 v1.2.0)

Students can view their enrolled courses and course details:

### Get Student Courses

```bash
GET /student/courses
X-API-Key: your-api-key
Authorization: Bearer your-jwt-token
```

Response:
```json
{
  "success": true,
  "message": "Retrieved 6 current and 12 previous courses across 3 academic years",
  "student_info": {
    "user_id": 17,
    "student_id": 12,
    "name": "John Doe",
    "email": "student@iskolarngbayan.pup.edu.ph",
    "student_number": "2023-12345",
    "current_academic_year": "2024-2025"
  },
  "current_courses": [...],
  "previous_courses": [...],
  "total_current": 6,
  "total_previous": 12,
  "enrollment_summary": {
    "enrolled": 15,
    "pending": 2,
    "passed": 1
  }
}
```

### Get Students in a Course

```bash
GET /student/courses/45/students
X-API-Key: your-api-key
Authorization: Bearer your-jwt-token
```

Response:
```json
{
  "success": true,
  "message": "Retrieved 28 students for course Programming Fundamentals",
  "course_info": {
    "assigned_course_id": 45,
    "course_name": "Programming Fundamentals",
    "faculty_name": "Dr. Jane Smith",
    "section_name": "Computer Science A"
  },
  "students": [...],
  "total_students": 28,
  "enrollment_summary": {
    "enrolled": 25,
    "pending": 3
  }
}
```

## Attendance Tracking (🆕 v1.2.0)

Students can view their complete attendance history:

### Get Student Attendance

```bash
GET /student/attendance
X-API-Key: your-api-key
Authorization: Bearer your-jwt-token
```

Response:
```json
{
  "success": true,
  "message": "Retrieved 156 attendance records across 8 courses and 2 academic years",
  "student_info": {
    "user_id": 17,
    "student_id": 12,
    "name": "John Doe",
    "email": "student@iskolarngbayan.pup.edu.ph",
    "student_number": "2023-12345"
  },
  "attendance_records": [...],
  "total_records": 156,
  "attendance_summary": {
    "total_sessions": 156,
    "present_count": 142,
    "absent_count": 8,
    "late_count": 6,
    "overall_attendance_percentage": 94.87
  },
  "course_summary": {...},
  "academic_year_summary": {...}
}
```

## Password Reset Flow

The API provides a secure password reset system:

1. Client validates email eligibility with `/forgotPassword/validate-email`
2. Client requests OTP with `/forgotPassword/send-reset-otp`
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
├── Main.py              # Main FastAPI application
├── db.py                # Database connection handling
├── models.py            # Model bridging to desktop app
├── run.py               # Helper to run the application
├── .env                 # Environment variables
├── requirements.txt     # Python dependencies
├── services/            # API services by functionality
│   ├── auth/           # Authentication-related endpoints
│   │   ├── jwt_service.py      # JWT token management
│   │   ├── login.py            # Login service
│   │   ├── register.py         # Registration service
│   │   ├── password_reset.py   # Password reset service
│   │   └── onboarding.py       # Student onboarding
│   ├── database/       # Database query services
│   │   ├── read_db.py          # Database read operations
│   │   └── create_db.py        # Database write operations
│   ├── email/          # Email services
│   ├── face/           # Face recognition services
│   ├── otp/            # OTP management
│   └── security/       # Security services (API key, etc.)
└── version_updates_log/ # Version history
    ├── attendify_v1.0.0.md
    ├── attendify_v1.1.0.md
    └── attendify_v1.2.0.md
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

- `DB_PATH`: Path to SQLite database
- `API_HOST`: Host to bind API server
- `API_PORT`: Port for API server
- `ENVIRONMENT`: "development" or "production"
- `API_KEY`: Your secret API key
- `API_KEY_NAME`: Header name for the API key
- `JWT_SECRET_KEY`: Secret key for JWT token generation
- `JWT_ALGORITHM`: Algorithm for JWT tokens (default: HS256)
- `JWT_ACCESS_TOKEN_EXPIRE_HOURS`: Token expiration in hours (default: 24)

## Version History

- **v1.2.0** (December 2024): Complete student management system with JWT authentication, onboarding, course management, and attendance tracking
- **v1.1.0** (June 2025): Enhanced authentication with login system and password reset
- **v1.0.0** (Initial): Basic registration with OTP verification and face validation

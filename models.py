"""
This file imports models from the desktop application.
All model definitions come directly from the desktop application.
"""
import os
import importlib.util
from dotenv import load_dotenv

# Load environment variables with override=True to ensure consistency
load_dotenv(override=True)

# Get desktop path from environment
DESKTOP_APP_PATH = os.getenv("DESKTOP_APP_PATH")

try:
    # Import models dynamically from file path
    desktop_models_path = os.path.join(DESKTOP_APP_PATH, "models.py")
    if not os.path.exists(desktop_models_path):
        raise ImportError(f"Models file not found at {desktop_models_path}")
    
    spec = importlib.util.spec_from_file_location("desktop_models", desktop_models_path)
    desktop_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(desktop_models)
    
    # Re-export all models and classes from desktop_models
    Base = desktop_models.Base
    User = desktop_models.User
    Student = desktop_models.Student
    Faculty = desktop_models.Faculty
    Course = desktop_models.Course
    Section = desktop_models.Section
    Program = desktop_models.Program
    AttendanceLog = desktop_models.AttendanceLog
    Attendance = desktop_models.AttendanceLog  # Alias for API consistency
    Assigned_Course = desktop_models.Assigned_Course
    Status = desktop_models.Status  # Added Status model
    
    OTP_Request = desktop_models.OTP_Request  # Make sure this exists in your desktop models
    
    # Additional models for onboarding functionality
    try:
        Schedule = desktop_models.Schedule
        Assigned_Course_Approval = desktop_models.Assigned_Course_Approval
    except AttributeError:
        # These models might not exist yet in the desktop app
        Schedule = None
        Assigned_Course_Approval = None
    
except ImportError as e:
    print(f"Error importing models from desktop application: {e}")
    raise

# References This code snippet is based on the desktop application's models.py file.
# from pydantic import BaseModel
# from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, LargeBinary
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.sql import func

# Base = declarative_base()
# class Status(Base):
#     __tablename__ = "statuses"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String(50), nullable=False, unique=True)
#     description = Column(String(255), nullable=True)
#     user_type = Column(String(20), nullable=False)  # 'student' or 'faculty'
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# class User(Base):
#     __tablename__ = "users"
#     id = Column(Integer, primary_key=True, index=True)
#     first_name = Column(String(100), nullable=False)
#     last_name = Column(String(100), nullable=False)
#     email = Column(String(255), unique=True, nullable=False, index=False)
#     birthday = Column(Date, nullable=False)
#     password_hash = Column(String(255), nullable=False)
#     contact_number = Column(String(20), nullable=False)
#     role = Column(String(50), nullable=False, default="Student")
#     status_id = Column(Integer, ForeignKey("statuses.id"), nullable=True)  # Added status reference
#     face_image = Column(LargeBinary, nullable=True)  # LargeBinary (LBLOB)
#     verified = Column(Integer, nullable=False, default=0)  # 0 for False, 1 for True
#     isDeleted = Column(Integer, nullable=False, default=0)  # 0 for False, 1 for True
#     last_verified_otp = Column(DateTime, nullable=True)  # Last OTP verification time
#     last_verified_otp_expiry = Column(DateTime, nullable=True)  # Last OTP expiry time
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# class Student(Base):
#     __tablename__ = "students"
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     student_number = Column(String(50), unique=True, nullable=False)  
#     section = Column(Integer, ForeignKey("sections.id"), nullable=True)

# class Faculty(Base):
#     __tablename__ = "faculties"
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     employee_number = Column(String(50), unique=True, nullable=False)

# class OTP_Request(Base):
#     __tablename__ = "otp_requests"
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     otp_code = Column(String(6), nullable=False)  # Assuming OTP is a 6-digit code
#     type = Column(String(50), nullable=False)  # e.g., "login", "registration", "password_reset"
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     expires_at = Column(DateTime, nullable=False)  # When the OTP expires

# class Program(Base):
#     __tablename__ = "programs"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String(100), nullable=False)
#     acronym = Column(String(50), nullable=False, unique=True) 
#     code = Column(String(50), nullable=False, unique=True) 
#     description = Column(String(255), nullable=True)
#     color = Column(String(7), nullable=True)  # Hex color code like #FF5733
#     isDeleted = Column(Integer, nullable=False, default=0)  # 0 for False, 1 for True
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# class Course(Base):
#     __tablename__ = "courses"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String(100), nullable=False)
#     code = Column(String(50), nullable=True, unique=True)  # Added course code field
#     description = Column(String(255), nullable=True)
#     program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
#     isDeleted = Column(Integer, nullable=False, default=0)  # 0 for False, 1 for True
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# class Section(Base):
#     __tablename__ = "sections"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String(100), nullable=False)
#     program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
#     isDeleted = Column(Integer, nullable=False, default=0)  # 0 for False, 1 for True
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# class Assigned_Course(Base):
#     __tablename__ = "assigned_courses"
#     id = Column(Integer, primary_key=True, index=True)
#     faculty_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
#     section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
#     academic_year = Column(String(20), nullable=True)
#     semester = Column(String(20), nullable=True)
#     room = Column(String(100), nullable=True)
#     isDeleted = Column(Integer, default=0, nullable=False)
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# class Assigned_Course_Approval(Base):
#     __tablename__ = "assigned_course_approvals"
#     id = Column(Integer, primary_key=True, index=True)
#     assigned_course_id = Column(Integer, ForeignKey("assigned_courses.id"), nullable=False)
#     student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
#     status = Column(String(50), nullable=False)  # e.g., "pending", "enrolled", "rejected", "passed"
#     rejection_reason = Column(String(255), nullable=True)  # Reason for rejection, if any
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# class Schedule(Base):
#     __tablename__ = "schedules"
#     id = Column(Integer, primary_key=True, index=True)
#     assigned_course_id = Column(Integer, ForeignKey("assigned_courses.id"), nullable=False)
#     day_of_week = Column(String(50), nullable=False)  # e.g., "Monday", "Tuesday"
#     start_time = Column(DateTime, nullable=False)
#     end_time = Column(DateTime, nullable=False)
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# class AttendanceLog(Base):
#     __tablename__ = "attendance_logs"
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     assigned_course_id = Column(Integer, ForeignKey("assigned_courses.id"), nullable=False)
#     date = Column(DateTime, nullable=False)
#     image = Column(LargeBinary, nullable=True)  # Changed from LONGBLOB to LargeBinary
#     status = Column(String(50), nullable=False)  # e.g., "present", "absent", "late"
#     created_at = Column(DateTime, nullable=False, server_default=func.now())
#     updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# class LoginRequest(BaseModel):
#     email: str
#     password: str


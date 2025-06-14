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

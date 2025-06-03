"""
This file imports models from the desktop application.
All model definitions come directly from the desktop application.
"""
import os
import importlib.util
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    AssignedCourse = desktop_models.Assigned_Course
    OTP_Request = desktop_models.OTP_Request  # Make sure this exists in your desktop models
    
except ImportError as e:
    print(f"Error importing models from desktop application: {e}")
    raise

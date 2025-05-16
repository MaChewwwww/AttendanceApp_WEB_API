from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, LargeBinary
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="Student")  # Default role is 'user'
    face_image = Column(LONGBLOB, nullable=True)  # Store image as binary data
    student_number = Column(String(50), unique=True, nullable=False)  # Optional field for student number

from sqlalchemy.dialects.mysql import LONGBLOB

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False)
    image = Column(LONGBLOB, nullable=True)  # Changed from LargeBinary to LONGBLOB
    
class LoginRequest(BaseModel):
    email: str
    password: str



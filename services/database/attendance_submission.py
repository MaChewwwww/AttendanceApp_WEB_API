from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
import base64
from models import (
    Student, Assigned_Course_Approval, AttendanceLog, 
    Assigned_Course, Course, Schedule, User
)

def validate_attendance_eligibility(
    db: Session, student_data: Dict[str, Any], assigned_course_id: int
) -> Dict[str, Any]:
    """
    Validate if student can submit attendance for a specific course
    """
    try:
        student_id = student_data.get("user_id")
        
        # Get student record
        student_record = db.query(Student).filter(Student.user_id == student_id).first()
        if not student_record:
            return {
                "can_submit": False,
                "message": "Student record not found"
            }
        
        # Check if student is enrolled in the course
        enrollment = db.query(Assigned_Course_Approval).filter(
            and_(
                Assigned_Course_Approval.student_id == student_record.id,
                Assigned_Course_Approval.assigned_course_id == assigned_course_id,
                Assigned_Course_Approval.status == "enrolled"
            )
        ).first()
        
        if not enrollment:
            return {
                "can_submit": False,
                "message": "Student is not enrolled in this course"
            }
        
        # Get course information
        course_info = db.query(
            Assigned_Course.id,
            Course.name.label("course_name"),
            Course.code.label("course_code"),
            User.first_name.label("faculty_first_name"),
            User.last_name.label("faculty_last_name"),
            Assigned_Course.academic_year,
            Assigned_Course.semester,
            Assigned_Course.room
        ).select_from(Assigned_Course).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            User, Assigned_Course.faculty_id == User.id
        ).filter(Assigned_Course.id == assigned_course_id).first()
        
        if not course_info:
            return {
                "can_submit": False,
                "message": "Course not found"
            }
        
        # Check for today's schedule
        current_datetime = datetime.now()
        current_day = current_datetime.strftime("%A")
        today_date = current_datetime.date()
        
        schedule = db.query(Schedule).filter(
            and_(
                Schedule.assigned_course_id == assigned_course_id,
                Schedule.day_of_week.ilike(current_day)
            )
        ).first()
        
        if not schedule:
            return {
                "can_submit": False,
                "message": f"No class scheduled for {current_day}",
                "schedule_info": None
            }
        
        # Extract time from schedule (handle datetime objects)
        if isinstance(schedule.start_time, datetime):
            start_time = schedule.start_time.time()
            end_time = schedule.end_time.time()
        else:
            start_time = schedule.start_time
            end_time = schedule.end_time
        
        # Create today's schedule times
        today_start = datetime.combine(today_date, start_time)
        today_end = datetime.combine(today_date, end_time)
        
        # Handle overnight classes
        if end_time < start_time:
            today_end = today_end + timedelta(days=1)
        
        # Check if it's within attendance window (class time + buffer)
        attendance_buffer = timedelta(minutes=30)  # 30 minutes after class ends
        attendance_window_end = today_end + attendance_buffer
        
        if current_datetime < today_start:
            return {
                "can_submit": False,
                "message": f"Class hasn't started yet. Class starts at {start_time.strftime('%H:%M')}",
                "schedule_info": {
                    "start_time": start_time.strftime("%H:%M"),
                    "end_time": end_time.strftime("%H:%M"),
                    "status": "upcoming"
                }
            }
        
        if current_datetime > attendance_window_end:
            return {
                "can_submit": False,
                "message": f"Attendance window has closed. Class ended at {end_time.strftime('%H:%M')}",
                "schedule_info": {
                    "start_time": start_time.strftime("%H:%M"),
                    "end_time": end_time.strftime("%H:%M"),
                    "status": "completed"
                }
            }
        
        # Check if student has already submitted attendance today
        existing_attendance = db.query(AttendanceLog).filter(
            and_(
                AttendanceLog.user_id == student_id,
                AttendanceLog.assigned_course_id == assigned_course_id,
                func.date(AttendanceLog.date) == today_date
            )
        ).first()
        
        if existing_attendance:
            return {
                "can_submit": False,
                "message": f"Attendance already submitted for today (Status: {existing_attendance.status})",
                "schedule_info": {
                    "start_time": start_time.strftime("%H:%M"),
                    "end_time": end_time.strftime("%H:%M"),
                    "status": "ongoing" if current_datetime <= today_end else "completed"
                },
                "existing_attendance": {
                    "attendance_id": existing_attendance.id,
                    "status": existing_attendance.status,
                    "submitted_at": existing_attendance.created_at.isoformat() if existing_attendance.created_at else None
                }
            }
        
        # Student can submit attendance
        class_status = "ongoing" if current_datetime <= today_end else "completed"
        
        return {
            "can_submit": True,
            "message": "Student can submit attendance",
            "schedule_info": {
                "start_time": start_time.strftime("%H:%M"),
                "end_time": end_time.strftime("%H:%M"),
                "status": class_status,
                "course_name": course_info.course_name,
                "course_code": course_info.course_code,
                "faculty_name": f"{course_info.faculty_first_name} {course_info.faculty_last_name}",
                "room": course_info.room
            }
        }
        
    except Exception as e:
        print(f"Error validating attendance eligibility: {e}")
        return {
            "can_submit": False,
            "message": f"Error validating attendance: {str(e)}"
        }

def submit_student_attendance(
    db: Session, student_data: Dict[str, Any], assigned_course_id: int,
    face_image: str, latitude: Optional[float] = None, longitude: Optional[float] = None
) -> Dict[str, Any]:
    """
    Submit attendance for the student
    """
    try:
        student_id = student_data.get("user_id")
        
        print(f"DEBUG: Starting attendance submission for student {student_id}, course {assigned_course_id}")
        
        # First validate eligibility
        validation_result = validate_attendance_eligibility(db, student_data, assigned_course_id)
        if not validation_result.get("can_submit", False):
            error_msg = validation_result.get("message", "Cannot submit attendance")
            print(f"DEBUG: Validation failed: {error_msg}")
            return {"error": error_msg}
        
        # Get student record
        student_record = db.query(Student).filter(Student.user_id == student_id).first()
        if not student_record:
            print(f"DEBUG: Student record not found for user_id {student_id}")
            return {"error": "Student record not found"}
        
        # Get the LOGGED-IN USER'S face image for comparison
        # The student_id from JWT token is the user_id of the logged-in user
        from models import User as UserModel
        logged_in_user = db.query(UserModel).filter(UserModel.id == student_id).first()
        if not logged_in_user:
            print(f"DEBUG: Logged-in user record not found for user_id {student_id}")
            return {"error": "User record not found"}
        
        print(f"DEBUG: Logged-in user: {logged_in_user.first_name} {logged_in_user.last_name} (ID: {logged_in_user.id})")
        
        # Verify face against the logged-in user's stored profile image
        if logged_in_user.face_image:
            print(f"Verifying face for: {logged_in_user.first_name} {logged_in_user.last_name}")
            try:
                from services.face.face_matcher import verify_face_against_profile
                is_verified, verification_message = verify_face_against_profile(
                    logged_in_user.face_image, face_image
                )
                
                if not is_verified:
                    print(f"Face verification failed: {verification_message}")
                    return {"error": f"Face verification failed: {verification_message}"}
                
                print("Face verification successful")
                
            except Exception as face_error:
                print(f"Face verification error: {str(face_error)}")
                return {"error": f"Face verification failed due to technical error: {str(face_error)}"}
        else:
            print("No profile face image found")
            return {"error": "No profile face image found. Please upload a profile picture with your face to enable attendance submission."}
        
        # Get course and schedule information
        current_datetime = datetime.now()
        current_day = current_datetime.strftime("%A")
        today_date = current_datetime.date()
        
        schedule = db.query(Schedule).filter(
            and_(
                Schedule.assigned_course_id == assigned_course_id,
                Schedule.day_of_week.ilike(current_day)
            )
        ).first()
        
        if not schedule:
            print(f"DEBUG: No schedule found for course {assigned_course_id} on {current_day}")
            return {"error": f"No schedule found for {current_day}"}
        
        # Extract time from schedule
        if isinstance(schedule.start_time, datetime):
            start_time = schedule.start_time.time()
            end_time = schedule.end_time.time()
        else:
            start_time = schedule.start_time
            end_time = schedule.end_time
        
        # Create today's schedule times
        today_start = datetime.combine(today_date, start_time)
        today_end = datetime.combine(today_date, end_time)
        
        # Handle overnight classes
        if end_time < start_time:
            today_end = today_end + timedelta(days=1)
        
        # Determine attendance status based on time
        late_threshold = timedelta(minutes=15)  # 15 minutes late threshold
        
        if current_datetime <= today_start + late_threshold:
            attendance_status = "present"
        else:
            attendance_status = "late"
        
        print(f"DEBUG: Attendance status determined: {attendance_status}")
        
        # Convert face image to binary
        try:
            if face_image.startswith('data:image'):
                # Remove data URL prefix if present
                face_image = face_image.split(',')[1]
            face_image_binary = base64.b64decode(face_image)
            print(f"DEBUG: Face image converted to binary, size: {len(face_image_binary)} bytes")
        except Exception as e:
            print(f"DEBUG: Face image conversion failed: {str(e)}")
            return {"error": f"Invalid face image format: {str(e)}"}
        
        # Create attendance record - THIS USES THE STUDENT'S USER_ID (the logged-in user)
        print(f"DEBUG: Creating attendance record for user_id: {student_id}")
        attendance_record = AttendanceLog(
            user_id=student_id,  # This is the logged-in user's ID
            assigned_course_id=assigned_course_id,
            date=current_datetime,
            status=attendance_status,
            image=face_image_binary,
            created_at=current_datetime,
            updated_at=current_datetime
        )
        
        # Note: Latitude and longitude are not stored in the current model
        if latitude is not None or longitude is not None:
            print(f"DEBUG: Location data provided (lat: {latitude}, lng: {longitude}) but not stored in model")
        
        try:
            db.add(attendance_record)
            db.commit()
            db.refresh(attendance_record)
            print(f"DEBUG: Attendance record created with ID: {attendance_record.id}")
        except Exception as db_error:
            db.rollback()
            print(f"DEBUG: Database error: {str(db_error)}")
            return {"error": f"Database error: {str(db_error)}"}
        
        # Get course information for response
        course_info = db.query(
            Course.name.label("course_name"),
            Course.code.label("course_code"),
            User.first_name.label("faculty_first_name"),
            User.last_name.label("faculty_last_name"),
            Assigned_Course.room
        ).select_from(Assigned_Course).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            User, Assigned_Course.faculty_id == User.id
        ).filter(Assigned_Course.id == assigned_course_id).first()
        
        print(f"DEBUG: Attendance submission successful for {logged_in_user.first_name} {logged_in_user.last_name}")
        
        return {
            "success": True,
            "message": f"Attendance submitted successfully (Status: {attendance_status})",
            "attendance_id": attendance_record.id,
            "status": attendance_status,
            "submitted_at": attendance_record.created_at.isoformat(),
            "course_info": {
                "course_name": course_info.course_name if course_info else "Unknown",
                "course_code": course_info.course_code if course_info else "Unknown",
                "faculty_name": f"{course_info.faculty_first_name} {course_info.faculty_last_name}" if course_info else "Unknown",
                "room": course_info.room if course_info else "Unknown",
                "schedule": {
                    "start_time": start_time.strftime("%H:%M"),
                    "end_time": end_time.strftime("%H:%M")
                }
            }
        }
        
    except Exception as e:
        db.rollback()
        print(f"ERROR in submit_student_attendance: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error submitting attendance: {str(e)}"}

def get_today_attendance_status(db: Session, student_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get student's attendance status for today across all enrolled courses
    """
    try:
        student_id = student_data.get("user_id")
        today_date = datetime.now().date()
        current_day = datetime.now().strftime("%A")
        
        # Get student record
        student_record = db.query(Student).filter(Student.user_id == student_id).first()
        if not student_record:
            return {"error": "Student record not found"}
        
        # Get enrolled courses
        enrolled_courses = db.query(
            Assigned_Course_Approval.assigned_course_id,
            Course.name.label("course_name"),
            Course.code.label("course_code"),
            User.first_name.label("faculty_first_name"),
            User.last_name.label("faculty_last_name"),
            Assigned_Course.room
        ).select_from(Assigned_Course_Approval).join(
            Assigned_Course, Assigned_Course_Approval.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            User, Assigned_Course.faculty_id == User.id
        ).filter(
            and_(
                Assigned_Course_Approval.student_id == student_record.id,
                Assigned_Course_Approval.status == "enrolled"
            )
        ).all()
        
        courses_status = []
        
        for course in enrolled_courses:
            # Check for today's schedule
            schedule = db.query(Schedule).filter(
                and_(
                    Schedule.assigned_course_id == course.assigned_course_id,
                    Schedule.day_of_week.ilike(current_day)
                )
            ).first()
            
            # Check attendance status
            attendance = db.query(AttendanceLog).filter(
                and_(
                    AttendanceLog.user_id == student_id,
                    AttendanceLog.assigned_course_id == course.assigned_course_id,
                    func.date(AttendanceLog.date) == today_date
                )
            ).first()
            
            course_status = {
                "assigned_course_id": course.assigned_course_id,
                "course_name": course.course_name,
                "course_code": course.course_code,
                "faculty_name": f"{course.faculty_first_name} {course.faculty_last_name}",
                "room": course.room,
                "has_schedule_today": schedule is not None,
                "schedule_info": None,
                "attendance_submitted": attendance is not None,
                "attendance_info": None
            }
            
            if schedule:
                # Extract time from schedule
                if isinstance(schedule.start_time, datetime):
                    start_time = schedule.start_time.time()
                    end_time = schedule.end_time.time()
                else:
                    start_time = schedule.start_time
                    end_time = schedule.end_time
                
                course_status["schedule_info"] = {
                    "start_time": start_time.strftime("%H:%M"),
                    "end_time": end_time.strftime("%H:%M")
                }
            
            if attendance:
                course_status["attendance_info"] = {
                    "attendance_id": attendance.id,
                    "status": attendance.status,
                    "submitted_at": attendance.created_at.isoformat() if attendance.created_at else None
                }
            
            courses_status.append(course_status)
        
        return {
            "success": True,
            "message": f"Today's attendance status retrieved for {current_day}",
            "date": today_date.isoformat(),
            "day": current_day,
            "student_info": {
                "user_id": student_id,
                "name": student_data.get("name"),
                "student_number": student_data.get("student_number")
            },
            "courses": courses_status,
            "total_courses": len(courses_status),
            "courses_with_schedule": len([c for c in courses_status if c["has_schedule_today"]]),
            "attendance_submitted": len([c for c in courses_status if c["attendance_submitted"]])
        }
        
    except Exception as e:
        print(f"Error getting today's attendance status: {e}")
        return {"error": f"Error getting today's attendance status: {str(e)}"}

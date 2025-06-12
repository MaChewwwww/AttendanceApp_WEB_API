from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
import base64  # Ensure base64 is imported at module level
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
    Submit attendance for the student with class-wide attendance management
    """
    try:
        student_id = student_data.get("user_id")
        
        print(f"DEBUG: Starting attendance submission for student {student_id}, course {assigned_course_id}")
        
        # Check if this is a faculty member or student
        # First check if this user is the faculty for this course
        faculty_check = db.query(Assigned_Course).filter(
            and_(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.faculty_id == student_id
            )
        ).first()
        
        is_faculty = faculty_check is not None
        print(f"DEBUG: User is faculty for this course: {is_faculty}")
        
        if is_faculty:
            # Handle faculty attendance submission
            return submit_faculty_attendance(db, student_data, assigned_course_id, face_image, latitude, longitude)
        else:
            # Handle student attendance submission (existing logic)
            return submit_regular_student_attendance(db, student_data, assigned_course_id, face_image, latitude, longitude)
            
    except Exception as e:
        db.rollback()
        print(f"ERROR in submit_student_attendance: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error submitting attendance: {str(e)}"}

def submit_faculty_attendance(
    db: Session, faculty_data: Dict[str, Any], assigned_course_id: int,
    face_image: str, latitude: Optional[float] = None, longitude: Optional[float] = None
) -> Dict[str, Any]:
    """
    Submit attendance for faculty member
    """
    try:
        faculty_id = faculty_data.get("user_id")
        
        print(f"DEBUG: Starting faculty attendance submission for faculty {faculty_id}, course {assigned_course_id}")
        
        # Verify this user is actually the faculty for this course
        faculty_course = db.query(Assigned_Course).filter(
            and_(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.faculty_id == faculty_id
            )
        ).first()
        
        if not faculty_course:
            return {"error": "You are not the assigned faculty for this course"}
        
        # Get faculty user record
        from models import User as UserModel
        faculty_user = db.query(UserModel).filter(UserModel.id == faculty_id).first()
        if not faculty_user:
            return {"error": "Faculty user record not found"}
        
        print(f"DEBUG: Faculty user: {faculty_user.first_name} {faculty_user.last_name} (ID: {faculty_user.id})")
        
        # Face verification (same as student)
        if faculty_user.face_image:
            print(f"Verifying face for faculty: {faculty_user.first_name} {faculty_user.last_name}")
            print(f"DEBUG: Faculty stored face image size: {len(faculty_user.face_image)} bytes")
            
            # JPEG debugging for faculty too
            try:
                header_check = faculty_user.face_image[:10]
                print(f"DEBUG: Faculty image header: {[hex(b) for b in header_check]}")
                
                if faculty_user.face_image[:2] == b'\xff\xd8':
                    print("DEBUG: Faculty image is JPEG format")
                elif faculty_user.face_image[:8] == b'\x89PNG\r\n\x1a\n':
                    print("DEBUG: Faculty image is PNG format")
                else:
                    print("DEBUG: Faculty image format unknown")
                    
            except Exception as header_error:
                print(f"DEBUG: Header check failed: {header_error}")
            
            try:
                # Test if we can decode the stored image first
                import numpy as np
                import cv2
                test_array = np.frombuffer(faculty_user.face_image, np.uint8)
                test_image = cv2.imdecode(test_array, cv2.IMREAD_COLOR)
                
                if test_image is None:
                    print("DEBUG: Cannot decode faculty stored face image")
                    return {"error": "Profile face image is corrupted. Please re-upload your profile picture."}
                
                print(f"DEBUG: Faculty stored image validation passed, shape: {test_image.shape}")
                
                # Now proceed with face verification
                from services.face.face_matcher import verify_face_against_profile
                is_verified, verification_message = verify_face_against_profile(
                    faculty_user.face_image, face_image
                )
                
                if not is_verified:
                    print(f"Faculty face verification failed: {verification_message}")
                    return {"error": f"Face verification failed: {verification_message}"}
                
                print("Faculty face verification successful")
                
            except Exception as face_error:
                print(f"Faculty face verification error: {str(face_error)}")
                import traceback
                traceback.print_exc()
                return {"error": f"Face verification failed due to technical error: {str(face_error)}"}
        else:
            print("No faculty profile face image found")
            return {"error": "No profile face image found. Please upload a profile picture to enable attendance submission."}
        
        # Get schedule information
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
            return {"error": f"No schedule found for {current_day}"}
        
        # Check if faculty already submitted attendance today
        existing_faculty_attendance = db.query(AttendanceLog).filter(
            and_(
                AttendanceLog.user_id == faculty_id,
                AttendanceLog.assigned_course_id == assigned_course_id,
                func.date(AttendanceLog.date) == today_date
            )
        ).first()
        
        # Convert face image to binary
        try:
            if face_image.startswith('data:image'):
                face_image = face_image.split(',')[1]
            face_image_binary = base64.b64decode(face_image)
        except Exception as e:
            return {"error": f"Invalid face image format: {str(e)}"}
        
        # Faculty is always marked as "present" (no late threshold for faculty)
        attendance_status = "present"
        
        if existing_faculty_attendance:
            # Update existing faculty attendance
            if existing_faculty_attendance.status == "present":
                return {"error": "Faculty attendance already submitted for today. Cannot submit again."}
            else:
                # Update from "absent" to "present"
                print(f"DEBUG: Updating faculty attendance from {existing_faculty_attendance.status} to {attendance_status}")
                existing_faculty_attendance.status = attendance_status
                existing_faculty_attendance.image = face_image_binary
                existing_faculty_attendance.updated_at = current_datetime
                
                try:
                    db.commit()
                    db.refresh(existing_faculty_attendance)
                    print(f"DEBUG: Faculty attendance record updated with ID: {existing_faculty_attendance.id}")
                except Exception as db_error:
                    db.rollback()
                    return {"error": f"Database error: {str(db_error)}"}
                
                return {
                    "success": True,
                    "message": f"Faculty attendance updated successfully (Status: {attendance_status})",
                    "attendance_id": existing_faculty_attendance.id,
                    "status": attendance_status,
                    "submitted_at": existing_faculty_attendance.updated_at.isoformat(),
                    "course_info": {
                        "course_name": "Faculty Attendance",
                        "role": "Faculty"
                    }
                }
        else:
            # Create new faculty attendance record
            faculty_record = AttendanceLog(
                user_id=faculty_id,
                assigned_course_id=assigned_course_id,
                date=current_datetime,
                status=attendance_status,
                image=face_image_binary,
                created_at=current_datetime,
                updated_at=current_datetime
            )
            
            try:
                db.add(faculty_record)
                db.commit()
                db.refresh(faculty_record)
                print(f"DEBUG: Faculty attendance record created with ID: {faculty_record.id}")
            except Exception as db_error:
                db.rollback()
                return {"error": f"Database error: {str(db_error)}"}
            
            return {
                "success": True,
                "message": f"Faculty attendance submitted successfully (Status: {attendance_status})",
                "attendance_id": faculty_record.id,
                "status": attendance_status,
                "submitted_at": faculty_record.created_at.isoformat(),
                "course_info": {
                    "course_name": "Faculty Attendance",
                    "role": "Faculty"
                }
            }
        
    except Exception as e:
        db.rollback()
        print(f"ERROR in submit_faculty_attendance: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error submitting faculty attendance: {str(e)}"}

def submit_regular_student_attendance(
    db: Session, student_data: Dict[str, Any], assigned_course_id: int,
    face_image: str, latitude: Optional[float] = None, longitude: Optional[float] = None
) -> Dict[str, Any]:
    """
    Submit attendance for regular student (renamed from original function)
    """
    try:
        student_id = student_data.get("user_id")
        
        # First validate eligibility
        validation_result = validate_attendance_eligibility(db, student_data, assigned_course_id)
        if not validation_result.get("can_submit", False):
            error_msg = validation_result.get("message", "Cannot submit attendance")
            print(f"DEBUG: Validation failed: {error_msg}")
            return {"error": error_msg}
        
        # Get student record
        student_record = db.query(Student).filter(Student.user_id == student_id).first()
        if not student_record:
            return {"error": "Student record not found"}
        
        # Get the LOGGED-IN USER'S face image for comparison
        from models import User as UserModel
        logged_in_user = db.query(UserModel).filter(UserModel.id == student_id).first()
        if not logged_in_user:
            print(f"DEBUG: Logged-in user record not found for user_id {student_id}")
            return {"error": "User record not found"}
        
        print(f"DEBUG: Logged-in user: {logged_in_user.first_name} {logged_in_user.last_name} (ID: {logged_in_user.id})")
        
        # Verify face against the logged-in user's stored profile image
        if logged_in_user.face_image:
            print(f"Verifying face for: {logged_in_user.first_name} {logged_in_user.last_name}")
            print(f"DEBUG: Stored face image size: {len(logged_in_user.face_image)} bytes")
            
            # DETAILED ANALYSIS OF THE STORED IMAGE PROBLEM
            print(f"=== STORED IMAGE ANALYSIS ===")
            print(f"Image length: {len(logged_in_user.face_image)}")
            print(f"First 20 bytes (raw): {logged_in_user.face_image[:20]}")
            print(f"First 20 bytes (hex): {logged_in_user.face_image[:20].hex()}")
            print(f"First 50 chars (repr): {repr(logged_in_user.face_image[:50])}")
            
            # Check if it looks like text/base64
            try:
                first_chars = logged_in_user.face_image[:100].decode('utf-8', errors='ignore')
                print(f"As UTF-8 text: {repr(first_chars)}")
                if 'PNG' in first_chars or 'JPEG' in first_chars or 'data:' in first_chars:
                    print("WARNING: Stored image appears to be text/base64, not binary!")
            except:
                print("Cannot decode as UTF-8 - likely binary data")
            
            # Check for common image signatures
            if logged_in_user.face_image.startswith(b'data:image'):
                print("ERROR: Stored image is a data URI! Should be binary.")
                return {"error": "Profile image corrupted - stored as text instead of binary. Please re-upload your profile picture."}
            elif logged_in_user.face_image.startswith(b'/9j/'):
                print("ERROR: Stored image is base64 encoded! Should be binary.")
                return {"error": "Profile image corrupted - stored as base64 instead of binary. Please re-upload your profile picture."}
            elif logged_in_user.face_image[:2] == b'\xff\xd8':
                print("OK: JPEG binary signature detected")
                image_format = "JPEG"
            elif logged_in_user.face_image[:8] == b'\x89PNG\r\n\x1a\n':
                print("OK: PNG binary signature detected")
                image_format = "PNG"
            else:
                print(f"UNKNOWN: Unrecognized image format")
                # Try to see if it's corrupted base64 or text
                try:
                    # Maybe it's corrupted base64 without proper padding
                    test_decode = base64.b64decode(logged_in_user.face_image + b'==')
                    print(f"Could be corrupted base64 - decoded size: {len(test_decode)}")
                    if test_decode[:2] == b'\xff\xd8' or test_decode[:8] == b'\x89PNG\r\n\x1a\n':
                        print("FOUND: Image was stored as base64 text instead of binary!")
                        return {"error": "Profile image corrupted - stored as base64 text. Please re-upload your profile picture."}
                except:
                    pass
                
                return {"error": "Profile image format not recognized. Please re-upload your profile picture in JPEG or PNG format."}
            print(f"========================")
            
            try:
                # Test decoding with multiple methods and better error handling
                import numpy as np
                import cv2
                test_array = np.frombuffer(logged_in_user.face_image, np.uint8)
                test_image = cv2.imdecode(test_array, cv2.IMREAD_COLOR)
                
                if test_image is None:
                    print(f"DEBUG: Primary decode failed for {image_format}, trying alternatives...")
                    # Try with different flags
                    test_image = cv2.imdecode(test_array, cv2.IMREAD_UNCHANGED)
                    if test_image is not None:
                        print(f"DEBUG: Alternative decode succeeded for {image_format}")
                        # Handle different channel configurations
                        if len(test_image.shape) == 3:
                            if test_image.shape[2] == 4:
                                test_image = cv2.cvtColor(test_image, cv2.COLOR_RGBA2BGR)
                                print("DEBUG: Converted RGBA to BGR")
                            elif test_image.shape[2] == 3:
                                print("DEBUG: 3-channel image, keeping as-is")
                        elif len(test_image.shape) == 2:
                            test_image = cv2.cvtColor(test_image, cv2.COLOR_GRAY2BGR)
                            print("DEBUG: Converted grayscale to BGR")
                    else:
                        # Try base64 decode (in case of double encoding)
                        try:
                            decoded_bytes = base64.b64decode(logged_in_user.face_image)
                            alt_array = np.frombuffer(decoded_bytes, np.uint8)
                            test_image = cv2.imdecode(alt_array, cv2.IMREAD_COLOR)
                            if test_image is not None:
                                print("DEBUG: Base64 decode succeeded - image was double-encoded")
                        except Exception as b64_error:
                            print(f"DEBUG: Base64 decode failed: {b64_error}")
                        
                        # Try PIL as last resort
                        if test_image is None:
                            try:
                                from PIL import Image
                                import io
                                pil_image = Image.open(io.BytesIO(logged_in_user.face_image))
                                test_image = np.array(pil_image)
                                if len(test_image.shape) == 3 and test_image.shape[2] == 3:
                                    test_image = cv2.cvtColor(test_image, cv2.COLOR_RGB2BGR)
                                print(f"DEBUG: PIL decode succeeded for {image_format}")
                            except Exception as pil_error:
                                print(f"DEBUG: PIL decode failed: {pil_error}")
                
                if test_image is None:
                    print(f"DEBUG: All decode attempts failed for {image_format} - image corrupted")
                    return {"error": f"Profile face image is corrupted or in unsupported format ({image_format}). Please re-upload your profile picture as JPEG or PNG."}
                
                print(f"DEBUG: Stored {image_format} image validation passed, shape: {test_image.shape}, dtype: {test_image.dtype}")
                
                # Now proceed with face verification
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
                import traceback
                traceback.print_exc()
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
                face_image = face_image.split(',')[1]
            face_image_binary = base64.b64decode(face_image)
            print(f"DEBUG: Face image converted to binary, size: {len(face_image_binary)} bytes")
        except Exception as e:
            print(f"DEBUG: Face image conversion failed: {str(e)}")
            return {"error": f"Invalid face image format: {str(e)}"}
        
        # Check if current user already has attendance record
        user_existing_attendance = db.query(AttendanceLog).filter(
            and_(
                AttendanceLog.user_id == student_id,
                AttendanceLog.assigned_course_id == assigned_course_id,
                func.date(AttendanceLog.date) == today_date
            )
        ).first()
        
        if user_existing_attendance:
            # User already has attendance - check if we can update it
            if user_existing_attendance.status in ["present", "late"]:
                # Student already submitted with present/late status - cannot submit again
                return {
                    "error": f"Attendance already submitted for today (Status: {user_existing_attendance.status}). Cannot submit again."
                }
            elif user_existing_attendance.status == "absent":
                # Update from "absent" to current status (classmate scenario)
                print(f"DEBUG: Classmate updating attendance from 'absent' to {attendance_status}")
                user_existing_attendance.status = attendance_status
                user_existing_attendance.image = face_image_binary
                user_existing_attendance.updated_at = current_datetime
                
                try:
                    db.commit()
                    db.refresh(user_existing_attendance)
                    print(f"DEBUG: Classmate attendance record updated with ID: {user_existing_attendance.id}")
                except Exception as db_error:
                    db.rollback()
                    print(f"DEBUG: Database error updating classmate attendance: {str(db_error)}")
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
                
                return {
                    "success": True,
                    "message": f"Attendance submitted successfully (Status: {attendance_status})",
                    "attendance_id": user_existing_attendance.id,
                    "status": attendance_status,
                    "submitted_at": user_existing_attendance.updated_at.isoformat(),
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
            else:
                # Some other status - shouldn't happen but handle gracefully
                print(f"DEBUG: Unexpected attendance status: {user_existing_attendance.status}")
                return {"error": f"Unexpected attendance status: {user_existing_attendance.status}"}
        
        # No existing attendance record - create new one
        print("DEBUG: No existing attendance record found, creating new record")
        
        # Check if any attendance records exist for this course today
        existing_attendance_count = db.query(AttendanceLog).filter(
            and_(
                AttendanceLog.assigned_course_id == assigned_course_id,
                func.date(AttendanceLog.date) == today_date
            )
        ).count()
        
        print(f"DEBUG: Total existing attendance records for today: {existing_attendance_count}")
        
        if existing_attendance_count == 0:
            # This is the FIRST submission for the day - create records for everyone
            print("DEBUG: First attendance submission for today - creating records for all participants")
            
            # Get all ENROLLED students for this course
            enrolled_students = db.query(
                Assigned_Course_Approval.student_id,
                Student.user_id,
                User.first_name,
                User.last_name
            ).select_from(Assigned_Course_Approval).join(
                Student, Assigned_Course_Approval.student_id == Student.id
            ).join(
                User, Student.user_id == User.id
            ).filter(
                and_(
                    Assigned_Course_Approval.assigned_course_id == assigned_course_id,
                    Assigned_Course_Approval.status == "enrolled"  # Only enrolled students
                )
            ).all()
            
            # Get faculty for this course (direct assignment, no approval needed)
            faculty_info = db.query(
                Assigned_Course.faculty_id,
                User.first_name.label("faculty_first_name"),
                User.last_name.label("faculty_last_name")
            ).select_from(Assigned_Course).join(
                User, Assigned_Course.faculty_id == User.id
            ).filter(Assigned_Course.id == assigned_course_id).first()
            
            print(f"DEBUG: Found {len(enrolled_students)} enrolled students and 1 faculty for course {assigned_course_id}")
            
            attendance_records = []
            submitter_record = None
            
            # Create attendance records for all participants
            for enrollment in enrolled_students:
                if enrollment.user_id == student_id:
                    # This is the submitter - set to present/late with face image
                    record = AttendanceLog(
                        user_id=enrollment.user_id,
                        assigned_course_id=assigned_course_id,
                        date=current_datetime,
                        status=attendance_status,
                        image=face_image_binary,
                        created_at=current_datetime,
                        updated_at=current_datetime
                    )
                    submitter_record = record
                    print(f"DEBUG: Creating submitter record for {enrollment.first_name} {enrollment.last_name} (user_id: {enrollment.user_id}) - Status: {attendance_status}")
                else:
                    # Other enrolled students - set to absent with no image (they can update this later)
                    record = AttendanceLog(
                        user_id=enrollment.user_id,
                        assigned_course_id=assigned_course_id,
                        date=current_datetime,
                        status="absent",  # Default to absent - they can update when they submit
                        image=None,
                        created_at=current_datetime,
                        updated_at=current_datetime
                    )
                    print(f"DEBUG: Creating absent record for {enrollment.first_name} {enrollment.last_name} (user_id: {enrollment.user_id}) - Can be updated later")
                attendance_records.append(record)
            
            # Create attendance record for faculty (always set to absent initially)
            if faculty_info:
                faculty_record = AttendanceLog(
                    user_id=faculty_info.faculty_id,
                    assigned_course_id=assigned_course_id,
                    date=current_datetime,
                    status="absent",  # Faculty default to absent
                    image=None,
                    created_at=current_datetime,
                    updated_at=current_datetime
                )
                attendance_records.append(faculty_record)
                print(f"DEBUG: Creating absent record for faculty {faculty_info.faculty_first_name} {faculty_info.faculty_last_name} (user_id: {faculty_info.faculty_id})")
            
            # Bulk insert all attendance records
            try:
                db.add_all(attendance_records)
                db.commit()
                print(f"DEBUG: Successfully created {len(attendance_records)} attendance records")
                print(f"DEBUG: Submitter's attendance record ID: {submitter_record.id if submitter_record else 'Not found'}")
            except Exception as db_error:
                db.rollback()
                print(f"DEBUG: Database error creating bulk attendance: {str(db_error)}")
                return {"error": f"Database error: {str(db_error)}"}
            
            # Verify submitter record was created
            if not submitter_record:
                print(f"ERROR: Submitter record not found in enrolled students!")
                return {"error": "Submitter is not enrolled in this course"}
            
        else:
            # Attendance records already exist but this student doesn't have one yet
            # This shouldn't happen if the first submission created records for everyone,
            # but handle it gracefully
            print("DEBUG: Attendance records exist but student doesn't have one - creating individual record")
            submitter_record = AttendanceLog(
                user_id=student_id,
                assigned_course_id=assigned_course_id,
                date=current_datetime,
                status=attendance_status,
                image=face_image_binary,
                created_at=current_datetime,
                updated_at=current_datetime
            )
            
            try:
                db.add(submitter_record)
                db.commit()
                db.refresh(submitter_record)
                print(f"DEBUG: Individual attendance record created with ID: {submitter_record.id}")
            except Exception as db_error:
                db.rollback()
                print(f"DEBUG: Database error creating individual attendance: {str(db_error)}")
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
            "attendance_id": submitter_record.id if submitter_record else None,
            "status": attendance_status,
            "submitted_at": submitter_record.created_at.isoformat() if submitter_record else current_datetime.isoformat(),
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

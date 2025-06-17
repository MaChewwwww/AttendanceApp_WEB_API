from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Optional
import base64

from models import (
    User, Faculty, Assigned_Course, Course, Section, Program, 
    Schedule, AttendanceLog
)

def validate_faculty_attendance_eligibility(
    db: Session, 
    current_faculty: Dict[str, Any], 
    assigned_course_id: int
) -> Dict[str, Any]:
    """
    Validate if faculty can submit attendance for a specific course
    
    Args:
        db: Database session
        current_faculty: Current faculty data from JWT
        assigned_course_id: ID of the assigned course
        
    Returns:
        Dictionary containing validation result
    """
    try:
        faculty_user_id = current_faculty.get("user_id")
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        current_day = current_datetime.strftime("%A")
        
        # 1. Check if faculty is assigned to teach this course
        assigned_course = db.query(Assigned_Course).filter(
            and_(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.isDeleted == 0
            )
        ).first()
        
        if not assigned_course:
            return {
                "can_submit": False,
                "message": "You are not authorized to submit attendance for this course",
                "schedule_info": None,
                "existing_attendance": None
            }
        
        # 2. Get course information
        course_info = db.query(
            Course.name.label("course_name"),
            Course.code.label("course_code"),
            Section.name.label("section_name"),
            Program.name.label("program_name"),
            Program.acronym.label("program_acronym")
        ).select_from(Course).join(
            Section, Assigned_Course.section_id == Section.id
        ).join(
            Program, Section.program_id == Program.id
        ).filter(
            Course.id == assigned_course.course_id
        ).first()
        
        # 3. Check for existing attendance today
        existing_attendance = db.query(AttendanceLog).filter(
            and_(
                AttendanceLog.user_id == faculty_user_id,
                AttendanceLog.assigned_course_id == assigned_course_id,
                func.date(AttendanceLog.date) == current_date
            )
        ).first()
        
        if existing_attendance:
            return {
                "can_submit": False,
                "message": f"You have already submitted attendance for {course_info.course_name} today",
                "schedule_info": None,
                "existing_attendance": {
                    "attendance_id": existing_attendance.id,
                    "status": existing_attendance.status,
                    "submitted_at": existing_attendance.created_at.isoformat() if existing_attendance.created_at else None
                }
            }
        
        # 4. Check if there's a schedule for today
        schedule_query = db.query(Schedule).filter(
            and_(
                Schedule.assigned_course_id == assigned_course_id,
                Schedule.day_of_week.ilike(f"%{current_day}%")
            )
        ).first()
        
        if not schedule_query:
            return {
                "can_submit": False,
                "message": f"No class scheduled for {current_day} in {course_info.course_name}",
                "schedule_info": None,
                "existing_attendance": None
            }
        
        # 5. Check if the class is ongoing or within submission window
        start_datetime = schedule_query.start_time if isinstance(schedule_query.start_time, datetime) else schedule_query.start_time
        end_datetime = schedule_query.end_time if isinstance(schedule_query.end_time, datetime) else schedule_query.end_time
        
        # Extract time portion
        if isinstance(start_datetime, datetime):
            start_time = start_datetime.time()
        else:
            start_time = start_datetime
            
        if isinstance(end_datetime, datetime):
            end_time = end_datetime.time()
        else:
            end_time = end_datetime
        
        # Create datetime objects for comparison
        today_start = datetime.combine(current_date, start_time)
        today_end = datetime.combine(current_date, end_time)
        
        # Handle overnight classes
        if end_time < start_time:
            today_end = today_end + timedelta(days=1)
        
        # Allow submission from 15 minutes before class until 30 minutes after class ends
        submission_start = today_start - timedelta(minutes=15)
        submission_end = today_end + timedelta(minutes=30)
        
        schedule_info = {
            "schedule_id": schedule_query.id,
            "day_of_week": schedule_query.day_of_week,
            "start_time": start_time.strftime("%H:%M") if start_time else None,
            "end_time": end_time.strftime("%H:%M") if end_time else None,
            "course_name": course_info.course_name,
            "course_code": course_info.course_code,
            "section_name": course_info.section_name,
            "program_name": course_info.program_name,
            "room": assigned_course.room
        }
        
        if current_datetime < submission_start:
            return {
                "can_submit": False,
                "message": f"Attendance submission for {course_info.course_name} will open 15 minutes before class starts at {start_time.strftime('%H:%M')}",
                "schedule_info": schedule_info,
                "existing_attendance": None
            }
        
        if current_datetime > submission_end:
            return {
                "can_submit": False,
                "message": f"Attendance submission window for {course_info.course_name} has closed (ended 30 minutes after class)",
                "schedule_info": schedule_info,
                "existing_attendance": None
            }
        
        # Determine status based on time
        status = "present"
        if current_datetime > today_end:
            status = "late"
        
        return {
            "can_submit": True,
            "message": f"You can submit attendance for {course_info.course_name}. Status will be: {status}",
            "schedule_info": schedule_info,
            "existing_attendance": None
        }
        
    except Exception as e:
        print(f"Error validating faculty attendance eligibility: {e}")
        return {
            "can_submit": False,
            "message": f"Error validating attendance eligibility: {str(e)}",
            "schedule_info": None,
            "existing_attendance": None
        }

def submit_faculty_attendance(
    db: Session,
    current_faculty: Dict[str, Any],
    assigned_course_id: int,
    face_image: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None
) -> Dict[str, Any]:
    """
    Submit faculty attendance for a specific course
    
    Args:
        db: Database session
        current_faculty: Current faculty data from JWT
        assigned_course_id: ID of the assigned course
        face_image: Base64 encoded face image
        latitude: GPS latitude (optional)
        longitude: GPS longitude (optional)
        
    Returns:
        Dictionary containing submission result
    """
    try:
        faculty_user_id = current_faculty.get("user_id")
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        current_day = current_datetime.strftime("%A")
        
        # 1. Validate eligibility first
        validation_result = validate_faculty_attendance_eligibility(db, current_faculty, assigned_course_id)
        
        if not validation_result.get("can_submit", False):
            return {"error": validation_result.get("message", "Cannot submit attendance")}
        
        # 2. Get assigned course information
        assigned_course = db.query(Assigned_Course).filter(
            and_(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.isDeleted == 0
            )
        ).first()
        
        if not assigned_course:
            return {"error": "Course assignment not found"}
        
        # 3. Get schedule information to determine status
        schedule_query = db.query(Schedule).filter(
            and_(
                Schedule.assigned_course_id == assigned_course_id,
                Schedule.day_of_week.ilike(f"%{current_day}%")
            )
        ).first()
        
        # 4. Determine attendance status based on time
        status = "present"  # Default status
        
        if schedule_query:
            start_datetime = schedule_query.start_time if isinstance(schedule_query.start_time, datetime) else schedule_query.start_time
            end_datetime = schedule_query.end_time if isinstance(schedule_query.end_time, datetime) else schedule_query.end_time
            
            # Extract time portion
            if isinstance(start_datetime, datetime):
                start_time = start_datetime.time()
            else:
                start_time = start_datetime
                
            if isinstance(end_datetime, datetime):
                end_time = end_datetime.time()
            else:
                end_time = end_datetime
            
            # Create datetime objects for comparison
            today_start = datetime.combine(current_date, start_time)
            today_end = datetime.combine(current_date, end_time)
            
            # Handle overnight classes
            if end_time < start_time:
                today_end = today_end + timedelta(days=1)
            
            # Determine status: late if after class ends
            if current_datetime > today_end:
                status = "late"
        
        # 5. Convert face image from base64 to binary
        try:
            face_image_binary = base64.b64decode(face_image)
        except Exception as decode_error:
            return {"error": f"Invalid face image format: {str(decode_error)}"}
        
        # 6. Create attendance record
        attendance_record = AttendanceLog(
            user_id=faculty_user_id,
            assigned_course_id=assigned_course_id,
            date=current_datetime,
            image=face_image_binary,
            status=status,
            created_at=current_datetime,
            updated_at=current_datetime
        )
        
        db.add(attendance_record)
        db.commit()
        db.refresh(attendance_record)
        
        # 7. Get course information for response
        course_info = db.query(
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            Course.code.label("course_code"),
            Section.name.label("section_name"),
            Program.name.label("program_name"),
            Program.acronym.label("program_acronym")
        ).select_from(Course).join(
            Section, Assigned_Course.section_id == Section.id
        ).join(
            Program, Section.program_id == Program.id
        ).filter(
            Course.id == assigned_course.course_id
        ).first()
        
        return {
            "success": True,
            "message": f"Faculty attendance submitted successfully for {course_info.course_name}",
            "attendance_id": attendance_record.id,
            "status": status,
            "submitted_at": current_datetime.isoformat(),
            "course_info": {
                "course_id": course_info.course_id,
                "course_name": course_info.course_name,
                "course_code": course_info.course_code,
                "section_name": course_info.section_name,
                "program_name": course_info.program_name,
                "program_acronym": course_info.program_acronym,
                "academic_year": assigned_course.academic_year,
                "semester": assigned_course.semester,
                "room": assigned_course.room
            }
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error submitting faculty attendance: {e}")
        return {"error": f"Failed to submit attendance: {str(e)}"}

def get_faculty_today_attendance_status(
    db: Session, 
    current_faculty: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get faculty's attendance status for today across all assigned courses
    
    Args:
        db: Database session
        current_faculty: Current faculty data from JWT
        
    Returns:
        Dictionary containing today's attendance status
    """
    try:
        faculty_user_id = current_faculty.get("user_id")
        current_date = datetime.now().date()
        current_day = datetime.now().strftime("%A")
        
        # Get all courses assigned to faculty
        assigned_courses_query = db.query(
            Assigned_Course.id.label("assigned_course_id"),
            Assigned_Course.academic_year,
            Assigned_Course.semester,
            Assigned_Course.room,
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            Course.code.label("course_code"),
            Section.name.label("section_name"),
            Program.name.label("program_name"),
            Program.acronym.label("program_acronym")
        ).select_from(Assigned_Course).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            Section, Assigned_Course.section_id == Section.id
        ).join(
            Program, Section.program_id == Program.id
        ).filter(
            and_(
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0,
                Section.isDeleted == 0,
                Program.isDeleted == 0
            )
        ).all()
        
        # Get today's schedules for these courses
        assigned_course_ids = [course.assigned_course_id for course in assigned_courses_query]
        
        today_schedules = []
        if assigned_course_ids:
            schedules_query = db.query(Schedule).filter(
                and_(
                    Schedule.assigned_course_id.in_(assigned_course_ids),
                    Schedule.day_of_week.ilike(f"%{current_day}%")
                )
            ).all()
            
            for schedule in schedules_query:
                # Find corresponding course info
                course_info = next(
                    (c for c in assigned_courses_query if c.assigned_course_id == schedule.assigned_course_id), 
                    None
                )
                
                if course_info:
                    today_schedules.append({
                        "schedule_id": schedule.id,
                        "assigned_course_id": schedule.assigned_course_id,
                        "course_name": course_info.course_name,
                        "course_code": course_info.course_code,
                        "section_name": course_info.section_name,
                        "program_acronym": course_info.program_acronym,
                        "room": course_info.room,
                        "start_time": schedule.start_time.strftime("%H:%M") if schedule.start_time else None,
                        "end_time": schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
                        "academic_year": course_info.academic_year,
                        "semester": course_info.semester
                    })
        
        # Get today's attendance records for faculty
        today_attendance = db.query(AttendanceLog).filter(
            and_(
                AttendanceLog.user_id == faculty_user_id,
                AttendanceLog.assigned_course_id.in_(assigned_course_ids) if assigned_course_ids else False,
                func.date(AttendanceLog.date) == current_date
            )
        ).all()
        
        # Map attendance to courses
        attendance_by_course = {att.assigned_course_id: att for att in today_attendance}
        
        # Prepare response data
        courses_status = []
        for schedule in today_schedules:
            assigned_course_id = schedule["assigned_course_id"]
            attendance = attendance_by_course.get(assigned_course_id)
            
            course_status = {
                "assigned_course_id": assigned_course_id,
                "course_name": schedule["course_name"],
                "course_code": schedule["course_code"],
                "section_name": schedule["section_name"],
                "program_acronym": schedule["program_acronym"],
                "room": schedule["room"],
                "start_time": schedule["start_time"],
                "end_time": schedule["end_time"],
                "academic_year": schedule["academic_year"],
                "semester": schedule["semester"],
                "has_attendance": attendance is not None,
                "attendance_status": attendance.status if attendance else None,
                "attendance_time": attendance.created_at.strftime("%H:%M") if attendance and attendance.created_at else None,
                "attendance_id": attendance.id if attendance else None
            }
            
            courses_status.append(course_status)
        
        # Prepare faculty info
        faculty_user = db.query(User).filter(User.id == faculty_user_id).first()
        faculty_record = db.query(Faculty).filter(Faculty.user_id == faculty_user_id).first()
        
        faculty_info = {
            "user_id": faculty_user_id,
            "name": f"{faculty_user.first_name} {faculty_user.last_name}" if faculty_user else current_faculty.get("name"),
            "email": faculty_user.email if faculty_user else current_faculty.get("email"),
            "employee_number": faculty_record.employee_number if faculty_record else None
        }
        
        # Calculate summary
        total_classes_today = len(today_schedules)
        attended_classes = len([c for c in courses_status if c["has_attendance"]])
        pending_classes = total_classes_today - attended_classes
        
        return {
            "success": True,
            "message": f"Faculty attendance status for {current_date}",
            "faculty_info": faculty_info,
            "date": current_date.isoformat(),
            "day": current_day,
            "courses": courses_status,
            "summary": {
                "total_classes_today": total_classes_today,
                "attended_classes": attended_classes,
                "pending_classes": pending_classes,
                "attendance_rate": round((attended_classes / total_classes_today * 100), 2) if total_classes_today > 0 else 0
            }
        }
        
    except Exception as e:
        print(f"Error getting faculty today attendance status: {e}")
        return {
            "success": False,
            "message": f"Error getting today's attendance status: {str(e)}",
            "faculty_info": {},
            "date": current_date.isoformat() if 'current_date' in locals() else None,
            "day": current_day if 'current_day' in locals() else None,
            "courses": [],
            "summary": {
                "total_classes_today": 0,
                "attended_classes": 0,
                "pending_classes": 0,
                "attendance_rate": 0
            }
        }

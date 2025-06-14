from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, extract
from models import (
    Assigned_Course, Course, Section, Program, Faculty, User, Student, 
    Assigned_Course_Approval, AttendanceLog
)
from typing import Dict, Any, List, Optional
from datetime import datetime, date

def get_faculty_course_attendance_records(
    db: Session, 
    current_faculty: Dict[str, Any], 
    assigned_course_id: int,
    academic_year: Optional[str] = None,
    month: Optional[int] = None,
    day: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get attendance records for a specific course with optional filtering.
    
    Args:
        db: Database session
        current_faculty: Current faculty user data from JWT
        assigned_course_id: ID of the assigned course
        academic_year: Optional filter by academic year
        month: Optional filter by month (1-12)
        day: Optional filter by day (1-31)
        
    Returns:
        Dict containing course attendance records and metadata
    """
    try:
        print(f"=== FACULTY COURSE ATTENDANCE DEBUG ===")
        print(f"Faculty User ID: {current_faculty.get('user_id')}")
        print(f"Assigned Course ID: {assigned_course_id}")
        print(f"Filters - Academic Year: {academic_year}, Month: {month}, Day: {day}")
        
        # Get faculty record
        faculty_query = db.query(Faculty).filter(Faculty.user_id == current_faculty["user_id"]).first()
        if not faculty_query:
            return {"error": "Faculty not found"}
        
        faculty_user_id = current_faculty["user_id"]
        
        # Get course information and verify faculty ownership
        course_query = db.query(
            Assigned_Course,
            Course,
            Section,
            Program,
            User.id.label("faculty_user_id"),
            User.first_name.label("faculty_first_name"),
            User.last_name.label("faculty_last_name"),
            User.email.label("faculty_email")
        ).join(
            Course, Course.id == Assigned_Course.course_id
        ).join(
            Section, Section.id == Assigned_Course.section_id
        ).join(
            Program, Program.id == Section.program_id
        ).join(
            User, User.id == Assigned_Course.faculty_id
        ).filter(
            and_(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.isDeleted == 0
            )
        ).first()
        
        if not course_query:
            return {"error": "Course not found or you don't have permission to access this course"}
        
        (assigned_course, course, section, program, 
         faculty_user_id, faculty_first_name, faculty_last_name, faculty_email) = course_query
        
        print(f"✓ Course found: {course.name}")
        
        # Prepare course information
        course_info = {
            "assigned_course_id": assigned_course.id,
            "course_id": course.id,
            "course_name": course.name,
            "course_code": course.code,
            "course_description": course.description,
            "academic_year": assigned_course.academic_year,
            "semester": assigned_course.semester,
            "room": assigned_course.room
        }
        
        # Prepare section information
        section_info = {
            "section_id": section.id,
            "section_name": section.name,
            "program_id": section.program_id,
            "program_name": program.name,
            "program_acronym": program.acronym
        }
        
        # Prepare faculty information
        faculty_info = {
            "faculty_id": faculty_query.id,
            "user_id": faculty_user_id,
            "name": f"{faculty_first_name} {faculty_last_name}",
            "email": faculty_email,
            "employee_number": faculty_query.employee_number
        }
        
        # Determine if this is a current course
        current_year = datetime.now().year
        course_year = None
        if assigned_course.academic_year and '-' in assigned_course.academic_year:
            course_year = int(assigned_course.academic_year.split('-')[0])
        
        is_current_course = course_year == current_year if course_year else False
        
        # Build attendance query with filters
        attendance_query = db.query(
            AttendanceLog,
            Student,
            User,
            Assigned_Course_Approval.status.label("enrollment_status")
        ).join(
            User, User.id == AttendanceLog.user_id
        ).join(
            Student, Student.user_id == User.id
        ).outerjoin(
            Assigned_Course_Approval,
            and_(
                Assigned_Course_Approval.student_id == Student.id,
                Assigned_Course_Approval.assigned_course_id == assigned_course_id
            )
        ).filter(
            AttendanceLog.assigned_course_id == assigned_course_id
        )
        
        # Apply filters
        if academic_year:
            # Filter by academic year (assuming academic year format is "2023-2024")
            if '-' in academic_year:
                year = int(academic_year.split('-')[0])
                attendance_query = attendance_query.filter(
                    extract('year', AttendanceLog.date) == year
                )
        
        if month:
            attendance_query = attendance_query.filter(
                extract('month', AttendanceLog.date) == month
            )
        
        if day:
            attendance_query = attendance_query.filter(
                extract('day', AttendanceLog.date) == day
            )
        
        # Order by date and time (most recent first)
        attendance_query = attendance_query.order_by(
            desc(AttendanceLog.date),
            desc(AttendanceLog.created_at)
        )
        
        attendance_results = attendance_query.all()
        
        print(f"✓ Found {len(attendance_results)} attendance records")
        
        # Process attendance records
        attendance_records = []
        for attendance, student, user, enrollment_status in attendance_results:
            # Extract time from created_at or use a default
            attendance_time = None
            if attendance.created_at:
                attendance_time = attendance.created_at.strftime("%H:%M:%S")
            
            attendance_record = {
                "attendance_id": attendance.id,
                "student_id": student.id,
                "user_id": user.id,
                "student_number": student.student_number,
                "student_name": f"{user.first_name} {user.last_name}",
                "student_email": user.email,
                "attendance_date": attendance.date.isoformat() if attendance.date else None,
                "attendance_time": attendance_time,
                "status": attendance.status,
                "has_image": bool(attendance.image),
                "enrollment_status": enrollment_status or "attending",
                "created_at": attendance.created_at.isoformat() if attendance.created_at else None,
                "updated_at": attendance.updated_at.isoformat() if attendance.updated_at else None
            }
            attendance_records.append(attendance_record)
        
        # Calculate attendance summary
        total_records = len(attendance_records)
        present_count = sum(1 for record in attendance_records if record["status"] == "present")
        late_count = sum(1 for record in attendance_records if record["status"] == "late")
        absent_count = sum(1 for record in attendance_records if record["status"] == "absent")
        
        attendance_summary = {
            "total_records": total_records,
            "present_count": present_count,
            "late_count": late_count,
            "absent_count": absent_count,
            "attendance_rate": round((present_count + late_count) / total_records * 100, 2) if total_records > 0 else 0.0
        }
        
        # Get available filter options
        available_filters = get_available_filter_options(db, assigned_course_id)
        
        print(f"✓ Attendance summary: {attendance_summary}")
        print(f"✓ Available filters: {available_filters}")
        
        return {
            "success": True,
            "message": "Course attendance records retrieved successfully",
            "course_info": course_info,
            "section_info": section_info,
            "faculty_info": faculty_info,
            "attendance_records": attendance_records,
            "total_records": total_records,
            "attendance_summary": attendance_summary,
            "academic_year": assigned_course.academic_year,
            "semester": assigned_course.semester,
            "is_current_course": is_current_course,
            "available_filters": available_filters
        }
        
    except Exception as e:
        print(f"ERROR in get_faculty_course_attendance_records: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Database error: {str(e)}"}

def get_available_filter_options(db: Session, assigned_course_id: int) -> Dict[str, List[str]]:
    """
    Get available filter options for the course attendance.
    
    Args:
        db: Database session
        assigned_course_id: ID of the assigned course
        
    Returns:
        Dict containing available years, months, and days
    """
    try:
        # Get distinct years from attendance records
        years_query = db.query(
            extract('year', AttendanceLog.date).label('year')
        ).filter(
            AttendanceLog.assigned_course_id == assigned_course_id
        ).distinct().all()
        
        available_years = [str(int(year.year)) for year in years_query if year.year]
        
        # Get distinct months from attendance records
        months_query = db.query(
            extract('month', AttendanceLog.date).label('month')
        ).filter(
            AttendanceLog.assigned_course_id == assigned_course_id
        ).distinct().all()
        
        available_months = [str(int(month.month)) for month in months_query if month.month]
        
        # Get distinct days from attendance records
        days_query = db.query(
            extract('day', AttendanceLog.date).label('day')
        ).filter(
            AttendanceLog.assigned_course_id == assigned_course_id
        ).distinct().all()
        
        available_days = [str(int(day.day)) for day in days_query if day.day]
        
        return {
            "years": sorted(available_years, reverse=True),  # Most recent first
            "months": sorted(available_months),
            "days": sorted(available_days)
        }
        
    except Exception as e:
        print(f"Error getting available filter options: {str(e)}")
        return {
            "years": [],
            "months": [],
            "days": []
        }

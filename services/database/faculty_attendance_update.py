"""
Faculty Attendance Update Service
Handles updating attendance status for faculty users
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import Dict, Any
from models import AttendanceLog, Assigned_Course, Faculty, User, Student, Course, Section, Program

def update_attendance_status_record(
    db: Session, 
    current_faculty: Dict[str, Any], 
    assigned_course_id: int, 
    attendance_id: int, 
    new_status: str
) -> Dict[str, Any]:
    """
    Update attendance status for a specific attendance record
    
    Args:
        db: Database session
        current_faculty: Current faculty user data from JWT
        assigned_course_id: ID of the assigned course
        attendance_id: ID of the attendance record to update
        new_status: New status value ("present", "absent", "late")
    
    Returns:
        Dict containing update result or error
    """
    try:
        print(f"=== ATTENDANCE UPDATE DEBUG ===")
        print(f"Faculty ID: {current_faculty.get('user_id')}")
        print(f"Assigned Course ID: {assigned_course_id}")
        print(f"Attendance ID: {attendance_id}")
        print(f"New Status: {new_status}")
        print("===============================")
        
        # 1. Validate new status
        valid_statuses = ["present", "absent", "late"]
        if new_status not in valid_statuses:
            return {
                "error": f"Invalid status '{new_status}'. Must be one of: {', '.join(valid_statuses)}"
            }
        
        # 2. Get faculty record
        faculty = db.query(Faculty).filter(Faculty.user_id == current_faculty["user_id"]).first()
        if not faculty:
            return {"error": "Faculty record not found"}
        
        # 3. Verify faculty has permission to modify this course
        assigned_course = db.query(Assigned_Course).filter(
            and_(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.faculty_id == current_faculty["user_id"],
                Assigned_Course.isDeleted == 0
            )
        ).first()
        
        if not assigned_course:
            return {"error": "Course not found or you don't have permission to modify this course"}
        
        # 4. Get the attendance record and verify it belongs to this course
        attendance_record = db.query(AttendanceLog).filter(
            and_(
                AttendanceLog.id == attendance_id,
                AttendanceLog.assigned_course_id == assigned_course_id
            )
        ).first()
        
        if not attendance_record:
            return {"error": "Attendance record not found for this course"}
        
        # 5. Store old status for response
        old_status = attendance_record.status
        
        # 6. Check if status is actually changing
        if old_status == new_status:
            return {"error": f"Attendance status is already '{new_status}'"}
        
        # 7. Update the attendance record
        attendance_record.status = new_status
        attendance_record.updated_at = datetime.now()
        
        # 8. Get student and course information for response
        student_user = db.query(User).filter(User.id == attendance_record.user_id).first()
        student = db.query(Student).filter(Student.user_id == attendance_record.user_id).first()
        course = db.query(Course).filter(Course.id == assigned_course.course_id).first()
        section = db.query(Section).filter(Section.id == assigned_course.section_id).first()
        program = db.query(Program).filter(Program.id == section.program_id if section else None).first()
        
        # 9. Commit the changes
        db.commit()
        
        print(f"Attendance status updated: {old_status} -> {new_status}")
        
        # 10. Prepare response data
        student_info = None
        if student_user and student:
            student_info = {
                "student_id": student.id,
                "user_id": student_user.id,
                "student_number": student.student_number,
                "name": f"{student_user.first_name} {student_user.last_name}",
                "email": student_user.email
            }
        
        course_info = None
        if course:
            course_info = {
                "assigned_course_id": assigned_course.id,
                "course_id": course.id,
                "course_name": course.name,
                "course_code": course.code,
                "section_name": section.name if section else "Unknown",
                "program_name": program.name if program else "Unknown",
                "academic_year": assigned_course.academic_year,
                "semester": assigned_course.semester
            }
        
        return {
            "success": True,
            "message": f"Attendance status updated successfully from '{old_status}' to '{new_status}'",
            "attendance_id": attendance_id,
            "old_status": old_status,
            "new_status": new_status,
            "updated_at": attendance_record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "student_info": student_info,
            "course_info": course_info
        }
        
    except Exception as e:
        print(f"Error in update_attendance_status_record: {str(e)}")
        db.rollback()
        return {"error": f"Failed to update attendance status: {str(e)}"}

def validate_faculty_course_permission(
    db: Session, 
    faculty_user_id: int, 
    assigned_course_id: int
) -> bool:
    """
    Validate if faculty has permission to modify a specific course
    
    Args:
        db: Database session
        faculty_user_id: Faculty user ID
        assigned_course_id: ID of the assigned course
    
    Returns:
        Boolean indicating if faculty has permission
    """
    try:
        assigned_course = db.query(Assigned_Course).filter(
            and_(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.isDeleted == 0
            )
        ).first()
        
        return assigned_course is not None
        
    except Exception as e:
        print(f"Error validating faculty course permission: {str(e)}")
        return False

def get_attendance_record_info(
    db: Session, 
    attendance_id: int, 
    assigned_course_id: int
) -> Dict[str, Any]:
    """
    Get detailed information about an attendance record
    
    Args:
        db: Database session
        attendance_id: ID of the attendance record
        assigned_course_id: ID of the assigned course
    
    Returns:
        Dict containing attendance record information or error
    """
    try:
        # Query with joins to get comprehensive information
        result = db.query(
            AttendanceLog,
            User,
            Student,
            Course,
            Section,
            Program,
            Assigned_Course
        ).join(
            User, AttendanceLog.user_id == User.id
        ).join(
            Student, Student.user_id == User.id
        ).join(
            Assigned_Course, AttendanceLog.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            Section, Assigned_Course.section_id == Section.id
        ).join(
            Program, Section.program_id == Program.id
        ).filter(
            and_(
                AttendanceLog.id == attendance_id,
                AttendanceLog.assigned_course_id == assigned_course_id
            )
        ).first()
        
        if not result:
            return {"error": "Attendance record not found"}
        
        attendance, user, student, course, section, program, assigned_course = result
        
        return {
            "attendance_id": attendance.id,
            "status": attendance.status,
            "date": attendance.date.strftime("%Y-%m-%d"),
            "student_info": {
                "student_id": student.id,
                "user_id": user.id,
                "student_number": student.student_number,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email
            },
            "course_info": {
                "assigned_course_id": assigned_course.id,
                "course_id": course.id,
                "course_name": course.name,
                "course_code": course.code,
                "section_name": section.name,
                "program_name": program.name,
                "academic_year": assigned_course.academic_year,
                "semester": assigned_course.semester
            }
        }
        
    except Exception as e:
        print(f"Error getting attendance record info: {str(e)}")
        return {"error": f"Failed to get attendance record information: {str(e)}"}

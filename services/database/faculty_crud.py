from sqlalchemy.orm import Session
from sqlalchemy import func, select, join, and_, or_
from typing import Dict, List, Any
from datetime import datetime
from models import (
    User, Faculty, Assigned_Course, Course, Section, Program,
    Assigned_Course_Approval, AttendanceLog, Status, Student
)

def get_faculty_courses(db: Session, faculty_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all courses assigned to a faculty member with detailed information
    
    Args:
        db: Database session
        faculty_data: Faculty user data from JWT token
        
    Returns:
        Dictionary with faculty courses data formatted for FacultyCoursesResponse
    """
    try:
        user_id = faculty_data.get('user_id')
        if not user_id:
            raise ValueError("Invalid faculty data - user_id not found")
        
        # Get faculty record
        faculty = db.query(Faculty).filter(Faculty.user_id == user_id).first()
        if not faculty:
            raise ValueError("Faculty record not found")
        
        # Get user record
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User record not found")
        
        # Get latest academic year/semester
        latest = db.query(Assigned_Course).filter(
            Assigned_Course.faculty_id == user_id,
            Assigned_Course.isDeleted == 0
        ).order_by(
            Assigned_Course.academic_year.desc(),
            Assigned_Course.semester.desc()
        ).first()
        
        current_academic_year = latest.academic_year if latest else None
        current_semester = latest.semester if latest else None
        
        # Query all assigned courses with joins
        courses = db.query(
            Assigned_Course, Course, Section, Program
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            Section, Assigned_Course.section_id == Section.id
        ).join(
            Program, Course.program_id == Program.id
        ).filter(
            Assigned_Course.faculty_id == user_id,
            Assigned_Course.isDeleted == 0,
            Course.isDeleted == 0,
            Section.isDeleted == 0,
            Program.isDeleted == 0
        ).all()
        
        # Prepare course lists and summary
        current_courses = []
        previous_courses = []
        semester_summary = {}
        
        for assigned, course, section, program in courses:
            # Get enrollment counts
            enrollment_counts = db.query(
                func.count().label('total'),
                func.sum(case((Assigned_Course_Approval.status == 'enrolled', 1), else_=0)).label('enrolled'),
                func.sum(case((Assigned_Course_Approval.status == 'pending', 1), else_=0)).label('pending')
            ).filter(
                Assigned_Course_Approval.assigned_course_id == assigned.id
            ).first()
            
            # Get total students in section
            total_students = db.query(func.count(Student.id)).filter(
                Student.section == section.id,
                Student.user_id == User.id,
                User.isDeleted == 0
            ).scalar()
            
            course_info = {
                "assigned_course_id": assigned.id,
                "course_id": course.id,
                "course_name": course.name,
                "course_code": course.code,
                "course_description": course.description,
                "section_id": section.id,
                "section_name": section.name,
                "program_id": program.id,
                "program_name": program.name,
                "program_acronym": program.acronym,
                "academic_year": assigned.academic_year,
                "semester": assigned.semester,
                "room": assigned.room,
                "enrollment_count": enrollment_counts.enrolled or 0,
                "pending_count": enrollment_counts.pending or 0,
                "total_students": total_students or 0,
                "created_at": assigned.created_at.isoformat() if assigned.created_at else None,
                "updated_at": assigned.updated_at.isoformat() if assigned.updated_at else None
            }
            
            # Track semester summary
            sem_key = f"{assigned.academic_year}-{assigned.semester}"
            if sem_key not in semester_summary:
                semester_summary[sem_key] = {
                    "total_courses": 0,
                    "total_students": 0,
                    "academic_year": assigned.academic_year,
                    "semester": assigned.semester
                }
            semester_summary[sem_key]["total_courses"] += 1
            semester_summary[sem_key]["total_students"] += enrollment_counts.enrolled or 0
            
            # Sort into current/previous courses
            if (assigned.academic_year == current_academic_year and 
                assigned.semester == current_semester):
                current_courses.append(course_info)
            else:
                previous_courses.append(course_info)
        
        # Sort courses by creation date
        current_courses.sort(key=lambda x: x["created_at"] or "", reverse=True)
        previous_courses.sort(key=lambda x: x["created_at"] or "", reverse=True)
        
        return {
            "success": True,
            "message": "Faculty courses retrieved successfully",
            "faculty_info": {
                "user_id": user.id,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "employee_number": faculty.employee_number,
                "role": user.role,
                "verified": user.verified,
                "status_id": user.status_id,
                "current_academic_year": current_academic_year,
                "current_semester": current_semester,
                "total_assigned_courses": len(courses)
            },
            "current_courses": current_courses,
            "previous_courses": previous_courses,
            "total_current": len(current_courses),
            "total_previous": len(previous_courses),
            "semester_summary": semester_summary
        }
        
    except Exception as e:
        print(f"Error in get_faculty_courses: {e}")
        import traceback
        traceback.print_exc()
        raise

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from models import (
    Assigned_Course, Course, Section, Program, Faculty, User, Student, 
    Assigned_Course_Approval, Attendance
)
from typing import Dict, Any, List
from datetime import datetime, date

def get_faculty_course_details(db: Session, current_faculty: Dict[str, Any], assigned_course_id: int) -> Dict[str, Any]:
    """
    Get comprehensive details about a specific course for faculty including students and attendance.
    
    Args:
        db: Database session
        current_faculty: Current faculty user data from JWT
        assigned_course_id: ID of the assigned course
        
    Returns:
        Dict containing course details, students, and attendance data
    """
    try:
        # Get faculty ID from the current faculty data
        faculty_query = db.query(Faculty).filter(Faculty.user_id == current_faculty["user_id"]).first()
        if not faculty_query:
            return {"error": "Faculty not found"}
        
        faculty_id = faculty_query.faculty_id
        
        # Get course information and verify faculty ownership
        course_query = db.query(
            Assigned_Course,
            Course,
            Section,
            Program,
            Faculty,
            User
        ).join(
            Course, Course.course_id == Assigned_Course.course_id
        ).join(
            Section, Section.section_id == Assigned_Course.section_id
        ).join(
            Program, Program.program_id == Section.program_id
        ).join(
            Faculty, Faculty.faculty_id == Assigned_Course.faculty_id
        ).join(
            User, User.user_id == Faculty.user_id
        ).filter(
            and_(
                Assigned_Course.assigned_course_id == assigned_course_id,
                Assigned_Course.faculty_id == faculty_id,
                Assigned_Course.isDeleted == 0
            )
        ).first()
        
        if not course_query:
            return {"error": "Course not found or you don't have permission to access this course"}
        
        assigned_course, course, section, program, faculty, faculty_user = course_query
        
        # Prepare course information
        course_info = {
            "assigned_course_id": assigned_course.assigned_course_id,
            "course_id": course.course_id,
            "course_name": course.course_name,
            "course_code": course.course_code,
            "course_description": course.course_description,
            "academic_year": assigned_course.academic_year,
            "semester": assigned_course.semester,
            "room": assigned_course.room,
            "created_at": assigned_course.created_at.isoformat() if assigned_course.created_at else None,
            "updated_at": assigned_course.updated_at.isoformat() if assigned_course.updated_at else None
        }
        
        # Prepare section information
        section_info = {
            "section_id": section.section_id,
            "section_name": section.section_name,
            "year_level": section.year_level,
            "max_students": section.max_students
        }
        
        # Prepare faculty information
        faculty_info = {
            "faculty_id": faculty.faculty_id,
            "user_id": faculty_user.user_id,
            "name": f"{faculty_user.first_name} {faculty_user.last_name}",
            "email": faculty_user.email,
            "employee_number": faculty.employee_number
        }
        
        # Get all students in this course with their enrollment status
        students_query = db.query(
            Student,
            User,
            Assigned_Course_Approval
        ).join(
            User, User.user_id == Student.user_id
        ).join(
            Assigned_Course_Approval, 
            Assigned_Course_Approval.student_id == Student.student_id
        ).filter(
            and_(
                Assigned_Course_Approval.assigned_course_id == assigned_course_id,
                Student.isDeleted == 0,
                User.isDeleted == 0
            )
        ).all()
        
        # Process students by enrollment status
        enrolled_students = []
        pending_students = []
        rejected_students = []
        
        enrollment_summary = {
            "enrolled": 0,
            "pending": 0,
            "rejected": 0,
            "total": 0
        }
        
        for student, user, approval in students_query:
            # Get attendance summary for this student
            attendance_stats = db.query(
                func.count(Attendance.attendance_id).label("total_sessions"),
                func.sum(func.case([(Attendance.status == "present", 1)], else_=0)).label("present_count"),
                func.sum(func.case([(Attendance.status == "absent", 1)], else_=0)).label("absent_count"),
                func.sum(func.case([(Attendance.status == "late", 1)], else_=0)).label("late_count")
            ).filter(
                and_(
                    Attendance.student_id == student.student_id,
                    Attendance.assigned_course_id == assigned_course_id
                )
            ).first()
            
            # Get latest attendance
            latest_attendance = db.query(Attendance).filter(
                and_(
                    Attendance.student_id == student.student_id,
                    Attendance.assigned_course_id == assigned_course_id
                )
            ).order_by(desc(Attendance.attendance_date), desc(Attendance.created_at)).first()
            
            # Calculate statistics
            total_sessions = attendance_stats.total_sessions or 0
            present_count = int(attendance_stats.present_count or 0)
            absent_count = int(attendance_stats.absent_count or 0)
            late_count = int(attendance_stats.late_count or 0)
            
            # Calculate attendance percentage
            if total_sessions > 0:
                attendance_percentage = round((present_count + late_count) / total_sessions * 100, 2)
            else:
                attendance_percentage = 0.0
            
            # Determine failed status (you can adjust this logic)
            failed_count = 1 if attendance_percentage < 75 else 0  # 75% minimum attendance requirement
            
            student_info = {
                "student_id": student.student_id,
                "user_id": user.user_id,
                "student_number": student.student_number,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "enrollment_status": approval.status,
                "rejection_reason": approval.rejection_reason,
                "enrollment_created_at": approval.created_at.isoformat() if approval.created_at else None,
                "enrollment_updated_at": approval.updated_at.isoformat() if approval.updated_at else None,
                "total_sessions": total_sessions,
                "present_count": present_count,
                "absent_count": absent_count,
                "late_count": late_count,
                "failed_count": failed_count,
                "attendance_percentage": attendance_percentage,
                "latest_attendance_date": latest_attendance.attendance_date.isoformat() if latest_attendance and latest_attendance.attendance_date else None,
                "latest_attendance_status": latest_attendance.status if latest_attendance else None
            }
            
            # Categorize by enrollment status
            if approval.status == "enrolled":
                enrolled_students.append(student_info)
                enrollment_summary["enrolled"] += 1
            elif approval.status == "pending":
                pending_students.append(student_info)
                enrollment_summary["pending"] += 1
            elif approval.status == "rejected":
                rejected_students.append(student_info)
                enrollment_summary["rejected"] += 1
            
            enrollment_summary["total"] += 1
        
        # Get recent attendance records (last 10 records)
        recent_attendance_query = db.query(
            Attendance,
            Student,
            User
        ).join(
            Student, Student.student_id == Attendance.student_id
        ).join(
            User, User.user_id == Student.user_id
        ).filter(
            Attendance.assigned_course_id == assigned_course_id
        ).order_by(
            desc(Attendance.attendance_date),
            desc(Attendance.created_at)
        ).limit(20).all()
        
        recent_attendance = []
        for attendance, student, user in recent_attendance_query:
            recent_attendance.append({
                "attendance_id": attendance.attendance_id,
                "student_id": student.student_id,
                "student_name": f"{user.first_name} {user.last_name}",
                "student_number": student.student_number,
                "attendance_date": attendance.attendance_date.isoformat() if attendance.attendance_date else None,
                "status": attendance.status,
                "has_image": bool(attendance.face_image),
                "created_at": attendance.created_at.isoformat() if attendance.created_at else None,
                "updated_at": attendance.updated_at.isoformat() if attendance.updated_at else None
            })
        
        # Calculate overall attendance summary
        total_attendance_records = db.query(func.count(Attendance.attendance_id)).filter(
            Attendance.assigned_course_id == assigned_course_id
        ).scalar() or 0
        
        overall_present = db.query(func.count(Attendance.attendance_id)).filter(
            and_(
                Attendance.assigned_course_id == assigned_course_id,
                Attendance.status == "present"
            )
        ).scalar() or 0
        
        overall_late = db.query(func.count(Attendance.attendance_id)).filter(
            and_(
                Attendance.assigned_course_id == assigned_course_id,
                Attendance.status == "late"
            )
        ).scalar() or 0
        
        overall_absent = db.query(func.count(Attendance.attendance_id)).filter(
            and_(
                Attendance.assigned_course_id == assigned_course_id,
                Attendance.status == "absent"
            )
        ).scalar() or 0
        
        # Get total unique attendance sessions
        total_sessions = db.query(
            func.count(func.distinct(Attendance.attendance_date))
        ).filter(
            Attendance.assigned_course_id == assigned_course_id
        ).scalar() or 0
        
        attendance_summary = {
            "total_records": total_attendance_records,
            "total_sessions": total_sessions,
            "present_count": overall_present,
            "late_count": overall_late,
            "absent_count": overall_absent,
            "overall_attendance_rate": round((overall_present + overall_late) / total_attendance_records * 100, 2) if total_attendance_records > 0 else 0.0
        }
        
        return {
            "success": True,
            "message": "Course details retrieved successfully",
            "course_info": course_info,
            "section_info": section_info,
            "faculty_info": faculty_info,
            "enrolled_students": enrolled_students,
            "pending_students": pending_students,
            "rejected_students": rejected_students,
            "enrollment_summary": enrollment_summary,
            "attendance_summary": attendance_summary,
            "recent_attendance": recent_attendance,
            "academic_year": assigned_course.academic_year,
            "semester": assigned_course.semester,
            "total_students": enrollment_summary["total"],
            "total_sessions": total_sessions
        }
        
    except Exception as e:
        print(f"Error in get_faculty_course_details: {str(e)}")
        return {"error": f"Database error: {str(e)}"}

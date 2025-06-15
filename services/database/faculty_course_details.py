from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, case
from models import (
    Assigned_Course, Course, Section, Program, Faculty, User, Student, 
    Assigned_Course_Approval, AttendanceLog
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
        print(f"Getting course details for assigned_course_id: {assigned_course_id}")
        
        # Get faculty record from the current faculty data
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
        
        print(f"Course found: {course.name}")
        
        # Prepare course information
        course_info = {
            "assigned_course_id": assigned_course.id,
            "course_id": course.id,
            "course_name": course.name,
            "course_code": course.code,
            "course_description": course.description,
            "academic_year": assigned_course.academic_year,
            "semester": assigned_course.semester,
            "room": assigned_course.room,
            "created_at": assigned_course.created_at.isoformat() if assigned_course.created_at else None,
            "updated_at": assigned_course.updated_at.isoformat() if assigned_course.updated_at else None
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
        
        # Get students with formal enrollment records in assigned_course_approval
        students_query = db.query(
            Student,
            User,
            Assigned_Course_Approval
        ).join(
            User, User.id == Student.user_id
        ).join(
            Assigned_Course_Approval, 
            Assigned_Course_Approval.student_id == Student.id
        ).filter(
            and_(
                Assigned_Course_Approval.assigned_course_id == assigned_course_id,
                User.isDeleted == 0
            )
        ).all()
        
        print(f"Processing {len(students_query)} students with formal enrollment records")
        
        # Process students by enrollment status
        enrolled_students = []
        pending_students = []
        rejected_students = []
        passed_students = []
        failed_students = []
        attending_students = []  # Students with attendance but no formal approval
        
        enrollment_summary = {
            "enrolled": 0,
            "pending": 0,
            "rejected": 0,
            "passed": 0,
            "failed": 0,
            "attending": 0,
            "total": 0
        }
        
        for student, user, approval in students_query:
            print(f"Processing student {student.id} ({user.first_name} {user.last_name}) with status: {approval.status}")
            
            # Get attendance summary for this student
            attendance_stats = db.query(
                func.count(AttendanceLog.id).label("total_sessions"),
                func.sum(case((AttendanceLog.status == "present", 1), else_=0)).label("present_count"),
                func.sum(case((AttendanceLog.status == "absent", 1), else_=0)).label("absent_count"),
                func.sum(case((AttendanceLog.status == "late", 1), else_=0)).label("late_count")
            ).filter(
                and_(
                    AttendanceLog.user_id == user.id,
                    AttendanceLog.assigned_course_id == assigned_course_id
                )
            ).first()
            
            # Get latest attendance
            latest_attendance = db.query(AttendanceLog).filter(
                and_(
                    AttendanceLog.user_id == user.id,
                    AttendanceLog.assigned_course_id == assigned_course_id
                )
            ).order_by(desc(AttendanceLog.date), desc(AttendanceLog.created_at)).first()
            
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
            
            # Determine if student failed based on attendance
            attendance_failed = attendance_percentage < 75 if total_sessions > 0 else False
            failed_count = 1 if attendance_failed else 0
            
            student_info = {
                "student_id": student.id,
                "user_id": user.id,
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
                "latest_attendance_date": latest_attendance.date.isoformat() if latest_attendance and latest_attendance.date else None,
                "latest_attendance_status": latest_attendance.status if latest_attendance else None
            }
            
            # Categorize by enrollment status
            if approval.status == "enrolled":
                enrolled_students.append(student_info)
                enrollment_summary["enrolled"] += 1
                print(f"  -> Added to ENROLLED list")
            elif approval.status == "pending":
                pending_students.append(student_info)
                enrollment_summary["pending"] += 1
                print(f"  -> Added to PENDING list")
            elif approval.status == "rejected":
                rejected_students.append(student_info)
                enrollment_summary["rejected"] += 1
                print(f"  -> Added to REJECTED list")
            elif approval.status == "passed":
                passed_students.append(student_info)
                enrollment_summary["passed"] += 1
                print(f"  -> Added to PASSED list")
            elif approval.status == "failed":
                failed_students.append(student_info)
                enrollment_summary["failed"] += 1
                print(f"  -> Added to FAILED list")
            
            enrollment_summary["total"] += 1
        
        # Get students with attendance but no formal enrollment (attending_students)
        attending_only_query = db.query(
            Student,
            User
        ).join(
            User, User.id == Student.user_id
        ).join(
            AttendanceLog, AttendanceLog.user_id == User.id
        ).filter(
            and_(
                AttendanceLog.assigned_course_id == assigned_course_id,
                User.isDeleted == 0,
                ~Student.id.in_([s.id for s, u, a in students_query])  # Exclude students with formal enrollment
            )
        ).distinct().all()
        
        print(f"Found {len(attending_only_query)} students with attendance but no formal enrollment")
        
        for student, user in attending_only_query:
            # Get attendance summary for this attending student
            attendance_stats = db.query(
                func.count(AttendanceLog.id).label("total_sessions"),
                func.sum(case((AttendanceLog.status == "present", 1), else_=0)).label("present_count"),
                func.sum(case((AttendanceLog.status == "absent", 1), else_=0)).label("absent_count"),
                func.sum(case((AttendanceLog.status == "late", 1), else_=0)).label("late_count")
            ).filter(
                and_(
                    AttendanceLog.user_id == user.id,
                    AttendanceLog.assigned_course_id == assigned_course_id
                )
            ).first()
            
            # Get latest attendance
            latest_attendance = db.query(AttendanceLog).filter(
                and_(
                    AttendanceLog.user_id == user.id,
                    AttendanceLog.assigned_course_id == assigned_course_id
                )
            ).order_by(desc(AttendanceLog.date), desc(AttendanceLog.created_at)).first()
            
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
            
            # Determine if student failed based on attendance
            attendance_failed = attendance_percentage < 75 if total_sessions > 0 else False
            failed_count = 1 if attendance_failed else 0
            
            attending_student_info = {
                "student_id": student.id,
                "user_id": user.id,
                "student_number": student.student_number,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "enrollment_status": "attending",  # Special status for students with attendance but no formal enrollment
                "rejection_reason": None,
                "enrollment_created_at": None,
                "enrollment_updated_at": None,
                "total_sessions": total_sessions,
                "present_count": present_count,
                "absent_count": absent_count,
                "late_count": late_count,
                "failed_count": failed_count,
                "attendance_percentage": attendance_percentage,
                "latest_attendance_date": latest_attendance.date.isoformat() if latest_attendance and latest_attendance.date else None,
                "latest_attendance_status": latest_attendance.status if latest_attendance else None
            }
            
            attending_students.append(attending_student_info)
            enrollment_summary["attending"] += 1
            enrollment_summary["total"] += 1
            print(f"  -> Added student {student.id} to ATTENDING list")
        
        # Get recent attendance records (last 20 records)
        recent_attendance_query = db.query(
            AttendanceLog,
            Student,
            User
        ).join(
            User, User.id == AttendanceLog.user_id
        ).join(
            Student, Student.user_id == User.id
        ).filter(
            AttendanceLog.assigned_course_id == assigned_course_id
        ).order_by(
            desc(AttendanceLog.date),
            desc(AttendanceLog.created_at)
        ).limit(20).all()
        
        recent_attendance = []
        for attendance, student, user in recent_attendance_query:
            recent_attendance.append({
                "attendance_id": attendance.id,
                "student_id": student.id,
                "student_name": f"{user.first_name} {user.last_name}",
                "student_number": student.student_number,
                "attendance_date": attendance.date.isoformat() if attendance.date else None,
                "status": attendance.status,
                "has_image": bool(attendance.image),
                "created_at": attendance.created_at.isoformat() if attendance.created_at else None,
                "updated_at": attendance.updated_at.isoformat() if attendance.updated_at else None
            })
        
        # Calculate overall attendance summary (optimized)
        attendance_summary_query = db.query(
            func.count(AttendanceLog.id).label("total_records"),
            func.count(func.distinct(AttendanceLog.date)).label("total_sessions"),
            func.sum(case((AttendanceLog.status == "present", 1), else_=0)).label("present_count"),
            func.sum(case((AttendanceLog.status == "late", 1), else_=0)).label("late_count"),
            func.sum(case((AttendanceLog.status == "absent", 1), else_=0)).label("absent_count")
        ).filter(
            AttendanceLog.assigned_course_id == assigned_course_id
        ).first()
        
        total_attendance_records = attendance_summary_query.total_records or 0
        total_sessions = attendance_summary_query.total_sessions or 0
        overall_present = attendance_summary_query.present_count or 0
        overall_late = attendance_summary_query.late_count or 0
        overall_absent = attendance_summary_query.absent_count or 0
        
        attendance_summary = {
            "total_records": total_attendance_records,
            "total_sessions": total_sessions,
            "present_count": overall_present,
            "late_count": overall_late,
            "absent_count": overall_absent,
            "overall_attendance_rate": round((overall_present + overall_late) / total_attendance_records * 100, 2) if total_attendance_records > 0 else 0.0
        }
        
        print(f"Course details completed successfully")
        print(f"Final enrollment summary: {enrollment_summary}")
        
        return {
            "success": True,
            "message": "Course details retrieved successfully",
            "course_info": course_info,
            "section_info": section_info,
            "faculty_info": faculty_info,
            "enrolled_students": enrolled_students,
            "pending_students": pending_students,
            "rejected_students": rejected_students,
            "passed_students": passed_students,
            "failed_students": failed_students,
            "attending_students": attending_students,
            "enrollment_summary": enrollment_summary,
            "attendance_summary": attendance_summary,
            "recent_attendance": recent_attendance,
            "academic_year": assigned_course.academic_year,
            "semester": assigned_course.semester,
            "total_students": enrollment_summary["total"],
            "total_sessions": total_sessions
        }
        
    except Exception as e:
        print(f"ERROR in get_faculty_course_details: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Database error: {str(e)}"}



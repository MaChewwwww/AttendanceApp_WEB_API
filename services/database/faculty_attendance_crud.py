from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime
from typing import Dict, Any, List, Optional
from models import (
    User, Faculty, Assigned_Course, Course, Section, Program,
    Assigned_Course_Approval, AttendanceLog, Status, Student
)

def get_faculty_attendance_history(db: Session, faculty_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all attendance records for courses assigned to this faculty member
    
    Args:
        db: Database session
        faculty_data: Faculty user data from JWT
        
    Returns:
        Dictionary with attendance records and summaries
    """
    try:
        user_id = faculty_data.get("user_id")
        
        if not user_id:
            raise ValueError("User ID not found in authentication data")
        
        # Get faculty record
        faculty = db.query(Faculty).filter(Faculty.user_id == user_id).first()
        if not faculty:
            raise ValueError("Faculty record not found for this user")
        
        # Get all attendance logs for courses assigned to this faculty
        print(f"Fetching attendance records for faculty user_id: {user_id}")
        attendance_query = db.query(
            AttendanceLog,
            Assigned_Course,
            Course,
            Section,
            Program,
            User,
            Student
        ).join(
            Assigned_Course, AttendanceLog.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            Section, Assigned_Course.section_id == Section.id
        ).join(
            Program, Section.program_id == Program.id
        ).join(
            User, AttendanceLog.user_id == User.id
        ).outerjoin(
            Student, Student.user_id == User.id
        ).filter(
            and_(
                Assigned_Course.faculty_id == user_id,
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0,
                User.isDeleted == 0
            )
        ).order_by(AttendanceLog.date.desc()).all()
        
        print(f"Found {len(attendance_query)} attendance records for faculty")
        
        # Process attendance records
        attendance_records = []
        course_summary = {}
        academic_year_summary = {}
        status_counts = {"present": 0, "absent": 0, "late": 0}
        student_summary = {}
        
        for attendance, assigned_course, course, section, program, user, student in attendance_query:
            # Check if attendance has an image
            has_image = attendance.image is not None and len(attendance.image) > 0
            
            # Determine user type and details
            user_type = "Student" if student else "Faculty"
            user_identifier = student.student_number if student else faculty.employee_number
            
            # Prepare attendance record
            attendance_record = {
                "attendance_id": attendance.id,
                "assigned_course_id": assigned_course.id,
                "course_id": course.id,
                "course_name": course.name,
                "course_code": course.code,
                "section_name": section.name,
                "program_name": program.name,
                "program_acronym": program.acronym,
                "academic_year": assigned_course.academic_year,
                "semester": assigned_course.semester,
                "room": assigned_course.room,
                "attendance_date": attendance.date.isoformat() if attendance.date else None,
                "status": attendance.status,
                "has_image": has_image,
                "attendee_user_id": user.id,
                "attendee_name": f"{user.first_name} {user.last_name}",
                "attendee_email": user.email,
                "attendee_type": user_type,
                "attendee_identifier": user_identifier,
                "created_at": attendance.created_at.isoformat() if attendance.created_at else None,
                "updated_at": attendance.updated_at.isoformat() if attendance.updated_at else None
            }
            
            attendance_records.append(attendance_record)
            
            # Update status counts
            if attendance.status in status_counts:
                status_counts[attendance.status] += 1
            
            # Update course summary
            course_key = f"{course.name} ({assigned_course.academic_year})"
            if course_key not in course_summary:
                course_summary[course_key] = {
                    "course_name": course.name,
                    "course_code": course.code,
                    "academic_year": assigned_course.academic_year,
                    "semester": assigned_course.semester,
                    "total_sessions": 0,
                    "present": 0,
                    "absent": 0,
                    "late": 0,
                    "unique_attendees": set(),
                    "attendance_percentage": 0.0
                }
            
            course_summary[course_key]["total_sessions"] += 1
            if attendance.status in ["present", "absent", "late"]:
                course_summary[course_key][attendance.status] += 1
            course_summary[course_key]["unique_attendees"].add(user.id)
            
            # Update academic year summary
            academic_year = assigned_course.academic_year or "Unknown"
            if academic_year not in academic_year_summary:
                academic_year_summary[academic_year] = {
                    "total_sessions": 0,
                    "present": 0,
                    "absent": 0,
                    "late": 0,
                    "unique_attendees": set(),
                    "attendance_percentage": 0.0
                }
            
            academic_year_summary[academic_year]["total_sessions"] += 1
            if attendance.status in ["present", "absent", "late"]:
                academic_year_summary[academic_year][attendance.status] += 1
            academic_year_summary[academic_year]["unique_attendees"].add(user.id)
            
            # Update student summary
            if user_type == "Student":
                student_key = f"{user.first_name} {user.last_name} ({user_identifier})"
                if student_key not in student_summary:
                    student_summary[student_key] = {
                        "user_id": user.id,
                        "name": f"{user.first_name} {user.last_name}",
                        "identifier": user_identifier,
                        "email": user.email,
                        "total_sessions": 0,
                        "present": 0,
                        "absent": 0,
                        "late": 0,
                        "attendance_percentage": 0.0
                    }
                
                student_summary[student_key]["total_sessions"] += 1
                if attendance.status in ["present", "absent", "late"]:
                    student_summary[student_key][attendance.status] += 1
        
        # Calculate attendance percentages for course summary
        for course_key in course_summary:
            course_data = course_summary[course_key]
            total = course_data["total_sessions"]
            if total > 0:
                attended = course_data["present"] + course_data["late"]
                course_data["attendance_percentage"] = round((attended / total) * 100, 2)
            # Convert set to count for JSON serialization
            course_data["unique_attendees"] = len(course_data["unique_attendees"])
        
        # Calculate attendance percentages for academic year summary
        for year in academic_year_summary:
            year_data = academic_year_summary[year]
            total = year_data["total_sessions"]
            if total > 0:
                attended = year_data["present"] + year_data["late"]
                year_data["attendance_percentage"] = round((attended / total) * 100, 2)
            # Convert set to count for JSON serialization
            year_data["unique_attendees"] = len(year_data["unique_attendees"])
        
        # Calculate attendance percentages for student summary
        for student_key in student_summary:
            student_data = student_summary[student_key]
            total = student_data["total_sessions"]
            if total > 0:
                attended = student_data["present"] + student_data["late"]
                student_data["attendance_percentage"] = round((attended / total) * 100, 2)
        
        # Calculate overall attendance statistics
        total_sessions = len(attendance_records)
        overall_attendance_percentage = 0.0
        if total_sessions > 0:
            attended_sessions = status_counts["present"] + status_counts["late"]
            overall_attendance_percentage = round((attended_sessions / total_sessions) * 100, 2)
        
        attendance_summary = {
            "total_sessions": total_sessions,
            "present_count": status_counts["present"],
            "absent_count": status_counts["absent"],
            "late_count": status_counts["late"],
            "attended_sessions": status_counts["present"] + status_counts["late"],
            "overall_attendance_percentage": overall_attendance_percentage,
            "unique_courses": len(course_summary),
            "unique_academic_years": len(academic_year_summary),
            "unique_students": len(student_summary)
        }
        
        # Prepare faculty info
        faculty_user = db.query(User).filter(User.id == user_id).first()
        faculty_info = {
            "user_id": user_id,
            "name": f"{faculty_user.first_name} {faculty_user.last_name}",
            "email": faculty_user.email,
            "employee_number": faculty.employee_number
        }
        
        print(f"Successfully retrieved {total_sessions} attendance records across {len(course_summary)} courses")
        
        return {
            "success": True,
            "message": f"Retrieved {total_sessions} attendance records across {len(course_summary)} courses and {len(academic_year_summary)} academic years",
            "faculty_info": faculty_info,
            "attendance_records": attendance_records,
            "total_records": total_sessions,
            "attendance_summary": attendance_summary,
            "course_summary": course_summary,
            "academic_year_summary": academic_year_summary,
            "student_summary": student_summary
        }
        
    except Exception as e:
        print(f"Error getting faculty attendance history: {e}")
        import traceback
        traceback.print_exc()
        raise

def get_faculty_current_semester_attendance(db: Session, faculty_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get attendance logs for current academic year and semester for faculty's assigned courses
    
    Args:
        db: Database session
        faculty_data: Faculty user data from JWT
        
    Returns:
        Dictionary with current semester attendance records and summaries
    """
    try:
        user_id = faculty_data.get("user_id")
        
        print(f"DEBUG: Faculty current semester attendance - Faculty ID: {user_id}")
        
        # Get faculty record
        faculty = db.query(Faculty).filter(Faculty.user_id == user_id).first()
        if not faculty:
            print(f"DEBUG: Faculty record not found for user_id: {user_id}")
            return {"error": "Faculty record not found"}
        
        print(f"DEBUG: Faculty record found - ID: {faculty.id}")
        
        # Get current semester courses assigned to this faculty
        current_courses = db.query(
            Assigned_Course.id.label("assigned_course_id"),
            Assigned_Course.academic_year,
            Assigned_Course.semester,
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            Course.code.label("course_code")
        ).select_from(Assigned_Course).join(
            Course, Assigned_Course.course_id == Course.id
        ).filter(
            and_(
                Assigned_Course.faculty_id == user_id,
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0
            )
        ).order_by(
            Assigned_Course.academic_year.desc(),
            Assigned_Course.semester.desc()
        ).all()
        
        print(f"DEBUG: Found {len(current_courses)} courses assigned to faculty")
        for course in current_courses:
            print(f"DEBUG: Assigned course - ID: {course.assigned_course_id}, Name: {course.course_name}, Academic Year: {course.academic_year}, Semester: {course.semester}")
        
        if not current_courses:
            print("DEBUG: No courses assigned to faculty")
            return {
                "success": True,
                "message": "No courses assigned to faculty for current semester",
                "faculty_info": {
                    "user_id": user_id,
                    "employee_number": faculty.employee_number,
                    "name": faculty_data.get("name"),
                    "email": faculty_data.get("email")
                },
                "attendance_logs": [],
                "total_logs": 0,
                "courses": [],
                "academic_year": None,
                "semester": None,
                "attendance_summary": {
                    "total_sessions": 0,
                    "present_count": 0,
                    "absent_count": 0,
                    "late_count": 0,
                    "attendance_percentage": 0
                }
            }
        
        # Get the latest academic year and semester (assume current)
        current_academic_year = current_courses[0].academic_year
        current_semester = current_courses[0].semester
        
        print(f"DEBUG: Current academic year: {current_academic_year}, Current semester: {current_semester}")
        
        # Filter courses to current semester only
        current_semester_courses = [c for c in current_courses 
                                   if c.academic_year == current_academic_year 
                                   and c.semester == current_semester]
        
        # Get assigned course IDs for current semester
        assigned_course_ids = [course.assigned_course_id for course in current_semester_courses]
        print(f"DEBUG: Current semester assigned course IDs: {assigned_course_ids}")
        
        # Get attendance logs for current semester courses
        attendance_logs = db.query(
            AttendanceLog.id.label("attendance_id"),
            AttendanceLog.user_id,
            AttendanceLog.assigned_course_id,
            AttendanceLog.date.label("attendance_date"),
            AttendanceLog.status,
            AttendanceLog.image,
            AttendanceLog.created_at,
            AttendanceLog.updated_at,
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            Course.code.label("course_code"),
            Course.description.label("course_description"),
            Assigned_Course.academic_year,
            Assigned_Course.semester,
            Assigned_Course.room,
            User.first_name.label("attendee_first_name"),
            User.last_name.label("attendee_last_name"),
            User.email.label("attendee_email"),
            Student.student_number.label("student_number")
        ).select_from(AttendanceLog).join(
            Assigned_Course, AttendanceLog.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            User, AttendanceLog.user_id == User.id
        ).outerjoin(
            Student, Student.user_id == User.id
        ).filter(
            AttendanceLog.assigned_course_id.in_(assigned_course_ids)
        ).order_by(AttendanceLog.date.desc()).all()
        
        print(f"DEBUG: Found {len(attendance_logs)} attendance logs for current semester")
        for log in attendance_logs[:3]:  # Show first 3 logs for debugging
            print(f"DEBUG: Attendance log - ID: {log.attendance_id}, Date: {log.attendance_date}, Status: {log.status}, Course: {log.course_name}, Attendee: {log.attendee_first_name} {log.attendee_last_name}")
        
        # Process attendance logs
        processed_logs = []
        for log in attendance_logs:
            # Determine attendee type
            attendee_type = "Student" if log.student_number else "Faculty"
            attendee_identifier = log.student_number if log.student_number else faculty.employee_number
            
            processed_logs.append({
                "attendance_id": log.attendance_id,
                "assigned_course_id": log.assigned_course_id,
                "course_id": log.course_id,
                "course_name": log.course_name,
                "course_code": log.course_code,
                "course_description": log.course_description,
                "attendee_user_id": log.user_id,
                "attendee_name": f"{log.attendee_first_name} {log.attendee_last_name}",
                "attendee_email": log.attendee_email,
                "attendee_type": attendee_type,
                "attendee_identifier": attendee_identifier,
                "academic_year": log.academic_year,
                "semester": log.semester,
                "room": log.room,
                "attendance_date": log.attendance_date.isoformat() if log.attendance_date else None,
                "status": log.status,
                "has_image": log.image is not None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "updated_at": log.updated_at.isoformat() if log.updated_at else None
            })
        
        # Process course information
        courses_info = []
        for course in current_semester_courses:
            courses_info.append({
                "assigned_course_id": course.assigned_course_id,
                "course_id": course.course_id,
                "course_name": course.course_name,
                "course_code": course.course_code,
                "academic_year": course.academic_year,
                "semester": course.semester
            })
        
        # Calculate attendance summary
        total_logs = len(processed_logs)
        present_count = len([log for log in processed_logs if log["status"] == "present"])
        absent_count = len([log for log in processed_logs if log["status"] == "absent"])
        late_count = len([log for log in processed_logs if log["status"] == "late"])
        
        attendance_percentage = (present_count / total_logs * 100) if total_logs > 0 else 0
        
        print(f"DEBUG: Attendance summary - Total: {total_logs}, Present: {present_count}, Absent: {absent_count}, Late: {late_count}")
        
        # Get faculty user info
        faculty_user = db.query(User).filter(User.id == user_id).first()
        
        return {
            "success": True,
            "message": f"Attendance logs retrieved for {current_academic_year} {current_semester}",
            "faculty_info": {
                "user_id": user_id,
                "employee_number": faculty.employee_number,
                "name": f"{faculty_user.first_name} {faculty_user.last_name}",
                "email": faculty_user.email
            },
            "attendance_logs": processed_logs,
            "total_logs": total_logs,
            "courses": courses_info,
            "academic_year": current_academic_year,
            "semester": current_semester,
            "attendance_summary": {
                "total_sessions": total_logs,
                "present_count": present_count,
                "absent_count": absent_count,
                "late_count": late_count,
                "attendance_percentage": round(attendance_percentage, 2)
            }
        }
        
    except Exception as e:
        print(f"ERROR in get_faculty_current_semester_attendance: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

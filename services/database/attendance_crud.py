from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, time
from typing import Dict, Any, List, Optional
from models import Schedule, Assigned_Course, Course, User

def get_student_schedule(db: Session, student_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get student's schedule for today
    """
    try:
        from models import Student, Assigned_Course_Approval
        
        student_id = student_data.get("user_id")
        section_id = student_data.get("section_id")
        
        # Get student record
        student_record = db.query(Student).filter(Student.user_id == student_id).first()
        if not student_record:
            return {"error": "Student record not found"}
        
        # Get ALL course approvals for this student (not just enrolled)
        all_approvals = db.query(
            Assigned_Course_Approval.id,
            Assigned_Course_Approval.assigned_course_id,
            Assigned_Course_Approval.status,
            Assigned_Course.section_id,
            Course.name.label("course_name")
        ).select_from(Assigned_Course_Approval).join(
            Assigned_Course, Assigned_Course_Approval.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).filter(
            Assigned_Course_Approval.student_id == student_record.id
        ).all()
        
        # Get enrolled course IDs
        enrolled_courses = db.query(Assigned_Course_Approval.assigned_course_id).filter(
            and_(
                Assigned_Course_Approval.student_id == student_record.id,
                Assigned_Course_Approval.status == "enrolled"
            )
        ).all()
        
        assigned_course_ids = [course.assigned_course_id for course in enrolled_courses]
        
        current_datetime = datetime.now()
        current_day = current_datetime.strftime("%A")
        current_time = current_datetime.time()
        current_date = current_datetime.date()
        
        # Get all schedules for enrolled courses regardless of day
        if assigned_course_ids:
            all_schedules_query = db.query(
                Schedule.id,
                Schedule.assigned_course_id,
                Schedule.day_of_week,
                Schedule.start_time,
                Schedule.end_time,
                Course.name.label("course_name")
            ).select_from(Schedule).join(
                Assigned_Course, Schedule.assigned_course_id == Assigned_Course.id
            ).join(
                Course, Assigned_Course.course_id == Course.id
            ).filter(
                Schedule.assigned_course_id.in_(assigned_course_ids)
            )
        else:
            # If no enrolled courses, check all schedules for the section
            all_schedules_query = db.query(
                Schedule.id,
                Schedule.assigned_course_id,
                Schedule.day_of_week,
                Schedule.start_time,
                Schedule.end_time,
                Course.name.label("course_name")
            ).select_from(Schedule).join(
                Assigned_Course, Schedule.assigned_course_id == Assigned_Course.id
            ).join(
                Course, Assigned_Course.course_id == Course.id
            ).filter(
                Assigned_Course.section_id == section_id
            )
        
        all_schedules = all_schedules_query.all()
        
        # Get schedules for today
        schedules = db.query(
            Schedule.id,
            Schedule.assigned_course_id,
            Schedule.day_of_week,
            Schedule.start_time,
            Schedule.end_time,
            Course.name.label("course_name")
        ).select_from(Schedule).join(
            Assigned_Course, Schedule.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).filter(
            and_(
                Schedule.assigned_course_id.in_(assigned_course_ids) if assigned_course_ids else Schedule.assigned_course_id.in_([]),
                Schedule.day_of_week.ilike(current_day)
            )
        ).all()
        
        # Additional debug: Check for Thursday schedules specifically
        if assigned_course_ids:
            thursday_check = db.query(
                Schedule.id,
                Schedule.day_of_week,
                Schedule.start_time,
                Schedule.end_time,
                Course.name.label("course_name")
            ).select_from(Schedule).join(
                Assigned_Course, Schedule.assigned_course_id == Assigned_Course.id
            ).join(
                Course, Assigned_Course.course_id == Course.id
            ).filter(
                and_(
                    Schedule.assigned_course_id.in_(assigned_course_ids),
                    Schedule.day_of_week.ilike('Thursday')
                )
            ).all()
        
        schedule_info = {
            "student_id": student_id,
            "student_record_id": student_record.id,
            "section_id": section_id,
            "enrolled_course_ids": assigned_course_ids,
            "current_datetime": current_datetime.isoformat(),
            "current_day": current_day,
            "current_time": current_time.strftime("%H:%M:%S"),
            "current_date": current_date.isoformat(),
            "total_schedules_found": len(schedules),
            "total_all_schedules": len(all_schedules),
            "total_approvals": len(all_approvals),
            "approvals": [],
            "schedules": [],
            "all_schedules": []
        }
        
        # Add approval details
        for approval in all_approvals:
            schedule_info["approvals"].append({
                "approval_id": approval.id,
                "assigned_course_id": approval.assigned_course_id,
                "status": approval.status,
                "section_id": approval.section_id,
                "course_name": approval.course_name
            })
        
        # Process today's schedules
        for schedule in schedules:
            # Handle datetime objects properly
            start_datetime = schedule.start_time if isinstance(schedule.start_time, datetime) else schedule.start_time
            end_datetime = schedule.end_time if isinstance(schedule.end_time, datetime) else schedule.end_time
            
            start_time = start_datetime.time() if isinstance(start_datetime, datetime) else start_datetime
            end_time = end_datetime.time() if isinstance(end_datetime, datetime) else end_datetime
            
            # Determine status with full datetime comparison
            status = "upcoming"
            if isinstance(start_datetime, datetime) and isinstance(end_datetime, datetime):
                if current_datetime >= start_datetime and current_datetime <= end_datetime:
                    status = "ongoing"
                elif current_datetime > end_datetime:
                    status = "completed"
            else:
                if current_time >= start_time and current_time <= end_time:
                    status = "ongoing"
                elif current_time > end_time:
                    status = "completed"
            
            schedule_info["schedules"].append({
                "schedule_id": schedule.id,
                "assigned_course_id": schedule.assigned_course_id,
                "course_name": schedule.course_name,
                "day_of_week": schedule.day_of_week,
                "start_datetime": start_datetime.isoformat() if isinstance(start_datetime, datetime) else str(start_datetime),
                "end_datetime": end_datetime.isoformat() if isinstance(end_datetime, datetime) else str(end_datetime),
                "start_time": start_time.strftime("%H:%M:%S") if start_time else None,
                "end_time": end_time.strftime("%H:%M:%S") if end_time else None,
                "status": status,
                "is_current": status == "ongoing"
            })
        
        # Process all schedules to see what days are available
        for schedule in all_schedules:
            start_datetime = schedule.start_time if isinstance(schedule.start_time, datetime) else schedule.start_time
            end_datetime = schedule.end_time if isinstance(schedule.end_time, datetime) else schedule.end_time
            
            schedule_info["all_schedules"].append({
                "schedule_id": schedule.id,
                "assigned_course_id": schedule.assigned_course_id,
                "course_name": schedule.course_name,
                "day_of_week": schedule.day_of_week,
                "start_datetime": start_datetime.isoformat() if isinstance(start_datetime, datetime) else str(start_datetime),
                "end_datetime": end_datetime.isoformat() if isinstance(end_datetime, datetime) else str(end_datetime)
            })
        
        return schedule_info
        
    except Exception as e:
        return {"error": str(e)}

def get_current_semester_attendance(db: Session, student_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get attendance logs for current academic year and semester based on enrolled courses
    """
    try:
        from models import Student, Assigned_Course_Approval, AttendanceLog
        
        student_id = student_data.get("user_id")
        section_id = student_data.get("section_id")
        
        print(f"DEBUG: Current semester attendance - Student ID: {student_id}, Section ID: {section_id}")
        
        # Get student record
        student_record = db.query(Student).filter(Student.user_id == student_id).first()
        if not student_record:
            print(f"DEBUG: Student record not found for user_id: {student_id}")
            return {"error": "Student record not found"}
        
        print(f"DEBUG: Student record found - ID: {student_record.id}")
        
        # Get enrolled courses for current semester
        enrolled_courses = db.query(
            Assigned_Course_Approval.assigned_course_id,
            Assigned_Course.academic_year,
            Assigned_Course.semester,
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            Course.code.label("course_code")
        ).select_from(Assigned_Course_Approval).join(
            Assigned_Course, Assigned_Course_Approval.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).filter(
            and_(
                Assigned_Course_Approval.student_id == student_record.id,
                Assigned_Course_Approval.status == "enrolled",
                Assigned_Course.section_id == section_id,
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0
            )
        ).all()
        
        print(f"DEBUG: Found {len(enrolled_courses)} enrolled courses")
        for course in enrolled_courses:
            print(f"DEBUG: Enrolled course - ID: {course.assigned_course_id}, Name: {course.course_name}, Academic Year: {course.academic_year}, Semester: {course.semester}")
        
        if not enrolled_courses:
            print("DEBUG: No enrolled courses found")
            return {
                "success": True,
                "message": "No enrolled courses found for current semester",
                "student_info": {
                    "user_id": student_id,
                    "student_number": student_data.get("student_number"),
                    "name": student_data.get("name"),
                    "section_id": section_id
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
        
        # Get the academic year and semester from enrolled courses (should be same for all)
        current_academic_year = enrolled_courses[0].academic_year
        current_semester = enrolled_courses[0].semester
        
        print(f"DEBUG: Current academic year: {current_academic_year}, Current semester: {current_semester}")
        
        # Get assigned course IDs for enrolled courses
        assigned_course_ids = [course.assigned_course_id for course in enrolled_courses]
        print(f"DEBUG: Assigned course IDs: {assigned_course_ids}")
        
        # Get attendance logs for current semester
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
            User.first_name.label("faculty_first_name"),
            User.last_name.label("faculty_last_name"),
            User.email.label("faculty_email")
        ).select_from(AttendanceLog).join(
            Assigned_Course, AttendanceLog.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            User, Assigned_Course.faculty_id == User.id
        ).filter(
            and_(
                AttendanceLog.user_id == student_id,
                AttendanceLog.assigned_course_id.in_(assigned_course_ids)
            )
        ).order_by(AttendanceLog.date.desc()).all()
        
        print(f"DEBUG: Found {len(attendance_logs)} attendance logs")
        for log in attendance_logs[:3]:  # Show first 3 logs for debugging
            print(f"DEBUG: Attendance log - ID: {log.attendance_id}, Date: {log.attendance_date}, Status: {log.status}, Course: {log.course_name}")
        
        # Also check if there are ANY attendance logs for this student
        all_student_logs = db.query(AttendanceLog).filter(AttendanceLog.user_id == student_id).all()
        print(f"DEBUG: Total attendance logs for student across all courses: {len(all_student_logs)}")
        
        # Check if there are attendance logs for any of these courses (regardless of student)
        course_logs = db.query(AttendanceLog).filter(AttendanceLog.assigned_course_id.in_(assigned_course_ids)).all()
        print(f"DEBUG: Total attendance logs for enrolled courses (all students): {len(course_logs)}")
        
        # Process attendance logs
        processed_logs = []
        for log in attendance_logs:
            processed_logs.append({
                "attendance_id": log.attendance_id,
                "assigned_course_id": log.assigned_course_id,
                "course_id": log.course_id,
                "course_name": log.course_name,
                "course_code": log.course_code,
                "course_description": log.course_description,
                "faculty_name": f"{log.faculty_first_name} {log.faculty_last_name}",
                "faculty_email": log.faculty_email,
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
        for course in enrolled_courses:
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
        
        return {
            "success": True,
            "message": f"Attendance logs retrieved for {current_academic_year} {current_semester}",
            "student_info": {
                "user_id": student_id,
                "student_number": student_data.get("student_number"),
                "name": student_data.get("name"),
                "section_id": section_id
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
        print(f"ERROR in get_current_semester_attendance: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

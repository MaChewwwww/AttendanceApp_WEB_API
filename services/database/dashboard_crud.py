from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
from models import (
    User, Student, Assigned_Course, Assigned_Course_Approval, 
    Course, Section, Program, Faculty, Schedule
)

def get_student_dashboard_data(db: Session, current_student: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data for the authenticated student
    
    Args:
        db: Database session
        current_student: Current student data from JWT
        
    Returns:
        Dictionary containing dashboard data
    """
    try:
        student_id = current_student.get("user_id")
        section_id = current_student.get("section_id")
        
        # Get student record
        student_record = db.query(Student).filter(Student.user_id == student_id).first()
        if not student_record:
            raise ValueError("Student record not found")
        
        # If no section assigned, return basic info
        if not section_id:
            return {
                "success": True,
                "message": "Student dashboard data retrieved (no section assigned)",
                "student_info": {
                    "user_id": current_student["user_id"],
                    "name": current_student["name"],
                    "email": current_student["email"],
                    "student_number": current_student["student_number"],
                    "has_section": False,
                    "section_id": None,
                    "section_name": None,
                    "program_name": None
                },
                "current_classes": [],
                "today_schedule": [],
                "total_enrolled_courses": 0,
                "pending_approvals": 0,
                "schedule_summary": {
                    "total_classes_today": 0,
                    "next_class": None,
                    "current_class": None
                }
            }
        
        # Get section and program info
        section_info = db.query(Section, Program).join(
            Program, Section.program_id == Program.id
        ).filter(
            Section.id == section_id
        ).first()
        
        if not section_info:
            raise ValueError(f"Section {section_id} not found or deleted")
        
        section, program = section_info
        
        # First, get the latest academic year and semester for this student's enrolled courses)
        latest_semester_query = db.query(
            Assigned_Course.academic_year,
            Assigned_Course.semester
        ).select_from(Assigned_Course_Approval).join(
            Assigned_Course, Assigned_Course_Approval.assigned_course_id == Assigned_Course.id
        ).filter(
            and_(
                Assigned_Course_Approval.student_id == student_record.id,
                Assigned_Course_Approval.status == "enrolled",  # Only enrolled
                Assigned_Course.section_id == section_id,
                Assigned_Course.isDeleted == 0
            )
        ).order_by(
            Assigned_Course.academic_year.desc(),
            Assigned_Course.semester.desc()
        ).first()
        
        current_academic_year = None
        current_semester = None
        
        if latest_semester_query:
            current_academic_year = latest_semester_query.academic_year
            current_semester = latest_semester_query.semester
            print(f"DEBUG: Latest academic year: {current_academic_year}, semester: {current_semester}")
        else:
            print("DEBUG: No enrolled courses found for student")
        
        # Find the latest academic year with enrolled courses
        enrolled_approvals = db.query(
            Assigned_Course_Approval,
            Assigned_Course
        ).join(
            Assigned_Course, Assigned_Course_Approval.assigned_course_id == Assigned_Course.id
        ).filter(
            Assigned_Course_Approval.student_id == student_record.id,
            Assigned_Course_Approval.status == "enrolled",
            Assigned_Course.section_id == section_id,
            Assigned_Course.isDeleted == 0
        ).all()

        # Helper to extract semester order (1st < 2nd < 3rd < Summer)
        def semester_order(sem):
            if not sem:
                return 99
            s = sem.lower()
            if "1" in s:
                return 1
            if "2" in s:
                return 2
            if "3" in s:
                return 3
            if "sum" in s:
                return 4
            return 99

        # Find latest academic year
        academic_years = [ac.academic_year for _, ac in enrolled_approvals if ac.academic_year]
        latest_academic_year = None
        if academic_years:
            def get_year_start(y):
                try:
                    return int(y.split("-")[0]) if "-" in y else int(y)
                except:
                    return 0
            valid_years = [(y, get_year_start(y)) for y in academic_years if get_year_start(y) > 0]
            if valid_years:
                latest_academic_year = max(valid_years, key=lambda x: x[1])[0]

        # For that academic year, find the lowest semester with enrolled status
        semesters = [ac.semester for _, ac in enrolled_approvals if ac.academic_year == latest_academic_year]
        current_semester = None
        if semesters:
            current_semester = sorted(semesters, key=semester_order)[0]

        current_academic_year = latest_academic_year

        # Get current enrolled courses (latest academic year, lowest semester)
        enrolled_courses_query = db.query(
            Assigned_Course_Approval.id.label("approval_id"),
            Assigned_Course_Approval.status.label("enrollment_status"),
            Assigned_Course.id.label("assigned_course_id"),
            Assigned_Course.academic_year,
            Assigned_Course.semester,
            Assigned_Course.room,
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            Course.code.label("course_code"),
            Course.description.label("course_description"),
            User.first_name.label("faculty_first_name"),
            User.last_name.label("faculty_last_name"),
            User.email.label("faculty_email")
        ).select_from(Assigned_Course_Approval).join(
            Assigned_Course, Assigned_Course_Approval.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            User, Assigned_Course.faculty_id == User.id
        ).filter(
            Assigned_Course_Approval.student_id == student_record.id,
            Assigned_Course_Approval.status == "enrolled",
            Assigned_Course.section_id == section_id,
            Assigned_Course.academic_year == current_academic_year,
            Assigned_Course.semester == current_semester,
            Assigned_Course.isDeleted == 0,
            Course.isDeleted == 0,
            User.isDeleted == 0
        )
        enrolled_courses = enrolled_courses_query.all() if current_academic_year and current_semester else []
        
        print(f"DEBUG: Found {len(enrolled_courses)} enrolled courses for current semester ({current_academic_year} {current_semester})")
        
        # Get pending approvals count (all pending, not just current semester)
        pending_count = db.query(Assigned_Course_Approval).filter(
            and_(
                Assigned_Course_Approval.student_id == student_record.id,
                Assigned_Course_Approval.status == "pending"
            )
        ).count()

        # Process current classes
        current_classes = []
        assigned_course_ids = []
        
        for course in enrolled_courses:
            assigned_course_ids.append(course.assigned_course_id)
            current_classes.append({
                "assigned_course_id": course.assigned_course_id,
                "course_id": course.course_id,
                "course_name": course.course_name,
                "course_code": course.course_code,
                "course_description": course.course_description,
                "faculty_name": f"{course.faculty_first_name} {course.faculty_last_name}",
                "faculty_email": course.faculty_email,
                "academic_year": course.academic_year,
                "semester": course.semester,
                "room": course.room,
                "enrollment_status": course.enrollment_status
            })
        
        # Get today's schedule and all schedules for enrolled courses
        today_schedule = []
        all_enrolled_schedules = []
        current_datetime = datetime.now()
        current_time = current_datetime.time()
        current_date = current_datetime.date()
        current_day = current_datetime.strftime("%A")
        
        # Check if we have any assigned course IDs to work with
        if not assigned_course_ids:
            print("DEBUG: No enrolled courses found for current semester")
            # If no enrolled courses for current semester, don't show any schedules
            all_section_schedules = []
        
        if assigned_course_ids:
            print(f"DEBUG: Getting schedules for {len(assigned_course_ids)} enrolled courses")
            # Get ALL schedules for enrolled courses (for calendar filtering)
            all_schedules_query = db.query(
                Schedule.id.label("schedule_id"),
                Schedule.assigned_course_id,
                Schedule.day_of_week,
                Schedule.start_time,
                Schedule.end_time,
                Course.name.label("course_name"),
                Course.code.label("course_code"),
                Assigned_Course.room,
                User.first_name.label("faculty_first_name"),
                User.last_name.label("faculty_last_name")
            ).select_from(Schedule).join(
                Assigned_Course, Schedule.assigned_course_id == Assigned_Course.id
            ).join(
                Course, Assigned_Course.course_id == Course.id
            ).join(
                User, Assigned_Course.faculty_id == User.id
            ).filter(
                Schedule.assigned_course_id.in_(assigned_course_ids)
            ).order_by(Schedule.day_of_week, Schedule.start_time).all()
            
            print(f"DEBUG: Found {len(all_schedules_query)} total schedules for enrolled courses")
            
            # Process all schedules for enrolled courses
            for schedule in all_schedules_query:
                # Handle datetime objects - but treat them as recurring weekly schedules
                start_datetime = schedule.start_time if isinstance(schedule.start_time, datetime) else schedule.start_time
                end_datetime = schedule.end_time if isinstance(schedule.end_time, datetime) else schedule.end_time
                
                # Extract just the TIME portion for comparison (ignore the date)
                if isinstance(start_datetime, datetime):
                    start_time = start_datetime.time()
                else:
                    start_time = start_datetime
                    
                if isinstance(end_datetime, datetime):
                    end_time = end_datetime.time()
                else:
                    end_time = end_datetime
                
                # Determine if this schedule is for today
                is_today = schedule.day_of_week.lower() == current_day.lower()
                
                # For today's schedules, calculate status
                class_status = "upcoming"  # Default status for non-today schedules
                
                if is_today:
                    # Create today's schedule times for comparison
                    today_start = datetime.combine(current_date, start_time)
                    today_end = datetime.combine(current_date, end_time)
                    
                    # Handle overnight classes (end time is next day)
                    if end_time < start_time:
                        today_end = today_end + timedelta(days=1)
                    
                    # Determine class status using TODAY'S schedule times
                    if current_datetime >= today_start and current_datetime <= today_end:
                        class_status = "ongoing"
                    elif current_datetime > today_end:
                        class_status = "completed"
                    else:
                        class_status = "upcoming"
                
                schedule_item = {
                    "schedule_id": schedule.schedule_id,
                    "assigned_course_id": schedule.assigned_course_id,
                    "course_name": schedule.course_name,
                    "course_code": schedule.course_code,
                    "faculty_name": f"{schedule.faculty_first_name} {schedule.faculty_last_name}",
                    "room": schedule.room,
                    "day_of_week": schedule.day_of_week,
                    "start_time": start_time.strftime("%H:%M") if start_time else None,
                    "end_time": end_time.strftime("%H:%M") if end_time else None,
                    "status": class_status,
                    "is_today": is_today
                }
                
                # Add to all schedules list
                all_enrolled_schedules.append(schedule_item)
                
                # Add to today's schedule if it's for today
                if is_today:
                    today_schedule.append(schedule_item)
        
        print(f"DEBUG: Today's schedule has {len(today_schedule)} classes")
        
        # Find current and next class from today's schedule
        current_class = None
        next_class = None
        
        for class_item in today_schedule:
            if class_item["status"] == "ongoing":
                current_class = class_item
                break
        
        # Find next upcoming class if no current class
        if not current_class:
            for class_item in today_schedule:
                if class_item["status"] == "upcoming":
                    next_class = class_item
                    break

        # Prepare response
        dashboard_data = {
            "success": True,
            "message": "Student dashboard data retrieved successfully",
            "student_info": {
                "user_id": current_student["user_id"],
                "name": current_student["name"],
                "email": current_student["email"],
                "student_number": current_student["student_number"],
                "has_section": True,
                "section_id": section.id,
                "section_name": section.name,
                "program_name": program.name,
                "program_acronym": program.acronym,
                "current_academic_year": current_academic_year,
                "current_semester": current_semester
            },
            "current_classes": current_classes,
            "today_schedule": today_schedule,
            "all_schedules": all_enrolled_schedules,  # All schedules for calendar filtering
            "total_enrolled_courses": len(current_classes),
            "pending_approvals": pending_count,
            "schedule_summary": {
                "total_classes_today": len(today_schedule),
                "total_weekly_schedules": len(all_enrolled_schedules),
                "current_class": current_class,
                "next_class": next_class,
                "current_day": current_day
            }
        }
        
        # Check if user is graduated (status_id == 2)
        if current_student.get('status_id') == 2:
            return {
                "success": True,
                "message": "Student dashboard data retrieved (graduated, no current classes)",
                "student_info": {
                    "user_id": current_student["user_id"],
                    "name": current_student["name"],
                    "email": current_student["email"],
                    "student_number": current_student["student_number"],
                    "has_section": True,
                    "section_id": section_id,
                    "section_name": None,
                    "program_name": None,
                    "program_acronym": None,
                    "current_academic_year": None,
                    "current_semester": None
                },
                "current_classes": [],
                "today_schedule": [],
                "all_schedules": [],
                "total_enrolled_courses": 0,
                "pending_approvals": 0,
                "schedule_summary": {
                    "total_classes_today": 0,
                    "total_weekly_schedules": 0,
                    "current_class": None,
                    "next_class": None,
                    "current_day": datetime.now().strftime("%A")
                }
            }

        return dashboard_data
        
    except Exception as e:
        print(f"Error getting student dashboard data: {e}")
        raise

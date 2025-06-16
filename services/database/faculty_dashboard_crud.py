from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
from models import (
    User, Faculty, Assigned_Course, Assigned_Course_Approval, 
    Course, Section, Program, Schedule, AttendanceLog
)

def get_semester_priority(semester: str) -> int:
    """
    Get semester priority based on hierarchy: Summer > 3rd Semester > 2nd Semester > 1st Semester
    Higher number = higher priority (more recent)
    """
    semester_map = {
        "Summer": 4,
        "3rd Semester": 3,
        "2nd Semester": 2,
        "1st Semester": 1
    }
    return semester_map.get(semester, 0)

def get_current_academic_period(assigned_courses_list) -> tuple:
    """
    Determine the current academic year and semester based on latest data
    """
    if not assigned_courses_list:
        return None, None
    
    # Group by academic year and find the latest
    academic_years = {}
    for course in assigned_courses_list:
        year = course.academic_year
        semester = course.semester
        
        if year not in academic_years:
            academic_years[year] = []
        academic_years[year].append(semester)
    
    # Get the latest academic year
    latest_year = max(academic_years.keys()) if academic_years else None
    
    if not latest_year:
        return None, None
    
    # Get the latest semester for the latest academic year
    semesters_in_year = list(set(academic_years[latest_year]))  # Remove duplicates
    latest_semester = max(semesters_in_year, key=get_semester_priority)
    
    return latest_year, latest_semester

def get_faculty_dashboard_data(db: Session, current_faculty: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data for the authenticated faculty
    Only returns current semester and academic year data
    
    Args:
        db: Database session
        current_faculty: Current faculty data from JWT
        
    Returns:
        Dictionary containing faculty dashboard data
    """
    try:
        faculty_user_id = current_faculty.get("user_id")
        
        # Get faculty record
        faculty_record = db.query(Faculty).filter(Faculty.user_id == faculty_user_id).first()
        if not faculty_record:
            raise ValueError("Faculty record not found")
        
        # Get current datetime information
        current_datetime = datetime.now()
        current_time = current_datetime.time()
        current_date = current_datetime.date()
        current_day = current_datetime.strftime("%A")
        
        # Get all courses assigned to this faculty to determine current period
        all_assigned_courses = db.query(
            Assigned_Course.academic_year,
            Assigned_Course.semester
        ).filter(
            and_(
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.isDeleted == 0
            )
        ).distinct().all()
        
        # Determine current academic year and semester
        current_academic_year, current_semester = get_current_academic_period(all_assigned_courses)
        
        print(f"DEBUG: Determined current academic year: {current_academic_year}, semester: {current_semester}")
        
        if not current_academic_year or not current_semester:
            # Return empty dashboard if no courses found
            faculty_user = db.query(User).filter(User.id == faculty_user_id).first()
            faculty_info = {
                "user_id": faculty_user_id,
                "name": f"{faculty_user.first_name} {faculty_user.last_name}" if faculty_user else current_faculty.get("name"),
                "email": faculty_user.email if faculty_user else current_faculty.get("email"),
                "employee_number": faculty_record.employee_number,
                "current_academic_year": None,
                "current_semester": None
            }
            
            return {
                "success": True,
                "message": "No current courses found for faculty",
                "faculty_info": faculty_info,
                "current_courses": [],
                "previous_courses": [],
                "today_schedule": [],
                "all_schedules": [],
                "total_current_courses": 0,
                "total_previous_courses": 0,
                "total_pending_approvals": 0,
                "today_attendance_count": 0,
                "recent_attendance": [],
                "schedule_summary": {
                    "total_classes_today": 0,
                    "total_weekly_schedules": 0,
                    "current_class": None,
                    "next_class": None,
                    "current_day": current_day
                }
            }
        
        # Get ONLY current semester courses
        current_courses_query = db.query(
            Assigned_Course.id.label("assigned_course_id"),
            Assigned_Course.academic_year,
            Assigned_Course.semester,
            Assigned_Course.room,
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            Course.code.label("course_code"),
            Course.description.label("course_description"),
            Section.id.label("section_id"),
            Section.name.label("section_name"),
            Program.id.label("program_id"),
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
                Assigned_Course.academic_year == current_academic_year,
                Assigned_Course.semester == current_semester,
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0,
                Section.isDeleted == 0,
                Program.isDeleted == 0
            )
        ).order_by(Course.name).all()
        
        print(f"DEBUG: Found {len(current_courses_query)} current semester courses for faculty")
        
        # Process current courses
        current_courses = []
        assigned_course_ids = []
        
        for course in current_courses_query:
            # Add enrollment counts for each course using separate queries
            total_count = db.query(func.count(Assigned_Course_Approval.id)).filter(
                Assigned_Course_Approval.assigned_course_id == course.assigned_course_id
            ).scalar() or 0
            
            # Enrolled students now includes "enrolled", "passed", and "failed" students
            enrolled_count = db.query(func.count(Assigned_Course_Approval.id)).filter(
                and_(
                    Assigned_Course_Approval.assigned_course_id == course.assigned_course_id,
                    Assigned_Course_Approval.status.in_(["enrolled", "passed", "failed"])
                )
            ).scalar() or 0
            
            pending_count = db.query(func.count(Assigned_Course_Approval.id)).filter(
                and_(
                    Assigned_Course_Approval.assigned_course_id == course.assigned_course_id,
                    Assigned_Course_Approval.status == "pending"
                )
            ).scalar() or 0
            
            rejected_count = db.query(func.count(Assigned_Course_Approval.id)).filter(
                and_(
                    Assigned_Course_Approval.assigned_course_id == course.assigned_course_id,
                    Assigned_Course_Approval.status == "rejected"
                )
            ).scalar() or 0

            passed_count = db.query(func.count(Assigned_Course_Approval.id)).filter(
                and_(
                    Assigned_Course_Approval.assigned_course_id == course.assigned_course_id,
                    Assigned_Course_Approval.status == "passed"
                )
            ).scalar() or 0

            course_info = {
                "assigned_course_id": course.assigned_course_id,
                "course_id": course.course_id,
                "course_name": course.course_name,
                "course_code": course.course_code,
                "course_description": course.course_description,
                "section_id": course.section_id,
                "section_name": course.section_name,
                "program_id": course.program_id,
                "program_name": course.program_name,
                "program_acronym": course.program_acronym,
                "academic_year": course.academic_year,
                "semester": course.semester,
                "room": course.room,
                "total_students": int(total_count),
                "enrolled_students": int(enrolled_count),  # Now includes passed and failed
                "pending_students": int(pending_count),
                "rejected_students": int(rejected_count),
                "passed_students": int(passed_count)  # Separate count for passed students only
            }

            current_courses.append(course_info)
            assigned_course_ids.append(course.assigned_course_id)
        
        # Get today's schedule for current courses
        today_schedule = []
        all_schedules = []
        
        if assigned_course_ids:
            print(f"DEBUG: Getting schedules for {len(assigned_course_ids)} current courses")
            
            # Get ALL schedules for current courses
            all_schedules_query = db.query(
                Schedule.id.label("schedule_id"),
                Schedule.assigned_course_id,
                Schedule.day_of_week,
                Schedule.start_time,
                Schedule.end_time,
                Course.name.label("course_name"),
                Course.code.label("course_code"),
                Assigned_Course.room,
                Section.name.label("section_name"),
                Program.acronym.label("program_acronym")
            ).select_from(Schedule).join(
                Assigned_Course, Schedule.assigned_course_id == Assigned_Course.id
            ).join(
                Course, Assigned_Course.course_id == Course.id
            ).join(
                Section, Assigned_Course.section_id == Section.id
            ).join(
                Program, Section.program_id == Program.id
            ).filter(
                Schedule.assigned_course_id.in_(assigned_course_ids)
            ).order_by(Schedule.day_of_week, Schedule.start_time).all()
            
            print(f"DEBUG: Found {len(all_schedules_query)} total schedules for current courses")
            
            # Process all schedules
            for schedule in all_schedules_query:
                # Handle datetime objects
                start_datetime = schedule.start_time if isinstance(schedule.start_time, datetime) else schedule.start_time
                end_datetime = schedule.end_time if isinstance(schedule.end_time, datetime) else schedule.end_time
                
                # Extract time portion
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
                
                # Calculate status for today's schedules
                class_status = "upcoming"  # Default for non-today schedules
                
                if is_today:
                    today_start = datetime.combine(current_date, start_time)
                    today_end = datetime.combine(current_date, end_time)
                    
                    # Handle overnight classes
                    if end_time < start_time:
                        today_end = today_end + timedelta(days=1)
                    
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
                    "section_name": schedule.section_name,
                    "program_acronym": schedule.program_acronym,
                    "room": schedule.room,
                    "day_of_week": schedule.day_of_week,
                    "start_time": start_time.strftime("%H:%M") if start_time else None,
                    "end_time": end_time.strftime("%H:%M") if end_time else None,
                    "status": class_status,
                    "is_today": is_today
                }
                
                # Add to all schedules
                all_schedules.append(schedule_item)
                
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
        
        # Get recent attendance statistics for faculty's current courses only
        recent_attendance_query = db.query(
            AttendanceLog.id,
            AttendanceLog.status,
            AttendanceLog.date,
            Course.name.label("course_name"),
            Section.name.label("section_name"),
            User.first_name,
            User.last_name
        ).select_from(AttendanceLog).join(
            Assigned_Course, AttendanceLog.assigned_course_id == Assigned_Course.id
        ).join(
            Course, Assigned_Course.course_id == Course.id
        ).join(
            Section, Assigned_Course.section_id == Section.id
        ).join(
            User, AttendanceLog.user_id == User.id
        ).filter(
            and_(
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.academic_year == current_academic_year,
                Assigned_Course.semester == current_semester,
                AttendanceLog.date >= current_date - timedelta(days=7)  # Last 7 days
            )
        ).order_by(desc(AttendanceLog.date), desc(AttendanceLog.created_at)).limit(10).all()
        
        recent_attendance = []
        for attendance in recent_attendance_query:
            recent_attendance.append({
                "attendance_id": attendance.id,
                "student_name": f"{attendance.first_name} {attendance.last_name}",
                "course_name": attendance.course_name,
                "section_name": attendance.section_name,
                "status": attendance.status,
                "date": attendance.date.isoformat() if attendance.date else None
            })
        
        # Get total pending approvals for current semester courses only
        total_pending_approvals = db.query(Assigned_Course_Approval).join(
            Assigned_Course, Assigned_Course_Approval.assigned_course_id == Assigned_Course.id
        ).filter(
            and_(
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.academic_year == current_academic_year,
                Assigned_Course.semester == current_semester,
                Assigned_Course_Approval.status == "pending"
            )
        ).count()
        
        # Calculate attendance summary for today (current semester courses only)
        today_attendance_count = db.query(AttendanceLog).join(
            Assigned_Course, AttendanceLog.assigned_course_id == Assigned_Course.id
        ).filter(
            and_(
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.academic_year == current_academic_year,
                Assigned_Course.semester == current_semester,
                func.date(AttendanceLog.date) == current_date
            )
        ).count()
        
        # Prepare faculty info
        faculty_user = db.query(User).filter(User.id == faculty_user_id).first()
        faculty_info = {
            "user_id": faculty_user_id,
            "name": f"{faculty_user.first_name} {faculty_user.last_name}" if faculty_user else current_faculty.get("name"),
            "email": faculty_user.email if faculty_user else current_faculty.get("email"),
            "employee_number": faculty_record.employee_number,
            "current_academic_year": current_academic_year,
            "current_semester": current_semester
        }
        
        # Prepare response - only current courses, no previous courses
        dashboard_data = {
            "success": True,
            "message": "Faculty dashboard data retrieved successfully",
            "faculty_info": faculty_info,
            "current_courses": current_courses,
            "previous_courses": [],  # Empty as requested - only current semester
            "today_schedule": today_schedule,
            "all_schedules": all_schedules,
            "total_current_courses": len(current_courses),
            "total_previous_courses": 0,  # 0 as we're only showing current semester
            "total_pending_approvals": total_pending_approvals,
            "today_attendance_count": today_attendance_count,
            "recent_attendance": recent_attendance,
            "schedule_summary": {
                "total_classes_today": len(today_schedule),
                "total_weekly_schedules": len(all_schedules),
                "current_class": current_class,
                "next_class": next_class,
                "current_day": current_day
            }
        }
        
        return dashboard_data
        
    except Exception as e:
        print(f"Error getting faculty dashboard data: {e}")
        raise

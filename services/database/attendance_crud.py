from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, time
from typing import Dict, Any, List, Optional
from models import Schedule, Assigned_Course, Course, User

def debug_student_schedule(db: Session, student_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Debug function to check student's schedule for today
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
        
        debug_info = {
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
            debug_info["approvals"].append({
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
            
            debug_info["schedules"].append({
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
            
            debug_info["all_schedules"].append({
                "schedule_id": schedule.id,
                "assigned_course_id": schedule.assigned_course_id,
                "course_name": schedule.course_name,
                "day_of_week": schedule.day_of_week,
                "start_datetime": start_datetime.isoformat() if isinstance(start_datetime, datetime) else str(start_datetime),
                "end_datetime": end_datetime.isoformat() if isinstance(end_datetime, datetime) else str(end_datetime)
            })
        
        return debug_info
        
    except Exception as e:
        return {"error": str(e)}

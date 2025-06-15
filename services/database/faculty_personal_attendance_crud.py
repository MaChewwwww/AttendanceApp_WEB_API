"""
Faculty Personal Attendance CRUD Operations

This module handles database operations for faculty's personal attendance records,
where the faculty member is the attendee (using user_id field in attendance_logs).
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, extract
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from models import (
    AttendanceLog, User, Faculty, Assigned_Course, Course, 
    Section, Program, Student
)


def get_faculty_personal_attendance_history(db: Session, current_faculty: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get comprehensive attendance history for a faculty member's personal attendance records.
    
    Args:
        db: Database session
        current_faculty: Current faculty user data from JWT
        
    Returns:
        Dictionary containing faculty info, attendance records, and statistics
    """
    try:
        faculty_user_id = current_faculty["user_id"]
        
        # Get faculty information
        faculty_info = {
            "user_id": faculty_user_id,
            "name": current_faculty["name"],
            "email": current_faculty["email"],
            "employee_number": current_faculty.get("employee_number"),
            "role": current_faculty.get("role", "Faculty")
        }
        
        # Query for faculty's personal attendance records
        # This gets records where the faculty member was the attendee (user_id matches)
        attendance_query = (
            db.query(
                AttendanceLog.id.label('attendance_id'),
                AttendanceLog.assigned_course_id,
                AttendanceLog.date.label('attendance_date'),
                AttendanceLog.status,
                AttendanceLog.image,
                AttendanceLog.created_at,
                AttendanceLog.updated_at,
                
                # Course information
                Course.id.label('course_id'),
                Course.name.label('course_name'),
                Course.code.label('course_code'),
                
                # Assigned course information
                Assigned_Course.academic_year,
                Assigned_Course.semester,
                Assigned_Course.room,
                
                # Section and Program information
                Section.name.label('section_name'),
                Program.name.label('program_name'),
                Program.acronym.label('program_acronym')
            )
            .join(Assigned_Course, AttendanceLog.assigned_course_id == Assigned_Course.id)
            .join(Course, Assigned_Course.course_id == Course.id)
            .join(Section, Assigned_Course.section_id == Section.id)
            .join(Program, Section.program_id == Program.id)
            .filter(
                and_(
                    AttendanceLog.user_id == faculty_user_id,  # This is the key filter - faculty's own attendance
                    Assigned_Course.isDeleted == 0,
                    Course.isDeleted == 0,
                    Section.isDeleted == 0,
                    Program.isDeleted == 0
                )
            )
            .order_by(desc(AttendanceLog.date))
        )
        
        attendance_results = attendance_query.all()
        
        print(f"Found {len(attendance_results)} personal attendance records for faculty user_id: {faculty_user_id}")
        
        # Process attendance records
        attendance_records = []
        for record in attendance_results:
            # Extract time from attendance date
            attendance_time = record.attendance_date.strftime("%H:%M:%S") if record.attendance_date else None
            
            attendance_record = {
                "attendance_id": record.attendance_id,
                "assigned_course_id": record.assigned_course_id,
                "course_id": record.course_id,
                "course_name": record.course_name,
                "course_code": record.course_code,
                "section_name": record.section_name,
                "program_name": record.program_name,
                "program_acronym": record.program_acronym,
                "academic_year": record.academic_year,  # Academic year from assigned_course
                "semester": record.semester,
                "room": record.room,
                "attendance_date": record.attendance_date.strftime("%Y-%m-%d"),
                "attendance_time": attendance_time,  # Time field
                "status": record.status,
                "has_image": record.image is not None,
                "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            attendance_records.append(attendance_record)
        
        # Generate attendance summary statistics
        total_records = len(attendance_records)
        present_count = len([r for r in attendance_records if r["status"].lower() in ["present", "1"]])
        late_count = len([r for r in attendance_records if r["status"].lower() in ["late", "2"]])
        absent_count = len([r for r in attendance_records if r["status"].lower() in ["absent", "0"]])
        
        attendance_percentage = (present_count + late_count) / total_records * 100 if total_records > 0 else 0
        
        attendance_summary = {
            "total_records": total_records,
            "present_count": present_count,
            "late_count": late_count,
            "absent_count": absent_count,
            "attendance_percentage": round(attendance_percentage, 2),
            "status_distribution": {
                "present": present_count,
                "late": late_count,
                "absent": absent_count
            }
        }
        
        # Generate course summary
        course_stats = {}
        for record in attendance_records:
            course_name = record["course_name"]
            if course_name not in course_stats:
                course_stats[course_name] = {
                    "total_sessions": 0,
                    "present": 0,
                    "late": 0,
                    "absent": 0,
                    "course_code": record["course_code"],
                    "academic_year": record["academic_year"],
                    "semester": record["semester"]
                }
            
            course_stats[course_name]["total_sessions"] += 1
            status = record["status"].lower()
            if status in ["present", "1"]:
                course_stats[course_name]["present"] += 1
            elif status in ["late", "2"]:
                course_stats[course_name]["late"] += 1
            elif status in ["absent", "0"]:
                course_stats[course_name]["absent"] += 1
        
        # Calculate attendance percentage for each course
        for course_name, stats in course_stats.items():
            total = stats["total_sessions"]
            if total > 0:
                attended = stats["present"] + stats["late"]
                stats["attendance_percentage"] = round((attended / total) * 100, 2)
            else:
                stats["attendance_percentage"] = 0
        
        course_summary = {
            "total_courses": len(course_stats),
            "courses": course_stats
        }
        
        # Generate academic year summary
        year_stats = {}
        for record in attendance_records:
            year = record["academic_year"] or "Unknown"
            if year not in year_stats:
                year_stats[year] = {"total": 0, "present": 0, "late": 0, "absent": 0}
            
            year_stats[year]["total"] += 1
            status = record["status"].lower()
            if status in ["present", "1"]:
                year_stats[year]["present"] += 1
            elif status in ["late", "2"]:
                year_stats[year]["late"] += 1
            elif status in ["absent", "0"]:
                year_stats[year]["absent"] += 1
        
        # Calculate percentages for each academic year
        for year, stats in year_stats.items():
            total = stats["total"]
            if total > 0:
                attended = stats["present"] + stats["late"]
                stats["attendance_percentage"] = round((attended / total) * 100, 2)
            else:
                stats["attendance_percentage"] = 0
        
        academic_year_summary = {
            "years": year_stats,
            "total_years": len(year_stats)
        }
        
        return {
            "success": True,
            "message": f"Faculty personal attendance history retrieved successfully. Found {total_records} attendance records.",
            "faculty_info": faculty_info,
            "attendance_records": attendance_records,
            "total_records": total_records,
            "attendance_summary": attendance_summary,
            "course_summary": course_summary,
            "academic_year_summary": academic_year_summary
        }
        
    except Exception as e:
        print(f"Error in get_faculty_personal_attendance_history: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "message": f"Error retrieving faculty personal attendance history: {str(e)}",
            "faculty_info": {"user_id": current_faculty.get("user_id"), "name": current_faculty.get("name", "Unknown")},
            "attendance_records": [],
            "total_records": 0,
            "attendance_summary": {"total_records": 0, "present_count": 0, "late_count": 0, "absent_count": 0, "attendance_percentage": 0},
            "course_summary": {"total_courses": 0, "courses": {}},
            "academic_year_summary": {"years": {}, "total_years": 0}
        }

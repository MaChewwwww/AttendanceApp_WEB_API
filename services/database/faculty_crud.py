from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, case
from models import (
    Assigned_Course, Course, Section, Program, Faculty, User, Student, 
    Assigned_Course_Approval
)
from typing import Dict, Any, List
from datetime import datetime, date

def get_faculty_courses(db: Session, current_faculty: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all courses assigned to the faculty with student enrollment counts.
    
    Args:
        db: Database session
        current_faculty: Current faculty user data from JWT
        
    Returns:
        Dict containing faculty courses with student counts and grouping by semester
    """
    try:
        print(f"=== FACULTY COURSES DEBUG ===")
        print(f"Faculty User ID: {current_faculty.get('user_id')}")
        
        # Get faculty record
        faculty_query = db.query(Faculty).filter(Faculty.user_id == current_faculty["user_id"]).first()
        if not faculty_query:
            return {"error": "Faculty not found"}
        
        faculty_user_id = current_faculty["user_id"]
        print(f"Faculty User ID for query: {faculty_user_id}")
        
        # Define semester order (latest to oldest: Summer > 3rd > 2nd > 1st)
        def get_semester_order(semester):
            semester_order = {
                "Summer": 4,
                "3rd Semester": 3,
                "2nd Semester": 2,
                "1st Semester": 1,
                "summer": 4,  # Handle case variations
                "3rd semester": 3,
                "2nd semester": 2,
                "1st semester": 1,
                "3rd": 3,
                "2nd": 2,
                "1st": 1,
                "Third": 3,
                "Second": 2,
                "First": 1
            }
            return semester_order.get(semester, 0)  # Default to 0 for unknown semesters
        
        # Get all courses assigned to this faculty with course, section, and program info
        courses_query = db.query(
            Assigned_Course,
            Course,
            Section,
            Program
        ).join(
            Course, Course.id == Assigned_Course.course_id
        ).join(
            Section, Section.id == Assigned_Course.section_id
        ).join(
            Program, Program.id == Section.program_id
        ).filter(
            and_(
                Assigned_Course.faculty_id == faculty_user_id,  # faculty_id references users.id
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0,
                Section.isDeleted == 0,
                Program.isDeleted == 0
            )
        ).all()
        
        # Sort by academic year (desc) and semester order (Summer > 3rd > 2nd > 1st)
        courses_query = sorted(courses_query, key=lambda x: (
            -(int(x[0].academic_year.split('-')[0]) if x[0].academic_year and '-' in x[0].academic_year else 0),
            -get_semester_order(x[0].semester or "")
        ))
        
        print(f"Found {len(courses_query)} assigned courses")
        
        # Prepare faculty information
        faculty_info = {
            "faculty_id": faculty_query.id,
            "user_id": faculty_user_id,
            "name": f"{current_faculty.get('first_name', '')} {current_faculty.get('last_name', '')}".strip(),
            "email": current_faculty.get("email"),
            "employee_number": faculty_query.employee_number
        }
        
        current_courses = []
        previous_courses = []
        semester_summary = {}
        
        # Find the latest academic year and semester from the faculty's courses
        latest_academic_year = None
        latest_semester = None
        latest_semester_order = 0
        
        if courses_query:
            # First pass: find the latest academic year and semester
            for assigned_course, course, section, program in courses_query:
                if assigned_course.academic_year:
                    current_year = assigned_course.academic_year
                    current_semester = assigned_course.semester or ""
                    current_semester_order = get_semester_order(current_semester)
                    
                    # Compare to find the absolute latest
                    if latest_academic_year is None:
                        latest_academic_year = current_year
                        latest_semester = current_semester
                        latest_semester_order = current_semester_order
                    else:
                        # Compare academic years first
                        latest_year_start = int(latest_academic_year.split('-')[0]) if '-' in latest_academic_year else 0
                        current_year_start = int(current_year.split('-')[0]) if '-' in current_year else 0
                        
                        if (current_year_start > latest_year_start or 
                            (current_year_start == latest_year_start and current_semester_order > latest_semester_order)):
                            latest_academic_year = current_year
                            latest_semester = current_semester
                            latest_semester_order = current_semester_order
        
        print(f"✓ Latest academic year: {latest_academic_year}, Latest semester: {latest_semester}")
        
        for assigned_course, course, section, program in courses_query:
            print(f"Processing course: {course.name} - {section.name} ({assigned_course.academic_year}, {assigned_course.semester})")
            
            # Count students in each enrollment status for this specific course
            enrollment_counts = db.query(
                Assigned_Course_Approval.status,
                func.count(Assigned_Course_Approval.id).label("count")
            ).filter(
                Assigned_Course_Approval.assigned_course_id == assigned_course.id
            ).group_by(Assigned_Course_Approval.status).all()
            
            # Convert to dictionary
            status_counts = {status: count for status, count in enrollment_counts}
            
            enrollment_count = status_counts.get("enrolled", 0)
            pending_count = status_counts.get("pending", 0)
            rejected_count = status_counts.get("rejected", 0)
            passed_count = status_counts.get("passed", 0)
            failed_count = status_counts.get("failed", 0)
            
            # Total should include ALL students regardless of status
            total_students = sum(status_counts.values())  # Sum all status counts
            
            print(f"  Student counts: {enrollment_count} enrolled, {pending_count} pending, {rejected_count} rejected, {passed_count} passed, {failed_count} failed")
            print(f"  Total students: {total_students} (all statuses)")
            
            course_info = {
                "assigned_course_id": assigned_course.id,
                "course_id": course.id,
                "course_name": course.name,
                "course_code": course.code,
                "course_description": course.description,
                "section_id": section.id,
                "section_name": section.name,
                "program_id": program.id,
                "program_name": program.name,
                "program_acronym": program.acronym,
                "academic_year": assigned_course.academic_year,
                "semester": assigned_course.semester,
                "room": assigned_course.room,
                "enrollment_count": enrollment_count,
                "pending_count": pending_count,
                "rejected_count": rejected_count,  # Add rejected count
                "passed_count": passed_count,      # Add passed count
                "failed_count": failed_count,      # Add failed count
                "total_students": total_students,
                "created_at": assigned_course.created_at.isoformat() if assigned_course.created_at else None,
                "updated_at": assigned_course.updated_at.isoformat() if assigned_course.updated_at else None
            }
            
            # Determine if this is current or previous course based on latest found
            course_semester_order = get_semester_order(assigned_course.semester or "")
            is_current = (assigned_course.academic_year == latest_academic_year and 
                         assigned_course.semester == latest_semester)
            
            if is_current:
                current_courses.append(course_info)
                print(f"  -> Added to CURRENT courses")
            else:
                previous_courses.append(course_info)
                print(f"  -> Added to PREVIOUS courses")

            # Update semester summary with proper ordering
            year_key = assigned_course.academic_year or "Unknown"
            semester_key = assigned_course.semester or "Unknown"
            
            if year_key not in semester_summary:
                semester_summary[year_key] = {}
            
            if semester_key not in semester_summary[year_key]:
                semester_summary[year_key][semester_key] = {
                    "course_count": 0,
                    "total_enrolled": 0,
                    "total_pending": 0,
                    "total_rejected": 0,  # Add rejected summary
                    "total_passed": 0,    # Add passed summary
                    "total_failed": 0,    # Add failed summary
                    "total_students": 0,
                    "semester_order": get_semester_order(semester_key)  # Add order for frontend sorting
                }
            
            semester_summary[year_key][semester_key]["course_count"] += 1
            semester_summary[year_key][semester_key]["total_enrolled"] += enrollment_count
            semester_summary[year_key][semester_key]["total_pending"] += pending_count
            semester_summary[year_key][semester_key]["total_rejected"] += rejected_count  # Add to summary
            semester_summary[year_key][semester_key]["total_passed"] += passed_count      # Add to summary
            semester_summary[year_key][semester_key]["total_failed"] += failed_count      # Add to summary
            semester_summary[year_key][semester_key]["total_students"] += total_students
        
        # Sort semester_summary by year (descending) and semester order (Summer > 3rd > 2nd > 1st)
        sorted_semester_summary = {}
        for year in sorted(semester_summary.keys(), key=lambda x: (
            -(int(x.split('-')[0]) if x != "Unknown" and '-' in x else 0)
        )):
            sorted_semester_summary[year] = {}
            for semester in sorted(semester_summary[year].keys(), 
                                 key=lambda x: -semester_summary[year][x]["semester_order"]):
                sorted_semester_summary[year][semester] = semester_summary[year][semester]
        
        print(f"✓ Current courses: {len(current_courses)}")
        print(f"✓ Previous courses: {len(previous_courses)}")
        print(f"✓ Semester summary (ordered): {sorted_semester_summary}")
        
        return {
            "success": True,
            "message": "Faculty courses retrieved successfully",
            "faculty_info": faculty_info,
            "current_courses": current_courses,
            "previous_courses": previous_courses,
            "total_current": len(current_courses),
            "total_previous": len(previous_courses),
            "semester_summary": sorted_semester_summary
        }
        
    except Exception as e:
        print(f"Error in get_faculty_courses: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Database error: {str(e)}"}

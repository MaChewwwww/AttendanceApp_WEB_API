"""
Database creation operations for AttendanceApp API
Contains database modification and creation operations
"""
from sqlalchemy.orm import Session
from typing import Dict, Any
from models import Student, Section, Assigned_Course, Assigned_Course_Approval

def assign_student_to_section(
    db: Session, 
    current_student: Dict[str, Any], 
    section_id: int
) -> Dict[str, Any]:
    """
    Assign student to a section and create Assigned_Course_Approval records
    
    Args:
        db: Database session
        current_student: Current student data from JWT
        section_id: ID of the section to assign
        
    Returns:
        Dictionary with assignment result
    """
    try:
        # Get student record by user_id
        student = db.query(Student).filter(
            Student.user_id == current_student["user_id"]
        ).first()
        
        if not student:
            raise ValueError("Student record not found")
        
        # Verify section exists and is active
        section = db.query(Section).filter(
            Section.id == section_id,
            Section.isDeleted == 0
        ).first()
        
        if not section:
            raise ValueError("Section not found or has been deleted")
        
        # Update student's section
        student.section = section_id
        
        # Get all assigned courses for this section
        assigned_courses = db.query(Assigned_Course).filter(
            Assigned_Course.section_id == section_id,
            Assigned_Course.isDeleted == 0
        ).all()

        # Only use assigned courses from the latest academic_year
        def get_academic_year_start(academic_year_str):
            if not academic_year_str or academic_year_str == "Unknown":
                return None
            try:
                if "-" in academic_year_str:
                    return int(academic_year_str.split("-")[0])
                return int(academic_year_str)
            except Exception:
                return None
        academic_years = [ac.academic_year for ac in assigned_courses if ac.academic_year]
        latest_academic_year = None
        if academic_years:
            valid_years = [(y, get_academic_year_start(y)) for y in academic_years if get_academic_year_start(y) is not None]
            if valid_years:
                latest_academic_year = max(valid_years, key=lambda x: x[1])[0]
        filtered_courses = [ac for ac in assigned_courses if ac.academic_year == latest_academic_year]

        # Create Assigned_Course_Approval records for each course in latest academic_year
        approval_records_created = 0
        for assigned_course in filtered_courses:
            # Check if approval already exists
            existing_approval = db.query(Assigned_Course_Approval).filter(
                Assigned_Course_Approval.assigned_course_id == assigned_course.id,
                Assigned_Course_Approval.student_id == student.id
            ).first()
            if not existing_approval:
                approval = Assigned_Course_Approval(
                    assigned_course_id=assigned_course.id,
                    student_id=student.id,
                    status="pending"
                )
                db.add(approval)
                approval_records_created += 1
        # Commit the transaction
        db.commit()
        db.refresh(student)
        return {
            "success": True,
            "message": f"Student successfully assigned to section {section.name}",
            "student_id": student.id,
            "section_id": section_id,
            "section_name": section.name,
            "assigned_courses_count": len(filtered_courses),
            "approval_records_created": approval_records_created
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error assigning student to section: {e}")
        raise

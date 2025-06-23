from sqlalchemy.orm import Session
from sqlalchemy import and_
from models import (
    Assigned_Course, Course, Faculty, User, Student, 
    Assigned_Course_Approval, AttendanceLog
)
from typing import Dict, Any, Optional
from datetime import datetime

def update_student_enrollment_status(
    db: Session, 
    current_faculty: Dict[str, Any], 
    assigned_course_id: int, 
    student_id: int, 
    new_status: str,
    rejection_reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update student enrollment status in assigned_course_approval table.
    
    Args:
        db: Database session
        current_faculty: Current faculty user data from JWT
        assigned_course_id: ID of the assigned course
        student_id: ID of the student
        new_status: New status to set
        rejection_reason: Reason for rejection (required if status is "rejected")
        
    Returns:
        Dict containing update result and student information
    """
    try:
        print(f"=== UPDATE STUDENT STATUS DEBUG ===")
        print(f"Faculty User ID: {current_faculty.get('user_id')}")
        print(f"Assigned Course ID: {assigned_course_id}")
        print(f"Student ID: {student_id}")
        print(f"New Status: {new_status}")
        print(f"Rejection Reason: {rejection_reason}")
        
        # Validate status
        valid_statuses = ["pending", "enrolled", "rejected", "passed", "failed"]
        if new_status.lower() not in valid_statuses:
            print(f"❌ Invalid status validation failed")
            return {"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
        
        print(f"✓ Status validation passed")
        
        # If status is rejected, rejection_reason is required
        if new_status.lower() == "rejected" and (not rejection_reason or rejection_reason.strip() == ""):
            print(f"❌ Rejection reason validation failed - rejection_reason: '{rejection_reason}'")
            return {"error": "Rejection reason is required when status is 'rejected'"}
        
        print(f"✓ Rejection reason validation passed (rejection_reason: '{rejection_reason}')")
        
        # Get faculty user ID
        faculty_user_id = current_faculty["user_id"]
        
        # Verify faculty has permission to modify this course
        print(f"Checking faculty permission for course {assigned_course_id} and faculty {faculty_user_id}")
        course_check = db.query(Assigned_Course).filter(
            and_(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.faculty_id == faculty_user_id,
                Assigned_Course.isDeleted == 0
            )
        ).first()
        
        if not course_check:
            print(f"❌ Course permission check failed")
            # Debug: Check what courses this faculty has
            faculty_courses = db.query(Assigned_Course).filter(
                Assigned_Course.faculty_id == faculty_user_id
            ).all()
            print(f"Faculty has access to courses: {[c.id for c in faculty_courses]}")
            return {"error": "Course not found or you don't have permission to modify this course"}
        
        print(f"✓ Faculty permission verified for course: {course_check.id}")
        
        # Debug: Check if student exists
        student_exists = db.query(Student).filter(Student.id == student_id).first()
        if not student_exists:
            print(f"❌ Student {student_id} does not exist")
            return {"error": f"Student with ID {student_id} not found"}
        
        print(f"✓ Student {student_id} exists: {student_exists.student_number}")
        
        # Check for existing approval record
        print(f"Looking for existing approval record...")
        approval_record = db.query(Assigned_Course_Approval).filter(
            and_(
                Assigned_Course_Approval.assigned_course_id == assigned_course_id,
                Assigned_Course_Approval.student_id == student_id
            )
        ).first()
        
        print(f"Approval record query result: {approval_record}")
        
        old_status = "attending"  # Default for students without formal approval
        
        if not approval_record:
            print(f"❌ No existing approval record found")
            
            # Check if student has attendance records for this course
            print(f"Checking for attendance records...")
            attendance_check = db.query(AttendanceLog).join(
                User, User.id == AttendanceLog.user_id
            ).join(
                Student, Student.user_id == User.id
            ).filter(
                and_(
                    Student.id == student_id,
                    AttendanceLog.assigned_course_id == assigned_course_id
                )
            ).first()
            
            print(f"Attendance check result: {attendance_check}")
            
            if not attendance_check:
                print(f"❌ Student {student_id} has no attendance records for course {assigned_course_id}")
                return {"error": f"Student has no enrollment or attendance records for this course"}
            
            print(f"✓ Student has attendance records. Creating new approval record...")
            print(f"Creating approval record with:")
            print(f"  - assigned_course_id: {assigned_course_id}")
            print(f"  - student_id: {student_id}")
            print(f"  - status: {new_status.lower()}")
            print(f"  - rejection_reason: {rejection_reason if new_status.lower() == 'rejected' else None}")
            
            # Create new approval record for attending student
            approval_record = Assigned_Course_Approval(
                assigned_course_id=assigned_course_id,
                student_id=student_id,
                status=new_status.lower(),
                rejection_reason=rejection_reason if new_status.lower() == "rejected" else None,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            print(f"New approval record object created: {approval_record}")
            print(f"Adding to database session...")
            db.add(approval_record)
            print(f"✓ New approval record added to session")
            
        else:
            print(f"✓ Found existing approval record - Current Status: {approval_record.status}")
            old_status = approval_record.status
            
            # Update the existing record
            print(f"Updating existing record:")
            print(f"  - Old status: {approval_record.status}")
            print(f"  - New status: {new_status.lower()}")
            
            approval_record.status = new_status.lower()
            approval_record.updated_at = datetime.now()
            
            # Update rejection reason if provided or clear it if not rejected
            if new_status.lower() == "rejected":
                approval_record.rejection_reason = rejection_reason
                print(f"  - Set rejection_reason: {rejection_reason}")
            else:
                approval_record.rejection_reason = None
                print(f"  - Cleared rejection_reason")
            
            print(f"✓ Updated existing approval record")
        
        # Commit the changes
        print(f"Attempting to commit changes to database...")
        try:
            db.commit()
            print(f"✓ Database commit successful")
            print(f"✓ Status updated from '{old_status}' to '{new_status}'")
        except Exception as commit_error:
            print(f"❌ Database commit failed: {commit_error}")
            db.rollback()
            print(f"❌ Error committing changes: {commit_error}")
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to save changes: {str(commit_error)}"}
        
        # Verify the update by querying the record again
        print(f"Verifying update by re-querying the record...")
        verification_record = db.query(Assigned_Course_Approval).filter(
            and_(
                Assigned_Course_Approval.assigned_course_id == assigned_course_id,
                Assigned_Course_Approval.student_id == student_id
            )
        ).first()
        
        if verification_record:
            print(f"✓ Verification successful - Current status in DB: {verification_record.status}")
            print(f"✓ Updated at: {verification_record.updated_at}")
        else:
            print(f"❌ Verification failed - Record not found after commit")
        
        # Get student information for response
        print(f"Getting student information for response...")
        student_info = db.query(Student, User).join(
            User, User.id == Student.user_id
        ).filter(Student.id == student_id).first()
        
        if student_info:
            student, user = student_info
            student_data = {
                "student_id": student.id,
                "user_id": user.id,
                "student_number": student.student_number,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email
            }
            print(f"✓ Student data prepared: {student_data}")
        else:
            student_data = None
            print(f"❌ Student data not found")
        
        response_data = {
            "success": True,
            "message": f"Student status successfully updated from '{old_status}' to '{new_status}'",
            "student_id": student_id,
            "assigned_course_id": assigned_course_id,
            "old_status": old_status,
            "new_status": new_status.lower(),
            "updated_at": approval_record.updated_at.isoformat(),
            "student_info": student_data
        }

        # Additional logic: If student has no more 'enrolled' or 'pending' Assigned_Course_Approval, set section to None
        enrolled_approvals = db.query(Assigned_Course_Approval).filter(
            Assigned_Course_Approval.student_id == student_id,
            Assigned_Course_Approval.status == "enrolled"
        ).count()
        pending_approvals = db.query(Assigned_Course_Approval).filter(
            Assigned_Course_Approval.student_id == student_id,
            Assigned_Course_Approval.status == "pending"
        ).count()
        if enrolled_approvals == 0 and pending_approvals == 0:
            print(f"No more 'enrolled' or 'pending' approvals for student {student_id}. Setting section to None.")
            student_obj = db.query(Student).filter(Student.id == student_id).first()
            if student_obj:
                student_obj.section = None
                try:
                    db.commit()
                    print(f"✓ Student section set to None and committed.")
                except Exception as commit_error:
                    print(f"❌ Error committing section update: {commit_error}")
                    db.rollback()
        else:
            print(f"Student {student_id} still has {enrolled_approvals} 'enrolled' or {pending_approvals} 'pending' approvals. Section not changed.")

        print(f"✓ Response data prepared: {response_data}")
        return response_data
        
    except Exception as e:
        print(f"❌ Unexpected error in update_student_enrollment_status: {str(e)}")
        db.rollback()  # Rollback on error
        print(f"Error in update_student_enrollment_status: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Database error: {str(e)}"}

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
        print(f"=== FACULTY COURSE DETAILS DEBUG ===")
        print(f"Faculty User ID: {current_faculty.get('user_id')}")
        print(f"Assigned Course ID: {assigned_course_id}")
        
        # Get faculty record from the current faculty data
        faculty_query = db.query(Faculty).filter(Faculty.user_id == current_faculty["user_id"]).first()
        if not faculty_query:
            print("ERROR: Faculty record not found in database")
            return {"error": "Faculty not found"}
        
        faculty_user_id = current_faculty["user_id"]  # Use user_id since Assigned_Course.faculty_id references users.id
        print(f"Faculty User ID for query: {faculty_user_id}")
        
        # Get course information and verify faculty ownership
        # Note: Assigned_Course.faculty_id references users.id, not faculties.id
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
            User, User.id == Assigned_Course.faculty_id  # faculty_id references users.id
        ).filter(
            and_(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.faculty_id == faculty_user_id,  # Use user_id directly
                Assigned_Course.isDeleted == 0
            )
        ).first()
        
        if not course_query:
            print("ERROR: Course not found or no permission")
            print(f"Looking for: assigned_course_id={assigned_course_id}, faculty_id={faculty_user_id}")
            # Debug: Check what courses this faculty has
            debug_courses = db.query(Assigned_Course).filter(
                Assigned_Course.faculty_id == faculty_user_id
            ).all()
            print(f"Faculty has {len(debug_courses)} courses: {[c.id for c in debug_courses]}")
            return {"error": "Course not found or you don't have permission to access this course"}
        
        (assigned_course, course, section, program, 
         faculty_user_id, faculty_first_name, faculty_last_name, faculty_email) = course_query
        
        print(f"✓ Course found: {course.name} ({course.code})")
        print(f"✓ Section: {section.name}")
        print(f"✓ Program: {program.name}")
        
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
        
        print(f"✓ Faculty info prepared: {faculty_info['name']}")
        
        # Get all students in this course with their enrollment status
        print(f"=== DEBUGGING STUDENT ENROLLMENT QUERY ===")
        print(f"Looking for enrollments in assigned_course_id: {assigned_course_id}")
        
        # First, let's check if there are any assigned_course_approval records for this course
        approval_count = db.query(func.count(Assigned_Course_Approval.id)).filter(
            Assigned_Course_Approval.assigned_course_id == assigned_course_id
        ).scalar()
        print(f"Total assigned_course_approval records for this course: {approval_count}")
        
        # Check what approval records exist
        approval_records = db.query(Assigned_Course_Approval).filter(
            Assigned_Course_Approval.assigned_course_id == assigned_course_id
        ).all()
        print(f"Approval records found: {len(approval_records)}")
        for approval in approval_records:
            print(f"  - Student ID: {approval.student_id}, Status: {approval.status}")
        
        # Check if students exist for these student_ids
        if approval_records:
            student_ids = [approval.student_id for approval in approval_records]
            existing_students = db.query(Student).filter(Student.id.in_(student_ids)).all()
            print(f"Students found for these IDs: {len(existing_students)}")
            for student in existing_students:
                user = db.query(User).filter(User.id == student.user_id).first()
                print(f"  - Student {student.id}: {user.first_name} {user.last_name} (User ID: {student.user_id}, isDeleted: {user.isDeleted})")
        
        # Let's also check who has attendance records for this course
        attendance_users = db.query(
            AttendanceLog.user_id,
            func.count(AttendanceLog.id).label("attendance_count")
        ).filter(
            AttendanceLog.assigned_course_id == assigned_course_id
        ).group_by(AttendanceLog.user_id).all()
        
        print(f"Users with attendance records: {len(attendance_users)}")
        for user_id, count in attendance_users:
            user = db.query(User).filter(User.id == user_id).first()
            student = db.query(Student).filter(Student.user_id == user_id).first()
            print(f"  - User {user_id}: {user.first_name} {user.last_name} (Student ID: {student.id if student else 'None'}, Attendance: {count})")
        
        # Try to get students from approval records first
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
                User.isDeleted == 0  # Only filter User.isDeleted, Student doesn't have isDeleted
            )
        ).all()
        
        print(f"Students from approval records: {len(students_query)} students")
        
        # If no approval records exist, get students from attendance records
        if len(students_query) == 0 and len(attendance_users) > 0:
            print("No approval records found, getting students from attendance records...")
            
            # Get students who have submitted attendance for this course
            attendance_students_query = db.query(
                Student,
                User
            ).join(
                User, User.id == Student.user_id
            ).join(
                AttendanceLog, AttendanceLog.user_id == User.id
            ).filter(
                and_(
                    AttendanceLog.assigned_course_id == assigned_course_id,
                    User.isDeleted == 0
                )
            ).distinct().all()
            
            print(f"Students from attendance records: {len(attendance_students_query)} students")
            
            # Convert to the expected format for processing
            students_query = []
            for student, user in attendance_students_query:
                # Create a mock approval record for students found in attendance
                mock_approval = type('MockApproval', (), {
                    'status': 'attending',  # Special status for students without formal approval
                    'rejection_reason': None,
                    'created_at': None,
                    'updated_at': None
                })()
                students_query.append((student, user, mock_approval))
        
        print(f"Final students_query result: {len(students_query)} students")
        print("=== END DEBUGGING STUDENT ENROLLMENT QUERY ===")

        # Process students by enrollment status
        enrolled_students = []
        pending_students = []
        rejected_students = []
        passed_students = []  # Students with "passed" status
        failed_students = []  # Students with "failed" status or poor attendance
        attending_students = []  # New category for students without formal approval
        
        enrollment_summary = {
            "enrolled": 0,
            "pending": 0,
            "rejected": 0,
            "passed": 0,  # Students who successfully completed the course
            "failed": 0,  # Students who failed the course
            "attending": 0,  # Students with attendance but no approval
            "total": 0  # This will be the sum of ALL students regardless of status
        }
        
        for student, user, approval in students_query:
            print(f"Processing student: {user.first_name} {user.last_name} ({student.student_number}) - Status: {approval.status}")
            
            # Get attendance summary for this student using correct syntax
            attendance_stats = db.query(
                func.count(AttendanceLog.id).label("total_sessions"),
                func.sum(case((AttendanceLog.status == "present", 1), else_=0)).label("present_count"),
                func.sum(case((AttendanceLog.status == "absent", 1), else_=0)).label("absent_count"),
                func.sum(case((AttendanceLog.status == "late", 1), else_=0)).label("late_count")
            ).filter(
                and_(
                    AttendanceLog.user_id == user.id,  # AttendanceLog uses user_id
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
            
            # Determine if student failed based on attendance (75% minimum requirement)
            attendance_failed = attendance_percentage < 75 if total_sessions > 0 else False
            
            # Determine failed status (1 if failed, 0 if passing)
            failed_count = 1 if attendance_failed else 0
            
            print(f"  Attendance: {present_count}P + {late_count}L + {absent_count}A = {total_sessions} total ({attendance_percentage}%)")
            print(f"  Attendance Status: {'FAILED' if attendance_failed else 'PASSING'} (Minimum 75% required)")
            
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
            
            # Categorize by enrollment status - but still count ALL towards total
            if approval.status == "enrolled":
                enrolled_students.append(student_info)
                enrollment_summary["enrolled"] += 1
                print(f"  -> Added to ENROLLED students")
            elif approval.status == "pending":
                pending_students.append(student_info)
                enrollment_summary["pending"] += 1
                print(f"  -> Added to PENDING students")
            elif approval.status == "rejected":
                rejected_students.append(student_info)
                enrollment_summary["rejected"] += 1
                print(f"  -> Added to REJECTED students")
            elif approval.status == "passed":
                passed_students.append(student_info)
                enrollment_summary["passed"] += 1
                print(f"  -> Added to PASSED students")
            elif approval.status == "failed" or (approval.status == "enrolled" and attendance_failed):
                # Students with explicit "failed" status OR enrolled students who failed due to poor attendance
                failed_students.append(student_info)
                enrollment_summary["failed"] += 1
                print(f"  -> Added to FAILED students (Status: {approval.status}, Attendance Failed: {attendance_failed})")
            elif approval.status == "attending":
                attending_students.append(student_info)
                enrollment_summary["attending"] += 1
                print(f"  -> Added to ATTENDING students (no formal approval)")
            else:
                # For any other status, categorize based on attendance if they have attendance records
                if total_sessions > 0:
                    if attendance_failed:
                        failed_students.append(student_info)
                        enrollment_summary["failed"] += 1
                        print(f"  -> Added to FAILED students (Unknown status but poor attendance)")
                    else:
                        attending_students.append(student_info)
                        enrollment_summary["attending"] += 1
                        print(f"  -> Added to ATTENDING students (Unknown status but good attendance)")
                else:
                    attending_students.append(student_info)
                    enrollment_summary["attending"] += 1
                    print(f"  -> Added to ATTENDING students (Unknown status, no attendance)")
            
            # Always increment total regardless of status
            enrollment_summary["total"] += 1
        
        print(f"✓ Enrollment summary: {enrollment_summary}")

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
        
        print(f"✓ Found {len(recent_attendance_query)} recent attendance records")
        
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
        
        # Calculate overall attendance summary
        total_attendance_records = db.query(func.count(AttendanceLog.id)).filter(
            AttendanceLog.assigned_course_id == assigned_course_id
        ).scalar() or 0
        
        overall_present = db.query(func.count(AttendanceLog.id)).filter(
            and_(
                AttendanceLog.assigned_course_id == assigned_course_id,
                AttendanceLog.status == "present"
            )
        ).scalar() or 0
        
        overall_late = db.query(func.count(AttendanceLog.id)).filter(
            and_(
                AttendanceLog.assigned_course_id == assigned_course_id,
                AttendanceLog.status == "late"
            )
        ).scalar() or 0
        
        overall_absent = db.query(func.count(AttendanceLog.id)).filter(
            and_(
                AttendanceLog.assigned_course_id == assigned_course_id,
                AttendanceLog.status == "absent"
            )
        ).scalar() or 0
        
        # Get total unique attendance sessions using correct field name
        total_sessions = db.query(
            func.count(func.distinct(AttendanceLog.date))
        ).filter(
            AttendanceLog.assigned_course_id == assigned_course_id
        ).scalar() or 0
        
        attendance_summary = {
            "total_records": total_attendance_records,
            "total_sessions": total_sessions,
            "present_count": overall_present,
            "late_count": overall_late,
            "absent_count": overall_absent,
            "overall_attendance_rate": round((overall_present + overall_late) / total_attendance_records * 100, 2) if total_attendance_records > 0 else 0.0
        }
        
        print(f"✓ Attendance summary: {attendance_summary}")
        print("=== FACULTY COURSE DETAILS SUCCESS ===")
        
        return {
            "success": True,
            "message": "Course details retrieved successfully",
            "course_info": course_info,
            "section_info": section_info,
            "faculty_info": faculty_info,
            "enrolled_students": enrolled_students,
            "pending_students": pending_students,
            "rejected_students": rejected_students,
            "passed_students": passed_students,  # Add passed students
            "failed_students": failed_students,  # Add failed students
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


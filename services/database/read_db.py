"""
Database query service for AttendanceApp API
Contains all database operations for different modules
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from models import Program, Section, Course, Assigned_Course, User, Student, Assigned_Course_Approval, AttendanceLog

class DatabaseQueryService:
    """Service class for handling all database queries"""
    
    @staticmethod
    def get_active_programs(db: Session) -> List[Dict[str, Any]]:
        """
        Get all active programs where isDeleted = 0
        
        Args:
            db: Database session
            
        Returns:
            List of program dictionaries
        """
        try:
            programs = db.query(Program).filter(
                Program.isDeleted == 0
            ).all()
            
            program_list = []
            for program in programs:
                program_info = {
                    "id": program.id,
                    "name": program.name,
                    "acronym": program.acronym,
                    "code": program.code,
                    "description": program.description,
                    "color": program.color,
                    "created_at": program.created_at.isoformat() if program.created_at else None,
                    "updated_at": program.updated_at.isoformat() if program.updated_at else None
                }
                program_list.append(program_info)
            
            return program_list
            
        except Exception as e:
            print(f"Error getting active programs: {e}")
            raise
    
    @staticmethod
    def get_sections_by_program(db: Session, program_id: int) -> List[Dict[str, Any]]:
        """
        Get all active sections for a specific program where isDeleted = 0
        
        Args:
            db: Database session
            program_id: ID of the program
            
        Returns:
            List of section dictionaries
            
        Raises:
            ValueError: If program not found or deleted
        """
        try:
            # Verify program exists and is active
            program = db.query(Program).filter(
                Program.id == program_id,
                Program.isDeleted == 0
            ).first()
            
            if not program:
                raise ValueError("Program not found or has been deleted")
            
            # Get all active sections for the program
            sections = db.query(Section, Program).join(
                Program, Section.program_id == Program.id
            ).filter(
                Section.program_id == program_id,
                Section.isDeleted == 0,
                Program.isDeleted == 0
            ).all()
            
            section_list = []
            for section, program in sections:
                section_info = {
                    "id": section.id,
                    "name": section.name,
                    "program_id": section.program_id,
                    "program_name": program.name,
                    "program_acronym": program.acronym,
                    "program_code": program.code,
                    "created_at": section.created_at.isoformat() if section.created_at else None,
                    "updated_at": section.updated_at.isoformat() if section.updated_at else None
                }
                section_list.append(section_info)
            
            return section_list
            
        except Exception as e:
            print(f"Error getting sections for program {program_id}: {e}")
            raise
    
    @staticmethod
    def get_assigned_courses_by_section(db: Session, section_id: int) -> List[Dict[str, Any]]:
        """
        Get all active assigned courses for a specific section where isDeleted = 0
        
        Args:
            db: Database session
            section_id: ID of the section
            
        Returns:
            List of assigned course dictionaries
            
        Raises:
            ValueError: If section not found or deleted
        """
        try:
            # Verify section exists and is active
            section = db.query(Section).filter(
                Section.id == section_id,
                Section.isDeleted == 0
            ).first()
            
            if not section:
                raise ValueError("Section not found or has been deleted")
            
            # Get all active assigned courses for the section with related data
            assigned_courses = db.query(
                Assigned_Course,
                Course,
                User,
                Section,
                Program
            ).join(
                Course, Assigned_Course.course_id == Course.id
            ).join(
                User, Assigned_Course.faculty_id == User.id
            ).join(
                Section, Assigned_Course.section_id == Section.id
            ).join(
                Program, Section.program_id == Program.id
            ).filter(
                Assigned_Course.section_id == section_id,
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0,
                Section.isDeleted == 0,
                Program.isDeleted == 0,
                User.isDeleted == 0
            ).all()
            
            course_list = []
            for assigned_course, course, faculty, section, program in assigned_courses:
                course_info = {
                    "assigned_course_id": assigned_course.id,
                    "course_id": course.id,
                    "course_name": course.name,
                    "course_code": course.code,
                    "course_description": course.description,
                    "faculty_id": faculty.id,
                    "faculty_name": f"{faculty.first_name} {faculty.last_name}",
                    "faculty_email": faculty.email,
                    "section_id": section.id,
                    "section_name": section.name,
                    "program_id": program.id,
                    "program_name": program.name,
                    "program_acronym": program.acronym,
                    "academic_year": assigned_course.academic_year,
                    "semester": assigned_course.semester,
                    "room": assigned_course.room,
                    "created_at": assigned_course.created_at.isoformat() if assigned_course.created_at else None,
                    "updated_at": assigned_course.updated_at.isoformat() if assigned_course.updated_at else None
                }
                course_list.append(course_info)
            
            return course_list
            
        except Exception as e:
            print(f"Error getting assigned courses for section {section_id}: {e}")
            raise
    
    @staticmethod
    def get_program_by_id(db: Session, program_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific program by ID
        
        Args:
            db: Database session
            program_id: ID of the program
            
        Returns:
            Program dictionary or None if not found
        """
        try:
            program = db.query(Program).filter(
                Program.id == program_id,
                Program.isDeleted == 0
            ).first()
            
            if not program:
                return None
            
            return {
                "id": program.id,
                "name": program.name,
                "acronym": program.acronym,
                "code": program.code,
                "description": program.description,
                "color": program.color,
                "created_at": program.created_at.isoformat() if program.created_at else None,
                "updated_at": program.updated_at.isoformat() if program.updated_at else None
            }
            
        except Exception as e:
            print(f"Error getting program {program_id}: {e}")
            raise
    
    @staticmethod
    def get_section_by_id(db: Session, section_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific section by ID with program information
        
        Args:
            db: Database session
            section_id: ID of the section
            
        Returns:
            Section dictionary or None if not found
        """
        try:
            result = db.query(Section, Program).join(
                Program, Section.program_id == Program.id
            ).filter(
                Section.id == section_id,
                Section.isDeleted == 0,
                Program.isDeleted == 0
            ).first()
            
            if not result:
                return None
            
            section, program = result
            return {
                "id": section.id,
                "name": section.name,
                "program_id": section.program_id,
                "program_name": program.name,
                "program_acronym": program.acronym,
                "program_code": program.code,
                "created_at": section.created_at.isoformat() if section.created_at else None,
                "updated_at": section.updated_at.isoformat() if section.updated_at else None
            }
            
        except Exception as e:
            print(f"Error getting section {section_id}: {e}")
            raise
    
    @staticmethod
    def get_assigned_course_by_id(db: Session, assigned_course_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific assigned course by ID with full details
        
        Args:
            db: Database session
            assigned_course_id: ID of the assigned course
            
        Returns:
            Assigned course dictionary or None if not found
        """
        try:
            result = db.query(
                Assigned_Course,
                Course,
                User,
                Section,
                Program
            ).join(
                Course, Assigned_Course.course_id == Course.id
            ).join(
                User, Assigned_Course.faculty_id == User.id
            ).join(
                Section, Assigned_Course.section_id == Section.id
            ).join(
                Program, Section.program_id == Program.id
            ).filter(
                Assigned_Course.id == assigned_course_id,
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0,
                Section.isDeleted == 0,
                Program.isDeleted == 0,
                User.isDeleted == 0
            ).first()
            
            if not result:
                return None
            
            assigned_course, course, faculty, section, program = result
            return {
                "assigned_course_id": assigned_course.id,
                "course_id": course.id,
                "course_name": course.name,
                "course_code": course.code,
                "course_description": course.description,
                "faculty_id": faculty.id,
                "faculty_name": f"{faculty.first_name} {faculty.last_name}",
                "faculty_email": faculty.email,
                "section_id": section.id,
                "section_name": section.name,
                "program_id": program.id,
                "program_name": program.name,
                "program_acronym": program.acronym,
                "academic_year": assigned_course.academic_year,
                "semester": assigned_course.semester,
                "room": assigned_course.room,
                "created_at": assigned_course.created_at.isoformat() if assigned_course.created_at else None,
                "updated_at": assigned_course.updated_at.isoformat() if assigned_course.updated_at else None
            }
            
        except Exception as e:
            print(f"Error getting assigned course {assigned_course_id}: {e}")
            raise
    
    @staticmethod
    def assign_student_to_section(db: Session, student_id: int, section_id: int) -> Dict[str, Any]:
        """
        Assign a student to a section and create Assigned_Course_Approval records
        
        Args:
            db: Database session
            student_id: ID of the student (from students table)
            section_id: ID of the section
            
        Returns:
            Dictionary with assignment result
            
        Raises:
            ValueError: If student or section not found
        """
        try:
            # Verify student exists and is active
            student = db.query(Student).join(User).filter(
                Student.id == student_id,
                User.isDeleted == 0
            ).first()
            
            if not student:
                raise ValueError("Student not found or has been deleted")
            
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
            
            # Create Assigned_Course_Approval records for each course
            approval_records = []
            for assigned_course in assigned_courses:
                # Check if approval already exists
                existing_approval = db.query(Assigned_Course_Approval).filter(
                    Assigned_Course_Approval.assigned_course_id == assigned_course.id,
                    Assigned_Course_Approval.student_id == student_id
                ).first()
                
                if not existing_approval:
                    approval = Assigned_Course_Approval(
                        assigned_course_id=assigned_course.id,
                        student_id=student_id,
                        status="pending"
                    )
                    db.add(approval)
                    approval_records.append({
                        "assigned_course_id": assigned_course.id,
                        "status": "pending"
                    })
            
            # Commit the transaction
            db.commit()
            db.refresh(student)
            
            return {
                "success": True,
                "message": f"Student successfully assigned to section {section.name}",
                "student_id": student_id,
                "section_id": section_id,
                "section_name": section.name,
                "assigned_courses_count": len(assigned_courses),
                "approval_records_created": len(approval_records)
            }
            
        except Exception as e:
            db.rollback()
            print(f"Error assigning student to section: {e}")
            raise
    
    @staticmethod
    def get_student_by_user_id(db: Session, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get student record by user ID
        
        Args:
            db: Database session
            user_id: ID of the user
            
        Returns:
            Student dictionary or None if not found
        """
        try:
            result = db.query(Student, User).join(
                User, Student.user_id == User.id
            ).filter(
                Student.user_id == user_id,
                User.isDeleted == 0
            ).first()
            
            if not result:
                return None
            
            student, user = result
            return {
                "student_id": student.id,
                "user_id": student.user_id,
                "student_number": student.student_number,
                "section_id": student.section,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email
            }
            
        except Exception as e:
            print(f"Error getting student by user ID {user_id}: {e}")
            raise
    
    @staticmethod
    def get_student_courses(db: Session, current_student: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get all current and previous courses for a student with enrollment status
        
        Args:
            db: Database session
            current_student: Current student data from JWT
            
        Returns:
            Dictionary with current and previous courses
        """
        try:
            user_id = current_student.get("user_id")
            student_id = current_student.get("student_id")
            current_section_id = current_student.get("section_id")
            
            if not user_id:
                raise ValueError("User ID not found in authentication data")
            
            # If student_id is not in JWT data, fetch it from database
            if not student_id:
                print(f"Student ID not in JWT, fetching from database for user_id: {user_id}")
                student_data = DatabaseQueryService.get_student_by_user_id(db, user_id)
                if not student_data:
                    raise ValueError("Student record not found for this user")
                student_id = student_data["student_id"]
                # Update current_section_id if not present
                if not current_section_id:
                    current_section_id = student_data["section_id"]
                print(f"Found student_id: {student_id}, section_id: {current_section_id}")
            
            # 1A. Get ALL courses from student's current section (regardless of enrollment status)
            current_courses = []
            if current_section_id:
                print(f"Fetching ALL courses for current section_id: {current_section_id}")
                current_courses_query = db.query(
                    Assigned_Course,
                    Course,
                    User,
                    Section,
                    Program,
                    Assigned_Course_Approval
                ).join(
                    Course, Assigned_Course.course_id == Course.id
                ).join(
                    User, Assigned_Course.faculty_id == User.id
                ).join(
                    Section, Assigned_Course.section_id == Section.id
                ).join(
                    Program, Section.program_id == Program.id
                ).outerjoin(
                    Assigned_Course_Approval, 
                    (Assigned_Course_Approval.assigned_course_id == Assigned_Course.id) &
                    (Assigned_Course_Approval.student_id == student_id)
                ).filter(
                    Assigned_Course.section_id == current_section_id,
                    Assigned_Course.isDeleted == 0,
                    Course.isDeleted == 0,
                    Section.isDeleted == 0,
                    Program.isDeleted == 0,
                    User.isDeleted == 0
                ).all()
                
                for assigned_course, course, faculty, section, program, approval in current_courses_query:
                    course_info = {
                        "assigned_course_id": assigned_course.id,
                        "course_id": course.id,
                        "course_name": course.name,
                        "course_code": course.code,
                        "course_description": course.description,
                        "faculty_id": faculty.id,
                        "faculty_name": f"{faculty.first_name} {faculty.last_name}",
                        "faculty_email": faculty.email,
                        "section_id": section.id,
                        "section_name": section.name,
                        "program_id": program.id,
                        "program_name": program.name,
                        "program_acronym": program.acronym,
                        "academic_year": assigned_course.academic_year,
                        "semester": assigned_course.semester,
                        "room": assigned_course.room,
                        "enrollment_status": approval.status if approval else "not_enrolled",
                        "rejection_reason": approval.rejection_reason if approval else None,
                        "course_type": "current",
                        "created_at": assigned_course.created_at.isoformat() if assigned_course.created_at else None,
                        "updated_at": assigned_course.updated_at.isoformat() if assigned_course.updated_at else None
                    }
                    current_courses.append(course_info)
                print(f"Found {len(current_courses)} current courses (all courses in current section)")
            else:
                print("No current section assigned to student")
            
            # 1B. Get previous courses ONLY from attendance logs where student attended but is NOT in current section
            previous_courses = []
            if current_section_id:  # Only look for previous courses if student has a current section
                print(f"Fetching previous courses for user_id: {user_id} (excluding current section {current_section_id})")
                previous_courses_query = db.query(
                    Assigned_Course,
                    Course,
                    User,
                    Section,
                    Program,
                    Assigned_Course_Approval
                ).join(
                    AttendanceLog, AttendanceLog.assigned_course_id == Assigned_Course.id
                ).join(
                    Course, Assigned_Course.course_id == Course.id
                ).join(
                    User, Assigned_Course.faculty_id == User.id
                ).join(
                    Section, Assigned_Course.section_id == Section.id
                ).join(
                    Program, Section.program_id == Program.id
                ).outerjoin(
                    Assigned_Course_Approval,
                    (Assigned_Course_Approval.assigned_course_id == Assigned_Course.id) &
                    (Assigned_Course_Approval.student_id == student_id)
                ).filter(
                    AttendanceLog.user_id == user_id,
                    Assigned_Course.section_id != current_section_id,  # Exclude current section
                    Assigned_Course.isDeleted == 0,
                    Course.isDeleted == 0,
                    User.isDeleted == 0
                ).distinct().all()
                
                for assigned_course, course, faculty, section, program, approval in previous_courses_query:
                    course_info = {
                        "assigned_course_id": assigned_course.id,
                        "course_id": course.id,
                        "course_name": course.name,
                        "course_code": course.code,
                        "course_description": course.description,
                        "faculty_id": faculty.id,
                        "faculty_name": f"{faculty.first_name} {faculty.last_name}",
                        "faculty_email": faculty.email,
                        "section_id": section.id,
                        "section_name": section.name,
                        "program_id": program.id,
                        "program_name": program.name,
                        "program_acronym": program.acronym,
                        "academic_year": assigned_course.academic_year,
                        "semester": assigned_course.semester,
                        "room": assigned_course.room,
                        "enrollment_status": approval.status if approval else "attended_without_enrollment",
                        "rejection_reason": approval.rejection_reason if approval else None,
                        "course_type": "previous",
                        "created_at": assigned_course.created_at.isoformat() if assigned_course.created_at else None,
                        "updated_at": assigned_course.updated_at.isoformat() if assigned_course.updated_at else None
                    }
                    previous_courses.append(course_info)
                print(f"Found {len(previous_courses)} previous courses (from attendance logs, excluding current section)")
            else:
                # If no current section, all attended courses are considered "previous"
                print(f"No current section - fetching all attended courses as previous for user_id: {user_id}")
                previous_courses_query = db.query(
                    Assigned_Course,
                    Course,
                    User,
                    Section,
                    Program,
                    Assigned_Course_Approval
                ).join(
                    AttendanceLog, AttendanceLog.assigned_course_id == Assigned_Course.id
                ).join(
                    Course, Assigned_Course.course_id == Course.id
                ).join(
                    User, Assigned_Course.faculty_id == User.id
                ).join(
                    Section, Assigned_Course.section_id == Section.id
                ).join(
                    Program, Section.program_id == Program.id
                ).outerjoin(
                    Assigned_Course_Approval,
                    (Assigned_Course_Approval.assigned_course_id == Assigned_Course.id) &
                    (Assigned_Course_Approval.student_id == student_id)
                ).filter(
                    AttendanceLog.user_id == user_id,
                    Assigned_Course.isDeleted == 0,
                    Course.isDeleted == 0,
                    User.isDeleted == 0
                ).distinct().all()
                
                for assigned_course, course, faculty, section, program, approval in previous_courses_query:
                    course_info = {
                        "assigned_course_id": assigned_course.id,
                        "course_id": course.id,
                        "course_name": course.name,
                        "course_code": course.code,
                        "course_description": course.description,
                        "faculty_id": faculty.id,
                        "faculty_name": f"{faculty.first_name} {faculty.last_name}",
                        "faculty_email": faculty.email,
                        "section_id": section.id,
                        "section_name": section.name,
                        "program_id": program.id,
                        "program_name": program.name,
                        "program_acronym": program.acronym,
                        "academic_year": assigned_course.academic_year,
                        "semester": assigned_course.semester,
                        "room": assigned_course.room,
                        "enrollment_status": approval.status if approval else "attended_without_enrollment",
                        "rejection_reason": approval.rejection_reason if approval else None,
                        "course_type": "previous",
                        "created_at": assigned_course.created_at.isoformat() if assigned_course.created_at else None,
                        "updated_at": assigned_course.updated_at.isoformat() if assigned_course.updated_at else None
                    }
                    previous_courses.append(course_info)
                print(f"Found {len(previous_courses)} total attended courses (no current section)")
            
            # Create enrollment summary
            all_courses = current_courses + previous_courses
            enrollment_summary = {}
            for course in all_courses:
                status = course["enrollment_status"]
                enrollment_summary[status] = enrollment_summary.get(status, 0) + 1
            
            # Prepare student info
            student_info = {
                "user_id": current_student["user_id"],
                "student_id": student_id,
                "name": current_student["name"],
                "email": current_student["email"],
                "student_number": current_student["student_number"],
                "current_section_id": current_section_id,
                "has_section": current_student.get("has_section", False)
            }
            
            print(f"Successfully retrieved courses - Current: {len(current_courses)}, Previous: {len(previous_courses)}")
            
            return {
                "success": True,
                "message": f"Retrieved {len(current_courses)} current and {len(previous_courses)} previous courses",
                "student_info": student_info,
                "current_courses": current_courses,
                "previous_courses": previous_courses,
                "total_current": len(current_courses),
                "total_previous": len(previous_courses),
                "enrollment_summary": enrollment_summary
            }
            
        except Exception as e:
            print(f"Error getting student courses: {e}")
            import traceback
            traceback.print_exc()
            raise

# Create a singleton instance for easy import
db_query = DatabaseQueryService()

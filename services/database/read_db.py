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
    def get_sections_by_program(db: Session, program_id: int, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all active sections for a specific program where isDeleted = 0
        Optionally filter out sections that the user has previously been assigned to via assigned_course_approval.
        
        Args:
            db: Database session
            program_id: ID of the program
            user_id: ID of the user (optional)
            
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
            
            # Filtering: Exclude sections that the user has previous assigned_course_approval for
            exclude_section_ids = set()
            exclude_prefixes = set()
            if user_id:
                from models import Assigned_Course_Approval, Assigned_Course
                # Get all assigned_course_approvals for this user (student)
                student = db.query(Student).filter(Student.user_id == user_id).first()
                if student:
                    approvals = db.query(Assigned_Course_Approval).filter(
                        Assigned_Course_Approval.student_id == student.id
                    ).all()
                    assigned_course_ids = [a.assigned_course_id for a in approvals]
                    if assigned_course_ids:
                        assigned_courses = db.query(Assigned_Course).filter(
                            Assigned_Course.id.in_(assigned_course_ids)
                        ).all()
                        # Get all previous section_ids and their names for this program
                        previous_sections = db.query(Section).filter(
                            Section.id.in_([ac.section_id for ac in assigned_courses]),
                            Section.program_id == program_id
                        ).all()
                        # Collect all prefixes (first character) of previous section names
                        exclude_prefixes = set(s.name[0] for s in previous_sections if s.name)
            section_list = []
            for section, program in sections:
                # Exclude if section name starts with any of the previous prefixes
                if any(section.name.startswith(prefix) for prefix in exclude_prefixes):
                    continue
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

            # Find the latest academic_year (treat as string, but try to extract start year for comparison)
            def get_academic_year_start(academic_year_str):
                if not academic_year_str or academic_year_str == "Unknown":
                    return None
                try:
                    if "-" in academic_year_str:
                        return int(academic_year_str.split("-")[0])
                    return int(academic_year_str)
                except Exception:
                    return None

            # Get all academic years
            academic_years = [ac.academic_year for ac, _, _, _, _ in assigned_courses if ac.academic_year]
            latest_academic_year = None
            if academic_years:
                valid_years = [(y, get_academic_year_start(y)) for y in academic_years if get_academic_year_start(y) is not None]
                if valid_years:
                    latest_academic_year = max(valid_years, key=lambda x: x[1])[0]

            # Filter assigned_courses to only those with the latest academic_year
            filtered_courses = [tup for tup in assigned_courses if tup[0].academic_year == latest_academic_year]

            course_list = []
            for assigned_course, course, faculty, section, program in filtered_courses:
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
        Uses assigned_course_approval as primary data source
        
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
            user_status = current_student.get("status_id")
            
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
            
            # Extract student enrollment year from student number (format: 2023-AAA)
            student_number = current_student.get("student_number", "")
            student_enrollment_year = None
            if student_number and "-" in student_number:
                try:
                    student_enrollment_year = int(student_number.split("-")[0])
                    print(f"Student enrollment year: {student_enrollment_year}")
                except ValueError:
                    print(f"Could not parse enrollment year from student number: {student_number}")
            
            # Check if user has graduated status
            is_graduated = False
            if user_status:
                # Query status table to check if user is graduated
                from models import Status
                status_record = db.query(Status).filter(Status.id == user_status).first()
                if status_record and status_record.name.lower() == "graduated":
                    is_graduated = True
                    print(f"User has graduated status - no current courses will be shown")
            
            # Helper function to extract start year from academic year format "2023-2024"
            def get_academic_year_start(academic_year_str):
                """Extract the starting year from academic year format like '2023-2024'"""
                if not academic_year_str or academic_year_str == "Unknown":
                    return None
                try:
                    # Handle format "2023-2024" -> return 2023
                    if "-" in academic_year_str:
                        return int(academic_year_str.split("-")[0])
                    # Handle single year format "2023" -> return 2023
                    return int(academic_year_str)
                except ValueError:
                    return None
            
            # Get all assigned course approvals for this student - USE THIS AS PRIMARY SOURCE
            print(f"Fetching all assigned_course_approval records for student_id: {student_id}")
            student_approvals_query = db.query(
                Assigned_Course_Approval,
                Assigned_Course,
                Course,
                User,
                Section,
                Program
            ).join(
                Assigned_Course, Assigned_Course_Approval.assigned_course_id == Assigned_Course.id
            ).join(
                Course, Assigned_Course.course_id == Course.id
            ).join(
                User, Assigned_Course.faculty_id == User.id
            ).join(
                Section, Assigned_Course.section_id == Section.id
            ).join(
                Program, Section.program_id == Program.id
            ).filter(
                Assigned_Course_Approval.student_id == student_id,
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0,
                User.isDeleted == 0
            ).all()
            
            print(f"Found {len(student_approvals_query)} total course approvals for student")
            
            # Filter by student enrollment year and group courses by academic year
            courses_by_year = {}
            for approval, assigned_course, course, faculty, section, program in student_approvals_query:
                academic_year = assigned_course.academic_year or "Unknown"
                academic_year_start = get_academic_year_start(academic_year)
                
                # Skip courses that are before the student's enrollment year
                if student_enrollment_year and academic_year_start and academic_year_start < student_enrollment_year:
                    print(f"Skipping course {course.name} from academic year {academic_year} (before enrollment year {student_enrollment_year})")
                    continue
                
                if academic_year not in courses_by_year:
                    courses_by_year[academic_year] = []
                
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
                    "academic_year": academic_year,
                    "semester": assigned_course.semester,
                    "room": assigned_course.room,
                    "enrollment_status": approval.status,  # Primary data from assigned_course_approval
                    "rejection_reason": approval.rejection_reason,  # Primary data from assigned_course_approval
                    "approval_created_at": approval.created_at.isoformat() if approval.created_at else None,
                    "approval_updated_at": approval.updated_at.isoformat() if approval.updated_at else None,
                    "created_at": assigned_course.created_at.isoformat() if assigned_course.created_at else None,
                    "updated_at": assigned_course.updated_at.isoformat() if assigned_course.updated_at else None
                }
                courses_by_year[academic_year].append(course_info)
            
            print(f"Filtered courses from enrollment year {student_enrollment_year} onwards")
            print(f"Academic years found: {list(courses_by_year.keys())}")
            
            # Find the latest academic year based on start year
            latest_academic_year = None
            if courses_by_year:
                # Sort years by their start year and get the latest
                valid_years = [(year, get_academic_year_start(year)) for year in courses_by_year.keys() if get_academic_year_start(year) is not None]
                if valid_years:
                    # Sort by start year and get the latest
                    latest_academic_year = max(valid_years, key=lambda x: x[1])[0]
                    print(f"Latest academic year found: {latest_academic_year}")
            
            # 1A. Current courses: Latest academic year courses from assigned_course_approval (if not graduated)
            current_courses = []
            if not is_graduated and latest_academic_year and latest_academic_year in courses_by_year:
                current_courses = courses_by_year[latest_academic_year].copy()
                for course in current_courses:
                    course["course_type"] = "current"
                print(f"Found {len(current_courses)} current courses for academic year {latest_academic_year}")
            else:
                if is_graduated:
                    print("User is graduated - no current courses")
                else:
                    print("No latest academic year found or no courses for latest year")
            
            # 1B. Previous courses: All other academic years from assigned_course_approval (excluding latest)
            previous_courses = []
            for year, courses in courses_by_year.items():
                if year != latest_academic_year or is_graduated:
                    for course in courses.copy():
                        course["course_type"] = "previous"
                        previous_courses.append(course)
            
            # Sort previous courses by academic year start year (most recent first)
            previous_courses.sort(key=lambda x: get_academic_year_start(x["academic_year"]) or 0, reverse=True)
            print(f"Found {len(previous_courses)} previous courses across {len(courses_by_year) - (1 if latest_academic_year and not is_graduated else 0)} academic years")
            
            # Create enrollment summary based on assigned_course_approval status
            all_courses = current_courses + previous_courses
            enrollment_summary = {}
            for course in all_courses:
                status = course["enrollment_status"]
                enrollment_summary[status] = enrollment_summary.get(status, 0) + 1
            
            # Create academic year summary
            academic_year_summary = {}
            for year, courses in courses_by_year.items():
                academic_year_summary[year] = len(courses)
            
            # Prepare student info
            student_info = {
                "user_id": current_student["user_id"],
                "student_id": student_id,
                "name": current_student["name"],
                "email": current_student["email"],
                "student_number": current_student["student_number"],
                "current_section_id": current_section_id,
                "current_academic_year": latest_academic_year,
                "student_enrollment_year": student_enrollment_year,
                "is_graduated": is_graduated,
                "has_section": current_student.get("has_section", False)
            }
            
            print(f"Successfully retrieved courses from assigned_course_approval - Current: {len(current_courses)}, Previous: {len(previous_courses)}")
            
            return {
                "success": True,
                "message": f"Retrieved {len(current_courses)} current and {len(previous_courses)} previous courses across {len(courses_by_year)} academic years",
                "student_info": student_info,
                "current_courses": current_courses,
                "previous_courses": previous_courses,
                "total_current": len(current_courses),
                "total_previous": len(previous_courses),
                "enrollment_summary": enrollment_summary,
                "academic_year_summary": academic_year_summary
            }
            
        except Exception as e:
            print(f"Error getting student courses: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    @staticmethod
    def get_course_students(db: Session, assigned_course_id: int) -> Dict[str, Any]:
        """
        Get all students enrolled in a specific course with attendance summary
        
        Args:
            db: Database session
            assigned_course_id: ID of the assigned course
            
        Returns:
            Dictionary with course info, students list, and summaries
            
        Raises:
            ValueError: If assigned course not found
        """
        try:
            print(f"[DEBUG] get_course_students called with assigned_course_id={assigned_course_id}")
            # 2A & 2E: Verify assigned course exists and get course information
            course_info_result = db.query(
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
            print(f"[DEBUG] course_info_result: {course_info_result}")
            if not course_info_result:
                print(f"[DEBUG] Assigned course not found for id={assigned_course_id}")
                raise ValueError("Assigned course not found or has been deleted")
            assigned_course, course, faculty, section, program = course_info_result
            # Prepare course information
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
            # 2A & 2B: Get all students enrolled in this course with enrollment status
            student_enrollments = db.query(
                Assigned_Course_Approval,
                Student,
                User
            ).join(
                Student, Assigned_Course_Approval.student_id == Student.id
            ).join(
                User, Student.user_id == User.id
            ).filter(
                Assigned_Course_Approval.assigned_course_id == assigned_course_id,
                User.isDeleted == 0
            ).all()
            print(f"[DEBUG] Found {len(student_enrollments)} student enrollments for course {assigned_course_id}")
            if not student_enrollments:
                print(f"[DEBUG] No student enrollments found for assigned_course_id={assigned_course_id}")
            students_list = []
            enrollment_summary = {}
            attendance_stats = {
                "total_sessions": 0,
                "students_with_attendance": 0,
                "average_attendance_percentage": 0.0
            }
            for approval, student, user in student_enrollments:
                # 2C: Get latest attendance record for this student in this course
                # Note: AttendanceLog uses user_id, not student_id
                latest_attendance = db.query(AttendanceLog).filter(
                    AttendanceLog.user_id == user.id,  # Changed from student.id to user.id
                    AttendanceLog.assigned_course_id == assigned_course_id
                ).order_by(AttendanceLog.created_at.desc()).first()
                
                # 2D: Get attendance summary for this student in this course
                # Note: AttendanceLog uses user_id, not student_id
                attendance_records = db.query(AttendanceLog).filter(
                    AttendanceLog.user_id == user.id,  # Changed from student.id to user.id
                    AttendanceLog.assigned_course_id == assigned_course_id
                ).all()
                
                # Calculate attendance statistics
                total_sessions = len(attendance_records)
                present_count = len([a for a in attendance_records if a.status == "present"])
                absent_count = len([a for a in attendance_records if a.status == "absent"])
                late_count = len([a for a in attendance_records if a.status == "late"])
                # Add failed_count (set to 0, or add your logic here)
                failed_count = 0
                # Calculate attendance percentage
                if total_sessions > 0:
                    attendance_percentage = round((present_count + late_count) / total_sessions * 100, 2)
                else:
                    attendance_percentage = 0.0
                # Prepare student information
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
                    "latest_attendance_date": latest_attendance.created_at.isoformat() if latest_attendance else None,
                    "latest_attendance_status": latest_attendance.status if latest_attendance else None,
                    "total_sessions": total_sessions,
                    "present_count": present_count,
                    "absent_count": absent_count,
                    "late_count": late_count,
                    "failed_count": failed_count,
                    "attendance_percentage": attendance_percentage
                }
                students_list.append(student_info)
                
                # Update enrollment summary
                status = approval.status
                enrollment_summary[status] = enrollment_summary.get(status, 0) + 1
                
                # Update attendance statistics
                if total_sessions > 0:
                    attendance_stats["students_with_attendance"] += 1
                    attendance_stats["total_sessions"] = max(attendance_stats["total_sessions"], total_sessions)
            
            # Calculate overall attendance statistics
            if attendance_stats["students_with_attendance"] > 0:
                total_attendance_percentage = sum([s["attendance_percentage"] for s in students_list if s["total_sessions"] > 0])
                attendance_stats["average_attendance_percentage"] = round(
                    total_attendance_percentage / attendance_stats["students_with_attendance"], 2
                )
            
            # Sort students by name
            students_list.sort(key=lambda x: x["name"])
            
            print(f"[DEBUG] Retrieved {len(students_list)} students for course {course.name}")
            print(f"[DEBUG] Enrollment summary: {enrollment_summary}")
            print(f"[DEBUG] Attendance summary: {attendance_stats}")
            
            return {
                "success": True,
                "message": f"Retrieved {len(students_list)} students for course {course.name}",
                "course_info": course_info,
                "students": students_list,
                "total_students": len(students_list),
                "enrollment_summary": enrollment_summary,
                "attendance_summary": attendance_stats
            }
        except Exception as e:
            print(f"[DEBUG] Error getting course students for assigned_course_id {assigned_course_id}: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    @staticmethod
    def get_student_attendance_history(db: Session, current_student: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get all attendance records for a student with course information
        
        Args:
            db: Database session
            current_student: Current student data from JWT
            
        Returns:
            Dictionary with attendance records and summaries
        """
        try:
            user_id = current_student.get("user_id")
            student_id = current_student.get("student_id")
            
            if not user_id:
                raise ValueError("User ID not found in authentication data")
            
            # If student_id is not in JWT data, fetch it from database
            if not student_id:
                print(f"Student ID not in JWT, fetching from database for user_id: {user_id}")
                student_data = DatabaseQueryService.get_student_by_user_id(db, user_id)
                if not student_data:
                    raise ValueError("Student record not found for this user")
                student_id = student_data["student_id"]
                print(f"Found student_id: {student_id}")
            
            # Get all attendance logs for this student with course information
            print(f"Fetching attendance records for user_id: {user_id}")
            attendance_query = db.query(
                AttendanceLog,
                Assigned_Course,
                Course,
                User,
                Section,
                Program
            ).join(
                Assigned_Course, AttendanceLog.assigned_course_id == Assigned_Course.id
            ).join(
                Course, Assigned_Course.course_id == Course.id
            ).join(
                User, Assigned_Course.faculty_id == User.id
            ).join(
                Section, Assigned_Course.section_id == Section.id
            ).join(
                Program, Section.program_id == Program.id
            ).filter(
                AttendanceLog.user_id == user_id,
                Assigned_Course.isDeleted == 0,
                Course.isDeleted == 0,
                User.isDeleted == 0
            ).order_by(AttendanceLog.date.desc()).all()
            
            print(f"Found {len(attendance_query)} attendance records for student")
            
            # Process attendance records
            attendance_records = []
            course_summary = {}
            academic_year_summary = {}
            status_counts = {"present": 0, "absent": 0, "late": 0}
            
            for attendance, assigned_course, course, faculty, section, program in attendance_query:
                # Check if attendance has an image
                has_image = attendance.image is not None and len(attendance.image) > 0
                
                # Prepare attendance record
                attendance_record = {
                    "attendance_id": attendance.id,
                    "assigned_course_id": assigned_course.id,
                    "course_id": course.id,
                    "course_name": course.name,
                    "course_code": course.code,
                    "faculty_name": f"{faculty.first_name} {faculty.last_name}",
                    "section_name": section.name,
                    "program_name": program.name,
                    "program_acronym": program.acronym,
                    "academic_year": assigned_course.academic_year,
                    "semester": assigned_course.semester,
                    "room": assigned_course.room,
                    "attendance_date": attendance.date.isoformat() if attendance.date else None,
                    "status": attendance.status,
                    "has_image": has_image,
                    "created_at": attendance.created_at.isoformat() if attendance.created_at else None,
                    "updated_at": attendance.updated_at.isoformat() if attendance.updated_at else None
                }
                
                attendance_records.append(attendance_record)
                
                # Update status counts
                if attendance.status in status_counts:
                    status_counts[attendance.status] += 1
                
                # Update course summary
                course_key = f"{course.name} ({assigned_course.academic_year})"
                if course_key not in course_summary:
                    course_summary[course_key] = {
                        "course_name": course.name,
                        "course_code": course.code,
                        "academic_year": assigned_course.academic_year,
                        "semester": assigned_course.semester,
                        "total_sessions": 0,
                        "present": 0,
                        "absent": 0,
                        "late": 0,
                        "attendance_percentage": 0.0
                    }
                
                course_summary[course_key]["total_sessions"] += 1
                if attendance.status in ["present", "absent", "late"]:
                    course_summary[course_key][attendance.status] += 1
                
                # Update academic year summary
                academic_year = assigned_course.academic_year or "Unknown"
                if academic_year not in academic_year_summary:
                    academic_year_summary[academic_year] = {
                        "total_sessions": 0,
                        "present": 0,
                        "absent": 0,
                        "late": 0,
                        "attendance_percentage": 0.0
                    }
                
                academic_year_summary[academic_year]["total_sessions"] += 1
                if attendance.status in ["present", "absent", "late"]:
                    academic_year_summary[academic_year][attendance.status] += 1
            
            # Calculate attendance percentages for course summary
            for course_key in course_summary:
                course_data = course_summary[course_key]
                total = course_data["total_sessions"]
                if total > 0:
                    attended = course_data["present"] + course_data["late"]
                    course_data["attendance_percentage"] = round((attended / total) * 100, 2)
            
            # Calculate attendance percentages for academic year summary
            for year in academic_year_summary:
                year_data = academic_year_summary[year]
                total = year_data["total_sessions"]
                if total > 0:
                    attended = year_data["present"] + year_data["late"]
                    year_data["attendance_percentage"] = round((attended / total) * 100, 2)
            
            # Calculate overall attendance statistics
            total_sessions = len(attendance_records)
            overall_attendance_percentage = 0.0
            if total_sessions > 0:
                attended_sessions = status_counts["present"] + status_counts["late"]
                overall_attendance_percentage = round((attended_sessions / total_sessions) * 100, 2)
            
            attendance_summary = {
                "total_sessions": total_sessions,
                "present_count": status_counts["present"],
                "absent_count": status_counts["absent"],
                "late_count": status_counts["late"],
                "attended_sessions": status_counts["present"] + status_counts["late"],
                "overall_attendance_percentage": overall_attendance_percentage,
                "unique_courses": len(course_summary),
                "unique_academic_years": len(academic_year_summary)
            }
            
            # Prepare student info
            student_info = {
                "user_id": current_student["user_id"],
                "student_id": student_id,
                "name": current_student["name"],
                "email": current_student["email"],
                "student_number": current_student["student_number"],
                "section_id": current_student.get("section_id"),
                "has_section": current_student.get("has_section", False)
            }
            
            print(f"Successfully retrieved {total_sessions} attendance records across {len(course_summary)} courses")
            
            return {
                "success": True,
                "message": f"Retrieved {total_sessions} attendance records across {len(course_summary)} courses and {len(academic_year_summary)} academic years",
                "student_info": student_info,
                "attendance_records": attendance_records,
                "total_records": total_sessions,
                "attendance_summary": attendance_summary,
                "course_summary": course_summary,
                "academic_year_summary": academic_year_summary
            }
            
        except Exception as e:
            print(f"Error getting student attendance history: {e}")
            import traceback
            traceback.print_exc()
            raise

# Create a singleton instance for easy import
db_query = DatabaseQueryService()

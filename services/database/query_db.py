"""
Database query service for AttendanceApp API
Contains all database operations for different modules
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from models import Program, Section, Course, Assigned_Course, User

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

# Create a singleton instance for easy import
db_query = DatabaseQueryService()

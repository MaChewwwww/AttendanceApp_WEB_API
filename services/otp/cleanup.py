import asyncio
import sqlite3
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging
from typing import Optional
import time

# Load environment variables
load_dotenv()

# Configure logging for cleanup service to write to file
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "otp_cleanup.log")

# Configure logging with file handler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

cleanup_logger = logging.getLogger("otp_cleanup")
cleanup_logger.setLevel(logging.INFO)

# Remove any existing handlers to avoid duplication
for handler in cleanup_logger.handlers[:]:
    cleanup_logger.removeHandler(handler)

# Add file handler only
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - OTP_CLEANUP - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
cleanup_logger.addHandler(file_handler)

# Remove console handler completely - no console logging except for errors
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)  # Only show ERROR level and above in console
console_formatter = logging.Formatter('🧹 OTP_CLEANUP - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
cleanup_logger.addHandler(console_handler)

# Prevent propagation to parent loggers
cleanup_logger.propagate = False

class OTPCleanupService:
    def __init__(self):
        self.db_path = os.getenv("DB_PATH")
        self.is_running = False
        self.cleanup_task: Optional[asyncio.Task] = None
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
        if not self.db_path:
            raise ValueError("DB_PATH environment variable not set")
        
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        
        cleanup_logger.info("="*80)
        cleanup_logger.info("🚀 OTP CLEANUP SERVICE INITIALIZATION")
        cleanup_logger.info("="*80)
        cleanup_logger.info(f"Database Path: {self.db_path}")
        cleanup_logger.info(f"Log File: {log_file}")
        cleanup_logger.info(f"Service Mode: Background cleanup every 15 minutes")
        cleanup_logger.info("="*80)

    def connect_db(self):
        """Create database connection with proper settings for concurrent access"""
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,  # Wait up to 30 seconds for lock
                isolation_level=None  # Autocommit mode
            )
            conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for better concurrent access
            conn.execute("PRAGMA journal_mode=WAL")
            # Set busy timeout
            conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds
            
            return conn
        except Exception as e:
            cleanup_logger.error(f"Failed to connect to database: {e}")
            raise
    
    def cleanup_expired_otps_with_retry(self):
        """Delete expired OTP records with retry logic for database locks"""
        for attempt in range(self.max_retries):
            try:
                return self.cleanup_expired_otps()
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() or "busy" in str(e).lower():
                    if attempt < self.max_retries - 1:
                        cleanup_logger.warning(f"Database locked, retrying in {self.retry_delay} seconds... (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        cleanup_logger.error(f"Database still locked after {self.max_retries} attempts, skipping cleanup")
                        return 0
                else:
                    raise
            except Exception as e:
                cleanup_logger.error(f"Unexpected error during cleanup: {e}")
                return 0
        return 0
    
    def cleanup_expired_otps(self):
        """Delete expired OTP records from the database"""
        conn = None
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            
            # Get current time
            current_time = datetime.now()
            
            # Use BEGIN IMMEDIATE to get an exclusive lock immediately
            cursor.execute("BEGIN IMMEDIATE")
            
            # Count expired OTPs before deletion
            cursor.execute("""
                SELECT COUNT(*) as count FROM otp_requests 
                WHERE expires_at < ?
            """, (current_time.isoformat(),))
            
            result = cursor.fetchone()
            expired_count = result['count'] if result else 0
            
            if expired_count > 0:
                # Delete expired OTPs
                cursor.execute("""
                    DELETE FROM otp_requests 
                    WHERE expires_at < ?
                """, (current_time.isoformat(),))
                
                cursor.execute("COMMIT")
                cleanup_logger.info(f"🧹 Cleaned up {expired_count} expired OTP records")
            else:
                cursor.execute("COMMIT")
                cleanup_logger.debug("No expired OTP records found")
            
            # Log current OTP statistics (separate transaction)
            cursor.execute("SELECT COUNT(*) as total FROM otp_requests")
            result = cursor.fetchone()
            total_otps = result['total'] if result else 0
            
            if total_otps > 0:
                cursor.execute("""
                    SELECT type, COUNT(*) as count 
                    FROM otp_requests 
                    GROUP BY type
                """)
                type_counts = cursor.fetchall()
                
                cleanup_logger.debug(f"Current OTP statistics: Total={total_otps}")
                for row in type_counts:
                    cleanup_logger.debug(f"  {row['type']}: {row['count']}")
            
            return expired_count
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() or "busy" in str(e).lower():
                cleanup_logger.warning(f"Database is busy (desktop app may be using it): {e}")
                return 0
            else:
                cleanup_logger.error(f"Database error during OTP cleanup: {e}")
                return 0
        except Exception as e:
            cleanup_logger.error(f"Error during OTP cleanup: {e}")
            return 0
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    def cleanup_old_otps(self, hours=24):
        """Delete OTPs older than specified hours with retry logic"""
        for attempt in range(self.max_retries):
            try:
                return self._cleanup_old_otps_internal(hours)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() or "busy" in str(e).lower():
                    if attempt < self.max_retries - 1:
                        cleanup_logger.warning(f"Database locked during old OTP cleanup, retrying in {self.retry_delay} seconds...")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        cleanup_logger.error(f"Database still locked after {self.max_retries} attempts, skipping old OTP cleanup")
                        return 0
                else:
                    raise
            except Exception as e:
                cleanup_logger.error(f"Unexpected error during old OTP cleanup: {e}")
                return 0
        return 0
    
    def _cleanup_old_otps_internal(self, hours=24):
        """Internal method for cleaning old OTPs"""
        conn = None
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute("BEGIN IMMEDIATE")
            
            cursor.execute("""
                SELECT COUNT(*) as count FROM otp_requests 
                WHERE created_at < ?
            """, (cutoff_time.isoformat(),))
            
            result = cursor.fetchone()
            old_count = result['count'] if result else 0
            
            if old_count > 0:
                cursor.execute("""
                    DELETE FROM otp_requests 
                    WHERE created_at < ?
                """, (cutoff_time.isoformat(),))
                
                cursor.execute("COMMIT")
                cleanup_logger.info(f"🧹 Cleaned up {old_count} OTP records older than {hours} hours")
            else:
                cursor.execute("COMMIT")
            
            return old_count
            
        except Exception as e:
            cleanup_logger.error(f"Error during old OTP cleanup: {e}")
            return 0
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    async def run_cleanup_cycle(self):
        """Run a single cleanup cycle with database lock handling"""
        try:
            cleanup_logger.info("")
            cleanup_logger.info("┌" + "─"*78 + "┐")
            cleanup_logger.info("│" + f"{'🔄 CLEANUP CYCLE STARTED':^78}" + "│")
            cleanup_logger.info("│" + f"{'Time: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^78}" + "│")
            cleanup_logger.info("└" + "─"*78 + "┘")
            
            # Clean expired OTPs with retry logic
            cleanup_logger.info("📋 Step 1: Cleaning expired OTPs...")
            expired_count = self.cleanup_expired_otps_with_retry()
            cleanup_logger.info(f"   Result: {expired_count} expired OTPs removed")
            
            # Small delay between operations to reduce lock contention
            await asyncio.sleep(1)
            
            # Clean very old OTPs (safety measure)
            cleanup_logger.info("📋 Step 2: Cleaning old OTPs (24+ hours)...")
            old_count = self.cleanup_old_otps(24)
            cleanup_logger.info(f"   Result: {old_count} old OTPs removed")
            
            # Summary
            total_removed = expired_count + old_count
            if total_removed > 0:
                cleanup_logger.info("")
                cleanup_logger.info("✅ CLEANUP SUMMARY:")
                cleanup_logger.info(f"   • Expired OTPs removed: {expired_count}")
                cleanup_logger.info(f"   • Old OTPs removed: {old_count}")
                cleanup_logger.info(f"   • Total OTPs cleaned: {total_removed}")
            else:
                cleanup_logger.info("")
                cleanup_logger.info("✅ CLEANUP SUMMARY: No OTPs required cleaning")
            
            cleanup_logger.info("┌" + "─"*78 + "┐")
            cleanup_logger.info("│" + f"{'✅ CLEANUP CYCLE COMPLETED':^78}" + "│")
            cleanup_logger.info("│" + f"{'Next cleanup in 15 minutes':^78}" + "│")
            cleanup_logger.info("└" + "─"*78 + "┘")
            cleanup_logger.info("")
            
        except Exception as e:
            cleanup_logger.error("")
            cleanup_logger.error("┌" + "─"*78 + "┐")
            cleanup_logger.error("│" + f"{'❌ CLEANUP CYCLE FAILED':^78}" + "│")
            cleanup_logger.error("└" + "─"*78 + "┘")
            cleanup_logger.error(f"Error details: {e}")
            cleanup_logger.error("")

    async def start_background_cleanup(self):
        """Start the background cleanup service"""
        if self.is_running:
            cleanup_logger.warning("Cleanup service is already running")
            return
        
        self.is_running = True
        cleanup_logger.info("")
        cleanup_logger.info("🚀 BACKGROUND CLEANUP SERVICE STARTED")
        cleanup_logger.info("   • Interval: Every 15 minutes")
        cleanup_logger.info("   • Running initial cleanup cycle...")
        cleanup_logger.info("")
        
        # Run initial cleanup
        await self.run_cleanup_cycle()
        
        try:
            while self.is_running:
                # Wait 15 minutes (900 seconds)
                await asyncio.sleep(900)
                
                if self.is_running:  # Check again in case service was stopped
                    await self.run_cleanup_cycle()
                
        except asyncio.CancelledError:
            cleanup_logger.info("")
            cleanup_logger.info("🛑 OTP cleanup service cancelled")
            cleanup_logger.info("")
        except Exception as e:
            cleanup_logger.error("")
            cleanup_logger.error(f"❌ Error in cleanup service: {e}")
            cleanup_logger.error("")
        finally:
            self.is_running = False

    def start_service(self):
        """Start the cleanup service as a background task"""
        if self.cleanup_task and not self.cleanup_task.done():
            cleanup_logger.warning("Cleanup service task already exists")
            return self.cleanup_task
        
        self.cleanup_task = asyncio.create_task(self.start_background_cleanup())
        return self.cleanup_task
    
    async def stop_service(self):
        """Stop the cleanup service"""
        self.is_running = False
        
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        cleanup_logger.info("")
        cleanup_logger.info("="*80)
        cleanup_logger.info("🛑 OTP CLEANUP SERVICE STOPPED")
        cleanup_logger.info("="*80)
        cleanup_logger.info("")

# Global cleanup service instance
_cleanup_service: Optional[OTPCleanupService] = None

def get_cleanup_service() -> OTPCleanupService:
    """Get or create the global cleanup service instance"""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = OTPCleanupService()
    return _cleanup_service

async def start_cleanup_service():
    """Start the global cleanup service"""
    service = get_cleanup_service()
    return service.start_service()

async def stop_cleanup_service():
    """Stop the global cleanup service"""
    global _cleanup_service
    if _cleanup_service:
        await _cleanup_service.stop_service()

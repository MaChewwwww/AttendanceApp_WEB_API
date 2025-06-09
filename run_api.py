"""
Script to run the AttendanceApp API with proper console output
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    """Main function to run the API server"""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    
    # Change to the API directory
    os.chdir(script_dir)
    
    # Set environment variables for better console output
    os.environ["PYTHONUNBUFFERED"] = "1"  # Ensure real-time output
    os.environ["PYTHONIOENCODING"] = "utf-8"  # Fix encoding issues
    
    print("=" * 60)
    print("[STARTING] AttendanceApp API Server")
    print("=" * 60)
    print(f"[INFO] Working Directory: {script_dir}")
    print(f"[INFO] Python Version: {sys.version}")
    print("=" * 60)
    
    try:
        # Run uvicorn with the main app (note: Main.py not main.py)
        cmd = [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "localhost",
            "--port", "8000",
            "--reload",
            "--log-level", "info"
        ]
        
        print(f"[CMD] Running command: {' '.join(cmd)}")
        print("=" * 60)
        print("[OUTPUT] API Server Output:")
        print("=" * 60)
        
        # Run the command and stream output in real-time
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace'  # Replace problematic characters
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(line, end='')
        
        # Wait for process to complete
        process.wait()
        
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("[STOPPED] API Server stopped by user (Ctrl+C)")
        print("=" * 60)
    except Exception as e:
        print(f"\n[ERROR] Error running API server: {e}")
        print("=" * 60)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import importlib.util
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get paths from environment variables
DESKTOP_APP_PATH = os.getenv("DESKTOP_APP_PATH")
DB_PATH = os.getenv("DB_PATH")

# Import Base directly from the desktop app
try:
    # Import models dynamically from file path
    desktop_models_path = os.path.join(DESKTOP_APP_PATH, "models.py")
    if not os.path.exists(desktop_models_path):
        raise ImportError(f"Models file not found at {desktop_models_path}")
    
    spec = importlib.util.spec_from_file_location("desktop_models", desktop_models_path)
    desktop_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(desktop_models)
    
    # Use Base directly from the loaded module
    Base = desktop_models.Base
    
except ImportError as e:
    print(f"Error importing models: {e}")
    raise

# Ensure database directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Create SQLite database URL with absolute path
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine with connection pool
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Needed for FastAPI with SQLite
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
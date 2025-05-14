from sqlalchemy import create_engine
from models import Base

# MySQL connection string format:
# mysql+pymysql://<username>:<password>@<host>/<database>
engine = create_engine("mysql+pymysql://root:@localhost/AttendanceApp")

Base.metadata.create_all(bind=engine)
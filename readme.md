# AttendanceApp FastAPI API

This project is a FastAPI-based web API for the AttendanceApp. It uses environment variables for database configuration.

## Prerequisites

- Python 3.10 or newer
- [pip](https://pip.pypa.io/en/stable/)
- [virtualenv](https://virtualenv.pypa.io/en/latest/) (optional but recommended)

## Setup

1. **Clone the repository**
   ```sh
   git clone <your-repo-url>
   cd AttendanceApp_WEB_API
   ```

2. **Create and activate a virtual environment**
   ```sh
   python -m venv venv
   ```
   - On Windows:
     ```sh
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```sh
     source venv/bin/activate
     ```

3. **Install dependencies**
   ```sh
   pip install fastapi uvicorn python-dotenv bcrypt email-validator
   ```
   Or, to install all dependencies at once (recommended for Pydantic email validation):
   ```sh
   pip install "pydantic[email]" fastapi uvicorn python-dotenv bcrypt
   ```

4. **Configure environment variables**
   Edit the `.env` file to set your database credentials:
   ```
   DB_HOST=localhost
   DB_USER=root
   DB_PASS=
   DB_NAME=AttendanceApp
   ```

5. **Running the API**
   ```sh
   uvicorn main:app --reload
   ```
   > **Note:** Use `Main:app` if your file is named `Main.py`. Use `main:app` if your file is named `main.py`.

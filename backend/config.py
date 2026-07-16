import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
(BASE_DIR / 'database').mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

class Config:
    API_PORT = int(os.getenv('API_PORT', '8000'))
    DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    DATA_PROVIDER = os.getenv('DATA_PROVIDER', 'google_drive')
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(BASE_DIR / "credentials.json"))
    GOOGLE_DRIVE_ROOT_FOLDER_ID = os.getenv('GOOGLE_DRIVE_ROOT_FOLDER_ID', '')
    GOOGLE_DRIVE_DATA_FILE = os.getenv('GOOGLE_DRIVE_DATA_FILE', 'hub-data.json')
    GOOGLE_DRIVE_SCOPES = os.getenv(
        'GOOGLE_DRIVE_SCOPES',
        'https://www.googleapis.com/auth/drive.readonly'
    ).split(',')
    SQL_DRIVER = os.getenv('SQL_DRIVER', '')
    SQL_HOST = os.getenv('SQL_HOST', '')
    SQL_PORT = os.getenv('SQL_PORT', '')
    SQL_DATABASE = os.getenv('SQL_DATABASE', '')
    SQL_USER = os.getenv('SQL_USER', '')
    SQL_PASSWORD = os.getenv('SQL_PASSWORD', '')
    SQLALCHEMY_DATABASE_URI = os.getenv(
    'DATABASE_URL',
    f"sqlite:///{(BASE_DIR / 'database' / 'hub.db').as_posix()}" 
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
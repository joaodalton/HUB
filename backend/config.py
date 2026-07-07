import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    API_PORT = int(os.getenv('API_PORT', '8000'))
    DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    DATA_PROVIDER = os.getenv('DATA_PROVIDER', 'google_drive')
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'credentials.json')
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

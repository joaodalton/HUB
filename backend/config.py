import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    API_PORT = int(os.getenv('API_PORT', '8000'))
    DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'credentials.json')
    GOOGLE_DRIVE_SCOPES = os.getenv(
        'GOOGLE_DRIVE_SCOPES',
        'https://www.googleapis.com/auth/drive.readonly'
    ).split(',')

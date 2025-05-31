import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI') or 'http://localhost:5000/callback'
    
    # Paths
    CREDENTIALS_FILE = 'auth/credentials.json'
    TOKEN_FILE = 'token.json'  # Auto-generated after first login
    TEMP_DIR = 'temp'
    LOG_DIR = 'logs'
    
    # Download settings
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    ALLOWED_FORMATS = ['mp4', 'webm', 'mkv', 'mp3', 'm4a']
    
    # Google Drive settings
    DRIVE_FOLDER_NAME = 'YouTube Downloads'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    
class DevelopmentConfig(Config):
    DEBUG = True
    
class ProductionConfig(Config):
    DEBUG = False
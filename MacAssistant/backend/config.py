"""
MacAssistant Configuration
Contains configuration settings for the MacAssistant application.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Application configuration
class Config:
    """Base configuration."""
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-testing-only')
    DEBUG = False
    TESTING = False
    
    # LLM configuration
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'openai')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4')
    
    # Logging configuration
    LOG_DIR = os.environ.get('LOG_DIR', 'logs')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Security configuration
    RISKY_COMMAND_PATTERNS = [
        r'rm\s+-rf',
        r'sudo',
        r'killall',
        r'shutdown',
        r'reboot',
        r'halt',
        r'dd',
        r'mkfs',
        r'fdisk',
        r'passwd',
        r'chmod\s+777',
        r'uninstall'
    ]
    
    # System configuration
    MAX_EXECUTION_TIME = int(os.environ.get('MAX_EXECUTION_TIME', 300))  # seconds

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    
class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    
class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    
# Set the active configuration based on environment
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

active_config = config[os.environ.get('FLASK_ENV', 'default')]
#!/usr/bin/env python3
"""
A simple utility script to verify that environment variables are being loaded properly.
"""

import os
from dotenv import load_dotenv

def main():
    """Check environment variables."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Environment variables to check
    env_vars = [
        'FLASK_ENV',
        'SECRET_KEY',
        'GOOGLE_API_KEY',
        'GEMINI_MODEL',
        'LOG_DIR',
        'LOG_LEVEL',
        'MAX_EXECUTION_TIME'
    ]
    
    print("MacAssistant Environment Variables:")
    print("==================================")
    
    all_set = True
    
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            # Mask the API key and secret key for security
            if var in ['GOOGLE_API_KEY', 'SECRET_KEY']:
                # Show only the first and last 4 characters
                if len(value) > 8:
                    masked_value = value[:4] + '*' * (len(value) - 8) + value[-4:]
                else:
                    masked_value = '*' * len(value)
                print(f"{var}: {masked_value}")
            else:
                print(f"{var}: {value}")
        else:
            print(f"{var}: NOT SET")
            all_set = False
    
    print("\nEnvironment Status:")
    if all_set:
        print("✅ All required environment variables are set.")
    else:
        print("❌ Some environment variables are missing. Please check your .env file.")
        
    print("\nNOTE: Make sure to replace 'your-google-api-key-here' with your actual Google API key in the .env file.")

if __name__ == "__main__":
    main()
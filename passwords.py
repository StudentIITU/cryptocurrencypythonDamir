import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PostgreSQL Database Password
_postgresql_password = os.getenv('POSTGRESQL_PASSWORD', 'postgres')

def validate_password():
    """
    Validate database password configuration
    """
    if not _postgresql_password:
        raise ValueError("Database password is not configured")
    return True
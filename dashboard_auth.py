"""
OKTAGON SAV v11.0 — Dashboard Authentication
HTTP Basic Auth pour sécuriser les endpoints API
"""
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import os

security = HTTPBasic()


def verify_credentials(
    credentials: HTTPBasicCredentials = Depends(security)
) -> str:
    """Vérifie username/password depuis .env"""
    correct_username = os.getenv('DASHBOARD_USERNAME', 'admin')
    correct_password = os.getenv('DASHBOARD_PASSWORD', 'changeme')
    
    is_correct_username = secrets.compare_digest(
        credentials.username.encode('utf-8'),
        correct_username.encode('utf-8')
    )
    is_correct_password = secrets.compare_digest(
        credentials.password.encode('utf-8'),
        correct_password.encode('utf-8')
    )
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid credentials',
            headers={'WWW-Authenticate': 'Basic'},
        )
    
    return credentials.username

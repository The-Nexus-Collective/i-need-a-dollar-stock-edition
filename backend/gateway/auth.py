"""
JWT Authentication for API Gateway
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel


# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """JWT token payload"""
    sub: str  # Subject (user id or service name)
    exp: datetime
    iat: datetime
    type: str = "access"  # 'access' or 'refresh'
    permissions: list[str] = []


class User(BaseModel):
    """User model for authentication"""
    id: str
    username: str
    is_active: bool = True
    is_admin: bool = False
    permissions: list[str] = []


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    permissions: list[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        subject: The subject (user id or service name)
        permissions: List of permission strings
        expires_delta: Custom expiration time
    
    Returns:
        Encoded JWT token string
    """
    now = datetime.utcnow()
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "type": "access",
        "permissions": permissions or [],
    }
    
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> TokenData:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT token string
    
    Returns:
        TokenData with decoded payload
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return TokenData(**payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Dependency to get the current authenticated user.
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user": user.username}
    """
    token = credentials.credentials
    token_data = decode_token(token)
    
    # For now, create user from token data
    # In production, you'd look up the user in a database
    user = User(
        id=token_data.sub,
        username=token_data.sub,
        permissions=token_data.permissions
    )
    
    return user


def require_permission(permission: str):
    """
    Dependency factory to require a specific permission.
    
    Usage:
        @app.post("/admin/action")
        async def admin_action(user: User = Depends(require_permission("admin"))):
            return {"status": "ok"}
    """
    async def permission_checker(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> User:
        user = await get_current_user(credentials)
        
        if permission not in user.permissions and "admin" not in user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        
        return user
    
    return permission_checker


# Service tokens for internal communication
def create_service_token(service_name: str) -> str:
    """Create a long-lived token for internal services"""
    return create_access_token(
        subject=f"service:{service_name}",
        permissions=["service"],
        expires_delta=timedelta(days=365)
    )

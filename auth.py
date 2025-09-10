import json
import jwt
import requests
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
import os
from functools import lru_cache

# Auth0 configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")  # Changed from AUTH0_API_AUDIENCE to match Node.js
AUTH0_ALGORITHMS = ["RS256"]

security = HTTPBearer()


class Auth0JWKSError(Exception):
    """Exception raised for Auth0 JWKS errors."""
    pass


class Auth0TokenError(Exception):
    """Exception raised for Auth0 token errors."""
    pass


@lru_cache()
def get_auth0_public_key():
    """Get Auth0 public key for JWT verification."""
    if not AUTH0_DOMAIN:
        raise Auth0JWKSError("AUTH0_DOMAIN not configured")
    
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    try:
        response = requests.get(jwks_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Auth0JWKSError(f"Failed to fetch JWKS: {e}")


def get_signing_key(token: str) -> str:
    """Get the signing key for token verification."""
    try:
        # Get the token header
        unverified_header = jwt.get_unverified_header(token)
        
        # Get Auth0 public keys
        jwks = get_auth0_public_key()
        
        # Find the correct key
        rsa_key = None
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break
        
        if not rsa_key:
            raise Auth0TokenError("Unable to find appropriate key")
        
        # Construct the key using PyJWT's RSAAlgorithm
        from jwt.algorithms import RSAAlgorithm
        public_key = RSAAlgorithm.from_jwk(json.dumps(rsa_key))
        return public_key
        
    except Exception as e:
        raise Auth0TokenError(f"Failed to get signing key: {str(e)}")


def auth0_verify_token(token: str) -> Dict[str, Any]:
    """Verify Auth0 JWT token and return payload - matches Node.js auth0VerifyToken function."""
    if not AUTH0_DOMAIN or not AUTH0_AUDIENCE:
        raise Auth0TokenError("Auth0 configuration missing")
    
    try:
        # Get signing key
        public_key = get_signing_key(token)
        
        # Verify and decode the token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=AUTH0_ALGORITHMS,
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise Auth0TokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise Auth0TokenError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise Auth0TokenError(f"Token verification failed: {str(e)}")


def get_or_create_user_from_token(db: Session, token_payload: Dict[str, Any]) -> User:
    """Get or create user from Auth0 token payload - matches Node.js authenticate middleware logic."""
    
    # Extract user ID from 'sub' claim (same as Node.js)
    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID claim missing from token"
        )
    
    # Try to find existing user by Auth0 ID
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        # Extract custom claims (same as Node.js)
        user_email = token_payload.get("https://pecha-tool/email")
        picture = token_payload.get("https://pecha-tool/picture")
        
        if not user_email or not picture:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or picture claim missing from token"
            )
        
        # Create username from email (same as Node.js: email.split("@")[0])
        username = user_email.split("@")[0]
        
        # Create new user (matching Node.js logic)
        user = User(
            id=user_id,
            username=username,
            first_name="",  # Default empty string for required field
            last_name="",   # Default empty string for required field
            email=user_email,
            role='user',  # Default role
            picture=picture  # Store picture URL
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print(f"✅ Created new user: {username} ({user_email})")
    
    return user


def authenticate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI middleware that authenticates requests using Auth0 access tokens.
    This matches the Node.js authenticate function exactly.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    access_token = credentials.credentials
    
    try:
        # Verify the token with Auth0 (same as Node.js validateAuth0Token + auth0VerifyToken)
        token_payload = auth0_verify_token(access_token)
        
        # Get or create user from token payload (same as Node.js logic)
        user = get_or_create_user_from_token(db, token_payload)
        
     
        
        return user
        
    except Auth0TokenError as e:
        print(f"❌ Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    except Exception as e:
        print(f"❌ Unexpected authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


# Alias for backward compatibility with existing code
get_current_user = authenticate
get_current_active_user = authenticate


def require_role(required_roles: list[str]):
    """Decorator to require specific user roles."""
    def role_checker(current_user: User = Depends(authenticate)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[role.value for role in required_roles]}, your role: {current_user.role.value}"
            )
        return current_user
    return role_checker




def get_auth0_debug_info(access_token: str) -> Dict[str, Any]:
    """Get debug information about Auth0 token (for development only)."""
    try:
        token_payload = auth0_verify_token(access_token)
        
        return {
            "token_valid": True,
            "token_payload": token_payload,
            "auth0_domain": AUTH0_DOMAIN,
            "auth0_audience": AUTH0_AUDIENCE,
            "custom_claims": {
                "email": token_payload.get("https://pecha-tool/email"),
                "picture": token_payload.get("https://pecha-tool/picture"),
                "user_id": token_payload.get("sub")
            }
        }
    except Exception as e:
        return {
            "token_valid": False,
            "error": str(e),
            "auth0_domain": AUTH0_DOMAIN,
            "auth0_audience": AUTH0_AUDIENCE
        } 
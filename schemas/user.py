import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str = Field(..., description="Username derived from email")
    first_name: str = Field(..., description="First name of the user")
    last_name: str = Field(..., description="Last name of the user")
    email: str = Field(..., description="Email of the user")
    picture: Optional[str] = Field(None, description="Profile picture url (optional)")
    role: str = Field(default='user', description="Role of the user")

class UserCreate(UserBase):
    pass  # ID comes from authenticated token, not request body

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, description="Username derived from email")
    first_name: Optional[str] = Field(None, description="First name of the user")
    last_name: Optional[str] = Field(None, description="Last name of the user")
    email: Optional[str] = Field(None, description="Email of the user")
    picture: Optional[str] = Field(None, description="Profile picture url (optional)")
    role: Optional[str] = Field(None, description="Role of the user (optional)")

class UserRead(UserBase):
    id: str = Field(..., description="Auth0 user ID")
    created_at: datetime = Field(..., description="Creation timestamp of the user")
    updated_at: datetime = Field(..., description="Last update timestamp of the user")

    class Config:
        from_attributes = True

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str  # Auth0 user ID
    created_at: datetime
    updated_at: Optional[datetime] = None
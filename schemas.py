"""
Pydantic schemas for request validation and response serialization.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# ==================== USER SCHEMAS ====================

class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)

class UserResponse(BaseModel):
    """Schema for returning user data (hides password hash)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime




# ==================== CATEGORY SCHEMAS ====================

class CategoryCreate(BaseModel):
    """Schema for creating a category."""
    name: str = Field(..., min_length=1, max_length=100)

class CategoryUpdate(BaseModel):
    """Useful if the user wants to rename a personal category."""
    name: str = Field(..., min_length=1, max_length=100)

class CategoryResponse(BaseModel):
    """Schema for returning category data."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    owner_id: Optional[int]

# ==================== FOOD ITEM SCHEMAS ====================

class FoodItemBase(BaseModel):
    """Base fields shared across food schemas."""
    date: datetime
    amount: float = Field(..., gt=0)
    category_id: int
    location: Optional[str] = Field(None, max_length=255)
    calories: Optional[float] = Field(None, ge=0)
    tags: Optional[str] = Field(None, max_length=255)
    note: Optional[str] = Field(None, max_length=255)

class FoodItemCreate(FoodItemBase):
    """All fields required for creation."""

class FoodItemUpdate(BaseModel):
    """All fields are optional for partial updates."""
    date: Optional[datetime] = None
    amount: Optional[float] = Field(None, gt=0)
    category_id: Optional[int] = None
    location: Optional[str] = None
    calories: Optional[float] = None
    tags: Optional[str] = None
    note: Optional[str] = None

class FoodItemResponse(FoodItemBase):
    """schema for returning food item data."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int

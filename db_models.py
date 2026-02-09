"""
SQLAlchemy ORM Models for Food Tracker Application

"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    """Base class for all ORM models"""

class User(Base):
    """User model representing application users"""
    __tablename__ = "users"

    id=Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda:datetime.now(timezone.utc), nullable=False)

    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    food_items=relationship("FoodItem", back_populates="user", cascade="all, delete-orphan")

class Category(Base):

    """
    Category model for organizing food items
    """
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=lambda:datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="categories")
    food_items = relationship("FoodItem", back_populates="category")

class FoodItem(Base):
    """
    FoodItem model representing individual food entries
    """
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, autoincrement=True)

    date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)

    location = Column(String(255), nullable=True)
    calories = Column(Float, nullable=True)
    tags=Column(String(255), nullable=True)
    note=Column(String(255), nullable=True)

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    category_id = Column(
        Integer,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=False,
    )
    created_at = Column(DateTime, default=lambda:datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="food_items")
    category = relationship("Category", back_populates="food_items")

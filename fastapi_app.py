"""
FastAPI Application for Food Tracker.
Demonstrates CRUD operations with bearer token auth
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm,OAuth2PasswordBearer

import schemas
import db_models
from db import DatabaseService

oauth2=OAuth2PasswordBearer(tokenUrl="login")
# --- Database Setup ---
_db_instance = DatabaseService()

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Handles startup and shutdown events."""
    await _db_instance.create_tables()
    try:
        yield
    finally:
        #shutdown
        await _db_instance.close()

app = FastAPI(
    title="Food Tracker API",
    description="API for logging food purchases, categories, and analysis.",
    version="1.0.0",
    lifespan=lifespan
)



# --- Dependency Injection ---

async def get_db() -> DatabaseService:
    """Dependency to provide database service instance"""
    return _db_instance

async def get_current_user(
    token: str = Depends(oauth2),
    db: DatabaseService = Depends(get_db)
)-> db_models.User:
    """get current user based on token in Authorization header."""

    user = await db.get_user_by_username(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    return user

# ==================== AUTHENTICATION ====================


@app.post("/login")
async def login(
    data: OAuth2PasswordRequestForm = Depends(),
    db: DatabaseService = Depends(get_db)
):
    """login"""
    user = await db.authenticate_user(data.username, data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {
        "access_token": user.username,
        "token_type": "bearer"
    }



# ==================== USER ENDPOINTS ====================

@app.post("/users", response_model=schemas.UserResponse, status_code=201)
async def create_user(user_data: schemas.UserCreate, db: DatabaseService = Depends(get_db)):
    """Register a new user (Create)."""
    if await db.get_user_by_username(user_data.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    return await db.create_user(**user_data.model_dump())

@app.get("/users/me", response_model=schemas.UserResponse)
async def get_current_user_profile(current_user: db_models.User = Depends(get_current_user)):
    """Get own profile (Read)."""
    return current_user

@app.get("/users", response_model=List[schemas.UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """List all users (Admin only requirement)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return await db.get_all_users(skip=skip, limit=limit)

@app.put("/users/{user_id}", response_model=schemas.UserResponse)
async def update_user(
    user_id: int,
    user_data: schemas.UserUpdate,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """Update user info (Own account or Admin)."""
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to update this user")

    updated_user = await db.update_user(user_id, **user_data.model_dump(exclude_unset=True))
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """Delete user (Own account or Admin)."""
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this user")

    success = await db.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

# ==================== CATEGORY ENDPOINTS ====================

@app.post("/categories", response_model=schemas.CategoryResponse, status_code=201)
async def create_category(
    category_data: schemas.CategoryCreate,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """
    Create a new personal category for the authenticated user.
    Requirement: Personal categories per user.
    """
    return await db.create_category(
        name=category_data.name,
        owner_id=current_user.id
    )

@app.get("/categories", response_model=List[schemas.CategoryResponse])
async def list_categories(
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """
    List all accessible categories (Global + Personal).
    Requirement: Category selection for food entries.
    """
    return await db.get_categories(user_id=current_user.id)

@app.put("/categories/{category_id}", response_model=schemas.CategoryResponse)
async def update_category(
    category_id: int,
    category_data: schemas.CategoryUpdate,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """
    Update a personal category name.
    Only the owner can update their categories.
    """
    updated = await db.update_category(
        category_id=category_id,
        user_id=current_user.id,
        name=category_data.name
    )
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Category not found or you don't have permission to edit it"
        )
    return updated

@app.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """
    Delete a personal category.
    Only the owner can delete their categories.
    """
    success = await db.delete_category(category_id=category_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Category not found or you don't have permission to delete it"
        )
    return None


# ==================== FOOD ITEM ENDPOINTS ====================

@app.post(
        "/food", 
        response_model=schemas.FoodItemResponse,
        status_code=status.HTTP_201_CREATED)
async def log_food(
    item: schemas.FoodItemCreate,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """Creates a new food log entry."""
    return await db.create_food_item(owner_id=current_user.id, **item.model_dump())

@app.get("/food", response_model=List[schemas.FoodItemResponse])
async def list_food(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    category_id: Optional[int] = None,
    tags: Optional[str] = None,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """Lists food entries with optional filters (Requirement: Filtering)."""
    return await db.get_food_items(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
        tags=tags
    )

@app.put("/food/{item_id}", response_model=schemas.FoodItemResponse)
async def update_food_item(
    item_id: int,
    item_data: schemas.FoodItemUpdate,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """Update an existing food record."""
    update_dict = item_data.model_dump(exclude_unset=True)

    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    updated = await db.update_food_item(item_id, current_user.id, **update_dict)
    if not updated:
        raise HTTPException(status_code=404, detail="Record not found or unauthorized")
    return updated

@app.delete("/food/{item_id}", status_code=204)
async def delete_food_item(
    item_id: int,
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """Delete a food record."""
    success = await db.delete_food_item(item_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Record not found")
    return None


# ==================== DASHBOARD ENDPOINT ====================

@app.get("/dashboard")
async def get_dashboard(
    current_user: db_models.User = Depends(get_current_user),
    db: DatabaseService = Depends(get_db)
):
    """Returns aggregated data for the dashboard (Requirement: Aggregates)."""
    return await db.get_dashboard_stats(user_id=current_user.id)


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

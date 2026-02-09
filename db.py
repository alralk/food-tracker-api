"""
Async Database Module with CRUD operations
"""
from datetime import datetime
from typing import Sequence, Optional
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import delete, and_, or_, func, select
from db_models import Base, User, Category, FoodItem

# Setup the password hashing algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class DatabaseService:
    """
    Async Database Manager for CRUD operations
    """
    def __init__(self, database_url: str = "sqlite+aiosqlite:///./food_tracker.db"):
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_tables(self):
        """Create all tables defined in models"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # preload if needed
        await self._preload_data()

    async def drop_tables(self):
        """testing"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def close(self):
        """close"""
        await self.engine.dispose()

    async def _preload_data(self):
        """Seed data"""
        existing_admin = await self.get_user_by_username("admin")
        if existing_admin:
            return

        async with self.async_session() as session:
            # 1. Create Admin
            admin = User(
                username="admin",
                email="admin@foodtracker.com",
                password_hash=pwd_context.hash("admin123"),
                is_admin=True,
            )
            session.add(admin)

            # 2. Create Demo User
            demo_user = User(
                username="demo",
                email="demo@example.com",
                password_hash=pwd_context.hash("demo123"),
                is_admin=False,
            )
            session.add(demo_user)
            await session.flush()  # Flush to get IDs before creating categories

            # 3. Global Categories
            categories = [
                Category(name="homemade", owner_id=None),
                Category(name="restaurant", owner_id=None),
                Category(name="delivery", owner_id=None),
            ]
            session.add_all(categories)
            await session.commit()
            print("✓ Database preloaded with demo data.")

    # ==================== USER CRUD OPERATIONS ====================

    async def create_user(
        self, username: str, email: str, password: str, is_admin: bool = False
    ) -> User:
        """user creation with a secure password hashing"""
        async with self.async_session() as session:

            password_hash = pwd_context.hash(password)

            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                is_admin=is_admin,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def authenticate_user(self, username: str, password: str) -> User | None:
        """verify user's credentials"""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).filter(User.username == username)
            )
            user = result.scalar_one_or_none()
            if user and pwd_context.verify(password, user.password_hash):
                return user
            return None

    async def get_user(self, user_id: int) -> User | None:
        """get user by id"""
        async with self.async_session() as session:
            result = await session.execute(select(User).filter(User.id == user_id))
            return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        """get user by username"""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).filter(User.username == username)
            )
            return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """get user by email"""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).filter(User.email == email)
            )
            return result.scalar_one_or_none()

    async def get_all_users(self, skip: int = 0, limit: int = 100) -> Sequence[User]:
        """get all users with pagination"""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
            )
            return result.scalars().all()

    async def update_user(self, user_id: int, **kwargs) -> User | None:
        """update user fields"""
        async with self.async_session() as session:
            # hash password if provided
            if "password" in kwargs:
                kwargs["password_hash"] = pwd_context.hash(kwargs.pop("password"))

            result = await session.execute(select(User).filter(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                for key, value in kwargs.items():
                    setattr(user, key, value)
                await session.commit()
                await session.refresh(user)
            return user

    async def delete_user(self, user_id: int) -> bool:
        """delete by id"""
        async with self.async_session() as session:
            result = await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
            return result.rowcount > 0

    # ==================== CATEGORY CRUD ====================
    async def create_category(self, name: str, owner_id: Optional[int] = None) -> Category:
        """category creation"""
        async with self.async_session() as session:
            category = Category(name=name, owner_id=owner_id)
            session.add(category)
            await session.commit()
            await session.refresh(category)
            return category

    async def get_categories(self, user_id: int) -> Sequence[Category]:
        """returns both global and user-specific categories"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Category).filter(
                    or_(
                        Category.owner_id == user_id,
                        Category.owner_id.is_(None),
                    )
                )
            )
            return result.scalars().all()

    async def update_category(self, category_id: int,
                              user_id: int,
                              name: str) -> Optional[Category]:
        """Update a personal category name."""
        async with self.async_session() as session:
            result = await session.execute(
                select(Category).filter(Category.id == category_id, Category.owner_id == user_id)
            )
            category = result.scalar_one_or_none()
            if category:
                category.name = name
                await session.commit()
                await session.refresh(category)
            return category

    async def delete_category(self, category_id: int, user_id: int) -> bool:
        """Delete a personal category."""
        async with self.async_session() as session:
            result = await session.execute(
                delete(Category).where(Category.id == category_id, Category.owner_id == user_id)
            )
            await session.commit()
            return result.rowcount > 0

    # ==================== FOOD ITEM CRUD ====================
    async def create_food_item(self, owner_id: int, **kwargs) -> FoodItem:
        """food item creation with flexible fields"""
        async with self.async_session() as session:
            item = FoodItem(owner_id=owner_id, **kwargs)
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    async def get_food_items(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category_id: Optional[int] = None,
        tags: Optional[str] = None
    ) -> Sequence[FoodItem]:
        """filtering food items by date range and category"""
        async with self.async_session() as session:
            query = select(FoodItem).filter(FoodItem.owner_id == user_id)

            if start_date:
                query = query.filter(FoodItem.date >= start_date)
            if end_date:
                query = query.filter(FoodItem.date <= end_date)
            if category_id:
                query = query.filter(FoodItem.category_id == category_id)
            if tags:
                query = query.filter(FoodItem.tags.ilike(f"%{tags}%"))

            result = await session.execute(query.order_by(FoodItem.date.desc()))
            return result.scalars().all()

    async def update_food_item(self, item_id: int, user_id: int, **kwargs) -> Optional[FoodItem]:
        """Update a food record if owned by the user."""
        async with self.async_session() as session:
            result = await session.execute(
                select(FoodItem).filter(FoodItem.id == item_id, FoodItem.owner_id == user_id)
            )
            item = result.scalar_one_or_none()
            if item:
                for key, value in kwargs.items():
                    setattr(item, key, value)
                await session.commit()
                await session.refresh(item)
            return item

    async def delete_food_item(self, item_id: int, user_id: int) -> bool:
        """Delete a food record."""
        async with self.async_session() as session:
            result = await session.execute(
                delete(FoodItem).where(FoodItem.id == item_id, FoodItem.owner_id == user_id)
            )
            await session.commit()
            return result.rowcount > 0


    async def get_dashboard_stats(self, user_id: int):
        """dashboard stats for monthly total,
                               top categories,
                               recent entries
        """
        async with self.async_session() as session:
            now = datetime.now()
            first_day = datetime(now.year, now.month, 1)

            # 1. Monthly Total
            total_q = select(func.sum(FoodItem.amount)).filter(
                and_(FoodItem.owner_id == user_id, FoodItem.date >= first_day)
            )
            total_res = await session.execute(total_q)
            total_amount = total_res.scalar() or 0.0

            # 2. Top Categories (Aggregated)
            # Groups by category name and sums amounts
            top_cats_q = (
                select(Category.name, func.sum(FoodItem.amount))
                .join(FoodItem, Category.id == FoodItem.category_id)
                .filter(FoodItem.owner_id == user_id)
                .group_by(Category.name)
                .order_by(func.sum(FoodItem.amount).desc())
                .limit(3)
            )
            cats_res = await session.execute(top_cats_q)
            top_categories = [{"category": row[0], "total": row[1]} for row in cats_res.all()]

            # 3. Last 5 Entries
            recent_items_q = (
                select(FoodItem)
                .filter(FoodItem.owner_id == user_id)
                .order_by(FoodItem.date.desc())
                .limit(5)
            )
            recent_res = await session.execute(recent_items_q)
            recent_items = recent_res.scalars().all()

            return {
                "monthly_total": float(total_amount),
                "top_categories": top_categories,
                "recent_entries": recent_items
            }

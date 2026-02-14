# pylint: disable=redefined-outer-name
"""
FastAPI App Tests
Comprehensive tests for Food Tracker REST API endpoints.
"""
from datetime import datetime

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi_app import app, get_db
from db import DatabaseService
from db_models import Base
# =========
# FIXTURES
# =========


@pytest.fixture
async def test_db():
    """Create an in-memory database for testing"""
    #Base.metadata.clear()
    db = DatabaseService("sqlite+aiosqlite:///:memory:")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db
    await db.close()


@pytest.fixture
async def client(test_db):
    """Create FastAPI test client with DB override"""
    async def override_get_db():
        return test_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def get_token_header(client, username, password):
    """Helper to get token header"""
    response = await client.post(
        "/login",
        data={"username": username, "password": password},
    )
    result=response.json()
    token=result["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ==================== AUTH & USER TESTS ====================


@pytest.mark.asyncio
async def test_register_and_login(client):
    """Test full flow: register -> login -> get token"""
    # 1. Register
    reg_resp = await client.post(
        "/users",
        json={"username": "tester", "email": "t@e.com", "password": "password123"},
    )
    assert reg_resp.status_code == 201

    # 2. Login
    login_resp = await client.post(
        "/login",
        data={"username": "tester", "password": "password123"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


# ==================== CATEGORY TESTS ====================


@pytest.mark.asyncio
async def test_create_category(client, test_db):
    """Test personal category creation"""
    await test_db.create_user("cat_user", "c@e.com", "pass123")
    headers = await get_token_header(client, "cat_user", "pass123")

    response = await client.post(
        "/categories",
        headers=headers,
        json={"name": "Keto Diet"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Keto Diet"


# ==================== FOOD ITEM TESTS ====================


@pytest.mark.asyncio
async def test_create_food_item_and_filter(client, test_db):
    """Test logging food and then searching by tags/category"""
    # Setup
    await test_db.create_user("foodie", "f@e.com", "pass123")
    headers = await get_token_header(client, "foodie", "pass123")

    # Create
    item_data = {
        "date": datetime.now().isoformat(),
        "amount": 20.5,
        "category_id": 1,  # 'Homemade' from seed data
        "tags": "dinner, healthy",
        "location": "Home",
    }
    post_resp = await client.post("/food", headers=headers, json=item_data)
    assert post_resp.status_code == 201

    # Filter by Tag
    get_resp = await client.get("/food?tags=dinner", headers=headers)
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 1
    assert "dinner" in get_resp.json()[0]["tags"]


@pytest.mark.asyncio
async def test_delete_food_item(client, test_db):
    """Test item deletion (CRUD)"""
    await test_db.create_user("deleter", "d@e.com", "pass123")
    headers = await get_token_header(client, "deleter", "pass123")

    # Create item first
    item = await test_db.create_food_item(owner_id=1, amount=10, category_id=1, date=datetime.now())

    # Delete
    del_resp = await client.delete(f"/food/{item.id}", headers=headers)
    assert del_resp.status_code in [200, 204]


# ==================== DASHBOARD TESTS ====================


@pytest.mark.asyncio
async def test_dashboard_stats(client, test_db):
    """Test if dashboard returns the monthly total"""
    await test_db.create_user("stat_user", "s@e.com", "pass123")
    headers = await get_token_header(client, "stat_user", "pass123")

    response = await client.get("/dashboard", headers=headers)
    assert response.status_code == 200
    assert "monthly_total" in response.json()


# ==================== EDGE CASE & ERROR TESTS ====================

@pytest.mark.asyncio
async def test_auth_failures(client):
    """Targets 'get_current_user' 401 branch"""
    # 1. No token
    resp = await client.get("/users/me")
    assert resp.status_code == 401

    # 2. Invalid token (user doesn't exist in DB)
    resp = await client.get("/users/me", headers={"Authorization": "Bearer fakeuser"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_restrictions(client, test_db):
    """Targets the 403 'Admin privileges required' branch"""
    await test_db.create_user("peasant", "p@e.com", "pass", is_admin=False)
    headers = await get_token_header(client, "peasant", "pass")

    response = await client.get("/users", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_user_permissions(client, test_db):
    """Targets the 403 'Not authorized' branch by using real IDs"""
    victim = await test_db.create_user("victim", "v@e.com", "pass")
    _ = await test_db.create_user("attacker", "a@e.com", "pass")
    #intentionally ignoring return value

    headers = await get_token_header(client, "attacker", "pass")

    # Attacker tries to update victim using victim's real ID
    response = await client.put(
        f"/users/{victim.id}",
        headers=headers,
        json={"email": "hacked@e.com"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_food_update_empty_payload(client, test_db):
    """Targets the 400 'No fields provided' branch"""
    user = await test_db.create_user("chef", "chef@e.com", "pass")
    headers = await get_token_header(client, "chef", "pass")

    # Create an item so we have a valid ID to target
    item = await test_db.create_food_item(owner_id=user.id,
                                           amount=10, category_id=1,
                                             date=datetime.now())

    # Send empty JSON {} to trigger the 'if not update_dict' check
    resp = await client.put(f"/food/{item.id}", headers=headers, json={})
    assert resp.status_code == 400
@pytest.mark.asyncio
async def test_user_management_errors(client, test_db):
    """covers error codes"""
    # Setup users
    _ = await test_db.create_user("big_boss", "b@e.com", "pass", is_admin=True)
    victim = await test_db.create_user("victim", "v@e.com", "pass")
    _ = await test_db.create_user("attacker", "a@e.com", "pass")

    attacker_headers = await get_token_header(client, "attacker", "pass")
    admin_headers = await get_token_header(client, "big_boss", "pass")

    # 403: Attacker tries to delete Victim (Line 138-144)
    resp = await client.delete(f"/users/{victim.id}", headers=attacker_headers)
    assert resp.status_code == 403

    # 404: Admin tries to delete non-existent user (Line 144)
    resp = await client.delete("/users/9999", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_category_and_food_edge_cases(client, test_db):
    """covers error codes"""
    _ = await test_db.create_user("chef", "c@e.com", "pass")
    headers = await get_token_header(client, "chef", "pass")

    # 404: Update category you don't own (Lines 185-195)
    resp = await client.put("/categories/9999", headers=headers, json={"name": "Ghost"})
    assert resp.status_code == 404

    # 404: Delete category you don't own (Lines 207-213)
    resp = await client.delete("/categories/9999", headers=headers)
    assert resp.status_code == 404

    # 404: Delete food item that doesn't exist (Lines 275)
    resp = await client.delete("/food/9999", headers=headers)
    assert resp.status_code == 404

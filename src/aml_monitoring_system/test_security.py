"""
Security / Auth Tests
"""
import pytest
from datetime import timedelta
from jose import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = hash_password("mysecret")
        assert h != "mysecret"
        assert len(h) > 20

    def test_verify_correct_password(self):
        h = hash_password("correcthorsebatterystaple")
        assert verify_password("correcthorsebatterystaple", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("correctpassword")
        assert verify_password("wrongpassword", h) is False

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2   # bcrypt uses random salt


class TestJWTTokens:
    def test_access_token_created(self):
        token = create_access_token({"sub": "user@test.com", "role": "analyst"})
        assert isinstance(token, str)
        assert len(token) > 10

    def test_access_token_decodable(self):
        token = create_access_token({"sub": "user@test.com", "role": "analyst"})
        payload = decode_token(token)
        assert payload["sub"] == "user@test.com"
        assert payload["role"] == "analyst"
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        token = create_refresh_token({"sub": "user@test.com"})
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_expired_token_raises(self):
        from fastapi import HTTPException
        token = create_access_token(
            {"sub": "user@test.com"},
            expires_delta=timedelta(seconds=-1),   # already expired
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401

    def test_tampered_token_raises(self):
        from fastapi import HTTPException
        token = create_access_token({"sub": "user@test.com"})
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(HTTPException):
            decode_token(tampered)

    def test_token_contains_expiry(self):
        token = create_access_token({"sub": "test"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload


class TestRoleGuards:
    @pytest.mark.asyncio
    async def test_analyst_can_access_analyst_route(self, app_client, analyst_headers):
        resp = await app_client.get("/api/v1/alerts/", headers=analyst_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_access_analyst_route(self, app_client, admin_headers):
        resp = await app_client.get("/api/v1/alerts/", headers=admin_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_no_token_returns_401(self, app_client):
        resp = await app_client.get("/api/v1/alerts/")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, app_client):
        resp = await app_client.get(
            "/api/v1/alerts/",
            headers={"Authorization": "Bearer this.is.not.valid"},
        )
        assert resp.status_code == 401

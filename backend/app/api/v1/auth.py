"""Auth API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str


@router.post("/login")
async def login(request: LoginRequest):
    """User login."""
    # TODO: Implement real authentication
    if request.username and request.password:
        return {
            "code": 0,
            "data": "mock_token_" + request.username,
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/me")
async def get_current_user():
    """Get current user info."""
    # TODO: Implement real user retrieval
    return {
        "code": 0,
        "data": {
            "id": 1,
            "username": "admin",
            "role": "admin",
            "created_at": "2026-04-15T00:00:00Z",
        },
    }

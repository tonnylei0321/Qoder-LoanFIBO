"""Auth API routes -- login, current user, permission dependencies."""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Callable

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.services.auth import verify_password, create_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])


# -- Schemas ------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None
    status: str
    roles: list[dict]
    permissions: list[str]
    created_at: str


# -- Dependencies -------------------------------------------------------------

async def get_current_user(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate user from Authorization header."""
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    if not token:
        raise HTTPException(401, "Missing token")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token payload")
    user = (await db.execute(select(User).where(User.id == int(user_id)))).scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    if user.status == "disabled":
        raise HTTPException(403, "User is disabled")
    return user


def require_permission(code: str) -> Callable:
    """Dependency factory: returns a dependency that checks the user has *code* permission."""
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_admin:
            return current_user
        if not current_user.has_permission(code):
            raise HTTPException(403, f"Permission denied: {code}")
        return current_user
    return _check


# -- Routes -------------------------------------------------------------------

@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """User login -- returns JWT token."""
    user = (await db.execute(select(User).where(User.username == request.username))).scalar_one_or_none()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    if user.status == "disabled":
        raise HTTPException(403, "用户已被禁用")
    token = create_token({"sub": str(user.id), "username": user.username})
    return {"code": 0, "data": {"token": token}}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    # Aggregate menu_codes from all roles
    menu_codes_set: set[str] = set()
    for role in current_user.roles:
        if role.menu_codes:
            menu_codes_set.update(role.menu_codes)
    # admin role gets all menus (empty set means no restriction)
    is_admin = any(r.code == "admin" for r in current_user.roles)
    return {
        "code": 0,
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "status": current_user.status,
            "roles": [{"id": r.id, "name": r.name, "code": r.code} for r in current_user.roles],
            "permissions": sorted(current_user.permissions),
            "menu_codes": None if is_admin else sorted(menu_codes_set),  # None = no restriction (admin)
            "created_at": str(current_user.created_at),
        },
    }

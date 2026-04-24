"""RBAC API routes — User / Role / Permission CRUD."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.role import Role
from backend.app.models.permission import Permission

router = APIRouter(prefix="/rbac", tags=["rbac"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Schemas ──────────────────────────────────────────────────────────────

# --- User ---
class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: str | None = None
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str | None = None


class UserRolesUpdate(BaseModel):
    role_ids: list[int]


class UserStatusUpdate(BaseModel):
    status: str  # active / disabled


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    status: str
    roles: list[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Role ---
class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=64)
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class RolePermissionsUpdate(BaseModel):
    permission_ids: list[int]


class RoleMenuCodesUpdate(BaseModel):
    menu_codes: list[str]


class RoleOut(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    status: str
    permissions: list[dict]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Permission ---
class PermissionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=128)
    module: str = Field(min_length=1, max_length=64)


class PermissionUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    module: str | None = None


class PermissionOut(BaseModel):
    id: int
    name: str
    code: str
    module: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ──────────────────────────────────────────────────────────────

def _user_to_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "status": user.status,
        "roles": [{"id": r.id, "name": r.name, "code": r.code} for r in user.roles],
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _role_to_out(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "code": role.code,
        "description": role.description,
        "status": role.status,
        "permissions": [{"id": p.id, "name": p.name, "code": p.code, "module": p.module} for p in role.permissions],
        "menu_codes": role.menu_codes or [],
        "created_at": role.created_at,
    }


def _perm_to_out(perm: Permission) -> dict:
    return {
        "id": perm.id,
        "name": perm.name,
        "code": perm.code,
        "module": perm.module,
        "created_at": perm.created_at,
    }


# ═══════════════════════════════════════════════════════════════════════
#  USER CRUD
# ═══════════════════════════════════════════════════════════════════════

@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User)
    if search:
        stmt = stmt.where(User.username.ilike(f"%{search}%"))
    total_stmt = select(func.count()).select_from(User)
    if search:
        total_stmt = total_stmt.where(User.username.ilike(f"%{search}%"))
    total = (await db.execute(total_stmt)).scalar() or 0
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    users = result.scalars().all()
    return {"code": 0, "data": {"items": [_user_to_out(u) for u in users], "total": total, "page": page, "page_size": page_size}}


@router.post("/users")
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "用户名已存在")
    user = User(
        username=body.username,
        password_hash=pwd_context.hash(body.password),
        email=body.email,
    )
    if body.role_ids:
        roles = (await db.execute(select(Role).where(Role.id.in_(body.role_ids)))).scalars().all()
        user.roles = list(roles)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return {"code": 0, "data": _user_to_out(user)}


@router.put("/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    if body.username is not None:
        user.username = body.username
    if body.email is not None:
        user.email = body.email
    if body.password:
        user.password_hash = pwd_context.hash(body.password)
    await db.flush()
    return {"code": 0, "data": _user_to_out(user)}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    await db.delete(user)
    return {"code": 0, "data": None}


@router.put("/users/{user_id}/roles")
async def assign_user_roles(user_id: int, body: UserRolesUpdate, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    roles = (await db.execute(select(Role).where(Role.id.in_(body.role_ids)))).scalars().all()
    user.roles = list(roles)
    await db.flush()
    return {"code": 0, "data": _user_to_out(user)}


@router.put("/users/{user_id}/status")
async def toggle_user_status(user_id: int, body: UserStatusUpdate, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.status = body.status
    await db.flush()
    return {"code": 0, "data": _user_to_out(user)}


# ═══════════════════════════════════════════════════════════════════════
#  ROLE CRUD
# ═══════════════════════════════════════════════════════════════════════

@router.get("/roles")
async def list_roles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Role))
    roles = result.scalars().all()
    return {"code": 0, "data": [_role_to_out(r) for r in roles]}


@router.post("/roles")
async def create_role(body: RoleCreate, db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(Role).where(Role.code == body.code))).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "角色编码已存在")
    role = Role(name=body.name, code=body.code, description=body.description)
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return {"code": 0, "data": _role_to_out(role)}


@router.put("/roles/{role_id}")
async def update_role(role_id: int, body: RoleUpdate, db: AsyncSession = Depends(get_db)):
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(404, "角色不存在")
    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    if body.status is not None:
        role.status = body.status
    await db.flush()
    return {"code": 0, "data": _role_to_out(role)}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db: AsyncSession = Depends(get_db)):
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(404, "角色不存在")
    await db.delete(role)
    return {"code": 0, "data": None}


@router.put("/roles/{role_id}/permissions")
async def assign_role_permissions(role_id: int, body: RolePermissionsUpdate, db: AsyncSession = Depends(get_db)):
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(404, "角色不存在")
    perms = (await db.execute(select(Permission).where(Permission.id.in_(body.permission_ids)))).scalars().all()
    role.permissions = list(perms)
    await db.flush()
    return {"code": 0, "data": _role_to_out(role)}


@router.put("/roles/{role_id}/menu-permissions")
async def assign_role_menu_codes(role_id: int, body: RoleMenuCodesUpdate, db: AsyncSession = Depends(get_db)):
    """Save menu/route permissions for a role."""
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(404, "角色不存在")
    role.menu_codes = body.menu_codes
    await db.flush()
    return {"code": 0, "data": _role_to_out(role)}


# ═══════════════════════════════════════════════════════════════════════
#  PERMISSION CRUD
# ═══════════════════════════════════════════════════════════════════════

@router.get("/permissions")
async def list_permissions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Permission).order_by(Permission.module, Permission.id))
    perms = result.scalars().all()
    return {"code": 0, "data": [_perm_to_out(p) for p in perms]}


@router.post("/permissions")
async def create_permission(body: PermissionCreate, db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(Permission).where(Permission.code == body.code))).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "权限编码已存在")
    perm = Permission(name=body.name, code=body.code, module=body.module)
    db.add(perm)
    await db.flush()
    return {"code": 0, "data": _perm_to_out(perm)}


@router.put("/permissions/{perm_id}")
async def update_permission(perm_id: int, body: PermissionUpdate, db: AsyncSession = Depends(get_db)):
    perm = (await db.execute(select(Permission).where(Permission.id == perm_id))).scalar_one_or_none()
    if not perm:
        raise HTTPException(404, "权限不存在")
    if body.name is not None:
        perm.name = body.name
    if body.code is not None:
        perm.code = body.code
    if body.module is not None:
        perm.module = body.module
    await db.flush()
    return {"code": 0, "data": _perm_to_out(perm)}


@router.delete("/permissions/{perm_id}")
async def delete_permission(perm_id: int, db: AsyncSession = Depends(get_db)):
    perm = (await db.execute(select(Permission).where(Permission.id == perm_id))).scalar_one_or_none()
    if not perm:
        raise HTTPException(404, "权限不存在")
    await db.delete(perm)
    return {"code": 0, "data": None}

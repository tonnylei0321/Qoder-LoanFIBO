"""Seed RBAC data: Permissions, Roles, and initial Admin user."""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.role import Role
from backend.app.models.permission import Permission

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database URL from environment or default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/loanfibo")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Seed Data Definition ───────────────────────────────────────────────

PERMISSIONS = [
    # User Management
    {"name": "查看用户列表", "code": "user:list", "module": "用户管理"},
    {"name": "创建用户", "code": "user:create", "module": "用户管理"},
    {"name": "编辑用户", "code": "user:update", "module": "用户管理"},
    {"name": "删除用户", "code": "user:delete", "module": "用户管理"},
    {"name": "分配用户角色", "code": "user:assign_role", "module": "用户管理"},

    # Role Management
    {"name": "查看角色列表", "code": "role:list", "module": "角色管理"},
    {"name": "创建角色", "code": "role:create", "module": "角色管理"},
    {"name": "编辑角色", "code": "role:update", "module": "角色管理"},
    {"name": "删除角色", "code": "role:delete", "module": "角色管理"},
    {"name": "分配角色权限", "code": "role:assign_perm", "module": "角色管理"},

    # Permission Management
    {"name": "查看权限列表", "code": "permission:list", "module": "权限管理"},
    {"name": "创建权限", "code": "permission:create", "module": "权限管理"},
    {"name": "编辑权限", "code": "permission:update", "module": "权限管理"},
    {"name": "删除权限", "code": "permission:delete", "module": "权限管理"},

    # DDL File Management
    {"name": "查看DDL文件", "code": "ddl:list", "module": "DDL管理"},
    {"name": "上传DDL文件", "code": "ddl:upload", "module": "DDL管理"},
    {"name": "删除DDL文件", "code": "ddl:delete", "module": "DDL管理"},

    # TTL File Management
    {"name": "查看TTL文件", "code": "ttl:list", "module": "TTL管理"},
    {"name": "上传TTL文件", "code": "ttl:upload", "module": "TTL管理"},
    {"name": "删除TTL文件", "code": "ttl:delete", "module": "TTL管理"},

    # Job Management
    {"name": "查看任务", "code": "job:list", "module": "任务管理"},
    {"name": "创建任务", "code": "job:create", "module": "任务管理"},
    {"name": "编辑任务", "code": "job:update", "module": "任务管理"},
    {"name": "删除任务", "code": "job:delete", "module": "任务管理"},
    {"name": "启动/停止任务", "code": "job:control", "module": "任务管理"},

    # Mapping Review
    {"name": "查看评审", "code": "review:list", "module": "映射评审"},
    {"name": "审批映射", "code": "review:approve", "module": "映射评审"},
    {"name": "驳回映射", "code": "review:reject", "module": "映射评审"},

    # Graph Explorer
    {"name": "浏览图谱", "code": "graph:explore", "module": "图谱浏览"},
    {"name": "查询实体", "code": "graph:query", "module": "图谱浏览"},

    # Sync Management
    {"name": "查看同步任务", "code": "sync:list", "module": "同步管理"},
    {"name": "创建同步任务", "code": "sync:create", "module": "同步管理"},
    {"name": "管理图谱实例", "code": "sync:manage_instance", "module": "同步管理"},

    # System Settings
    {"name": "查看系统设置", "code": "setting:view", "module": "系统设置"},
    {"name": "修改系统设置", "code": "setting:update", "module": "系统设置"},
]

ROLES = [
    {
        "name": "系统管理员",
        "code": "admin",
        "description": "拥有所有权限的系统管理员",
        "permission_codes": [p["code"] for p in PERMISSIONS],  # All permissions
    },
    {
        "name": "数据管理员",
        "code": "data_admin",
        "description": "管理DDL/TTL文件和映射任务",
        "permission_codes": [
            "ddl:list", "ddl:upload", "ddl:delete",
            "ttl:list", "ttl:upload", "ttl:delete",
            "job:list", "job:create", "job:update", "job:control",
            "review:list", "review:approve", "review:reject",
            "graph:explore", "graph:query",
            "sync:list", "sync:create",
        ],
    },
    {
        "name": "数据分析师",
        "code": "analyst",
        "description": "查看和分析映射结果",
        "permission_codes": [
            "ddl:list", "ttl:list",
            "job:list",
            "review:list",
            "graph:explore", "graph:query",
        ],
    },
    {
        "name": "访客",
        "code": "viewer",
        "description": "只读访问权限",
        "permission_codes": [
            "ddl:list", "ttl:list",
            "job:list",
            "review:list",
            "graph:explore",
        ],
    },
]

ADMIN_USER = {
    "username": "admin",
    "password": "admin123",  # Change this in production!
    "email": "admin@loanfibo.com",
    "role_code": "admin",
}


# ── Seed Function ──────────────────────────────────────────────────────

async def seed_rbac():
    """Insert permissions, roles, and admin user if they don't exist."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Create Permissions
            print("📋 Seeding permissions...")
            perm_map = {}
            for perm_data in PERMISSIONS:
                existing = (await db.execute(
                    select(Permission).where(Permission.code == perm_data["code"])
                )).scalar_one_or_none()
                
                if not existing:
                    perm = Permission(**perm_data)
                    db.add(perm)
                    await db.flush()
                    perm_map[perm_data["code"]] = perm.id
                    print(f"  ✅ Created permission: {perm_data['code']}")
                else:
                    perm_map[perm_data["code"]] = existing.id
            
            await db.flush()
            print(f"✅ Total permissions: {len(perm_map)}")

            # 2. Create Roles
            print("\n🎭 Seeding roles...")
            role_map = {}
            for role_data in ROLES:
                existing = (await db.execute(
                    select(Role).where(Role.code == role_data["code"])
                )).scalar_one_or_none()
                
                if not existing:
                    role = Role(
                        name=role_data["name"],
                        code=role_data["code"],
                        description=role_data["description"],
                    )
                    
                    # Assign permissions
                    perm_ids = [
                        perm_map[code] 
                        for code in role_data["permission_codes"] 
                        if code in perm_map
                    ]
                    perms = (await db.execute(
                        select(Permission).where(Permission.id.in_(perm_ids))
                    )).scalars().all()
                    role.permissions = list(perms)
                    
                    db.add(role)
                    await db.flush()
                    role_map[role_data["code"]] = role.id
                    print(f"  ✅ Created role: {role_data['name']} ({len(perms)} permissions)")
                else:
                    role_map[role_data["code"]] = existing.id
                    print(f"  ⏭️  Role already exists: {role_data['name']}")
            
            await db.flush()
            print(f"✅ Total roles: {len(role_map)}")

            # 3. Create Admin User
            print("\n👤 Seeding admin user...")
            existing_admin = (await db.execute(
                select(User).where(User.username == ADMIN_USER["username"])
            )).scalar_one_or_none()
            
            if not existing_admin:
                admin = User(
                    username=ADMIN_USER["username"],
                    password_hash=pwd_context.hash(ADMIN_USER["password"]),
                    email=ADMIN_USER["email"],
                )
                
                # Assign admin role
                admin_role = (await db.execute(
                    select(Role).where(Role.code == ADMIN_USER["role_code"])
                )).scalar_one_or_none()
                
                if admin_role:
                    admin.roles = [admin_role]
                    db.add(admin)
                    await db.flush()
                    print(f"  ✅ Created admin user: {ADMIN_USER['username']}")
                    print(f"  🔑 Default password: {ADMIN_USER['password']}")
                else:
                    print(f"  ❌ Admin role not found!")
            else:
                print(f"  ⏭️  Admin user already exists: {ADMIN_USER['username']}")
            
            await db.commit()
            print("\n✅ RBAC seed completed successfully!")
            
        except Exception as e:
            await db.rollback()
            print(f"\n❌ Error seeding RBAC data: {e}")
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("LoanFIBO RBAC Seed Script")
    print("=" * 60)
    asyncio.run(seed_rbac())

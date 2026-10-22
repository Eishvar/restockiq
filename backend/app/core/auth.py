"""Simulated login. The browser sends `X-User-Id`; `require_role()` guards endpoints by role.

Roles are ordered owner > manager > staff, so require_role("manager") also lets the owner in.
Real deployments would swap `current_user` for a proper session/JWT check; routers stay unchanged.
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.settings.models import User

ROLE_RANK = {"staff": 1, "manager": 2, "owner": 3}


def current_user(
    x_user_id: int | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if x_user_id is None:
        raise HTTPException(401, "Please choose a user (X-User-Id header missing)")
    user = db.get(User, x_user_id)
    if user is None:
        raise HTTPException(401, "Unknown user")
    return user


def require_role(min_role: str):
    """Dependency factory: the caller must have at least `min_role`."""
    if min_role not in ROLE_RANK:
        raise ValueError(f"Unknown role: {min_role}")

    def checker(user: User = Depends(current_user)) -> User:
        if ROLE_RANK.get(user.role, 0) < ROLE_RANK[min_role]:
            raise HTTPException(403, f"This needs the {min_role} role or higher; you are signed in as {user.role}")
        return user

    return checker

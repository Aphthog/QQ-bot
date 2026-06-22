"""Access control data models and SQLite storage."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Permission(str, Enum):
    BANNED = "banned"
    USER = "user"
    ADMIN = "admin"
    SUPERUSER = "superuser"


@dataclass
class AccessRule:
    id: int = 0
    user_id: str = ""
    group_id: str = ""
    rule_type: str = ""  # "blacklist" | "whitelist" | "permission"
    level: str = ""
    reason: str = ""
    added_by: str = ""
    added_at: int = 0

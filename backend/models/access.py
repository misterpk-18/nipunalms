"""Users, roles, role scopes and login sessions."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import db
from models.masters import Branch


class Role(db.Model):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_code: Mapped[str] = mapped_column(String(50), unique=True)
    role_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    is_company_wide: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self) -> dict:
        return {
            "role_id": self.role_id,
            "role_code": self.role_code,
            "role_name": self.role_name,
            "description": self.description,
            "is_company_wide": self.is_company_wide,
        }


class User(db.Model):
    """A staff member or a student login (student_id set)."""

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    student_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("students.student_id"), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())

    scopes: Mapped[list["UserRoleScope"]] = relationship(
        back_populates="user", foreign_keys="UserRoleScope.user_id", order_by="UserRoleScope.scope_id"
    )

    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """The user block of the login / profile response."""
        return {
            "user_id": self.user_id,
            "full_name": self.full_name,
            "email": self.email,
            "must_change_password": self.must_change_password,
            "student_id": self.student_id,
        }

    def to_summary(self) -> dict:
        return {"user_id": self.user_id, "full_name": self.full_name, "email": self.email}


class UserRoleScope(db.Model):
    """One role at one branch (branch_id NULL = all branches, company-wide roles only)."""

    __tablename__ = "user_role_scopes"

    scope_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.role_id"))
    branch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("branches.branch_id"))
    granted_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="scopes", foreign_keys=[user_id])
    role: Mapped[Role] = relationship(lazy="joined")
    branch: Mapped[Branch | None] = relationship(lazy="joined")

    def to_dict(self) -> dict:
        return {
            "scope_id": self.scope_id,
            "role_code": self.role.role_code,
            "role_name": self.role.role_name,
            "branch_id": self.branch_id,
            "branch_code": self.branch.branch_code if self.branch else None,
            "branch_name": self.branch.branch_name if self.branch else None,
            "is_company_wide": self.role.is_company_wide,
        }


class UserSession(db.Model):
    """A login. session_id is the SHA-256 of the bearer token; the token itself is never stored."""

    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=db.func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # filled by trigger
    reauthenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(100))


class ActiveSession(db.Model):
    """Read-only view: sessions not revoked, not past their maximum and not idle, with the fresh-auth flag."""

    __tablename__ = "active_sessions"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    has_fresh_auth: Mapped[bool] = mapped_column(Boolean)

    def to_dict(self, current_session_id: str | None = None) -> dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "expires_at": self.expires_at,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "user_agent": self.user_agent,
            "current": self.session_id == current_session_id,
        }

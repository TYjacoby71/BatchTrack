from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Tuple

from flask_login import current_user

from app.extensions import db
from app.models import User


class UserService:
    """Helper functions for developer-managed user operations."""

    @staticmethod
    def list_customer_users():
        return User.query.filter(User.user_type != "developer").all()

    @staticmethod
    def list_developer_users():
        return User.query.filter(User.user_type == "developer").all()

    @staticmethod
    def toggle_user_active(user: User) -> Tuple[bool, str]:
        user.is_active = not user.is_active
        db.session.commit()
        status = "activated" if user.is_active else "deactivated"
        return True, f"User {user.username} {status}"

    @staticmethod
    def serialize_user(user: User) -> Dict[str, str]:
        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
            "user_type": user.user_type,
            "is_active": user.is_active,
            "organization_id": user.organization_id,
            "organization_name": user.organization.name if user.organization else None,
            "last_login": user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else None,
            "created_at": user.created_at.strftime("%Y-%m-%d") if user.created_at else None,
        }

    @staticmethod
    def update_user(user: User, data: Dict) -> Tuple[bool, str]:
        if user.user_type == "developer":
            return False, "Cannot edit developer users through this endpoint"

        user.first_name = data.get("first_name", user.first_name)
        user.last_name = data.get("last_name", user.last_name)
        user.email = data.get("email", user.email)
        user.phone = data.get("phone", user.phone)
        user.user_type = data.get("user_type", user.user_type)
        user.is_active = data.get("is_active", user.is_active)

        if "is_organization_owner" in data:
            new_owner_status = data["is_organization_owner"]
            from app.models.role import Role

            org_owner_role = Role.query.filter_by(
                name="organization_owner", is_system_role=True
            ).first()

            if new_owner_status and not user.is_organization_owner:
                other_owners = User.query.filter(
                    User.organization_id == user.organization_id,
                    User.id != user.id,
                    User._is_organization_owner == True,
                ).all()
                for other in other_owners:
                    other.is_organization_owner = False
                    if org_owner_role:
                        other.remove_role(org_owner_role)

                user.is_organization_owner = True
                if org_owner_role:
                    user.assign_role(org_owner_role, assigned_by=current_user)

            elif not new_owner_status and user.is_organization_owner:
                user.is_organization_owner = False
                if org_owner_role:
                    user.remove_role(org_owner_role)

        try:
            db.session.commit()
            return True, "User updated successfully"
        except Exception as exc:  # pragma: no cover - defensive
            db.session.rollback()
            return False, str(exc)

    @staticmethod
    def update_developer_user(user: User, data: Dict) -> Tuple[bool, str]:
        if user.user_type != "developer":
            return False, "User is not a developer"

        user.first_name = data.get("first_name", user.first_name)
        user.last_name = data.get("last_name", user.last_name)
        user.email = data.get("email", user.email)
        user.phone = data.get("phone", user.phone)
        user.is_active = data.get("is_active", user.is_active)

        from app.models.user_role_assignment import UserRoleAssignment

        existing_assignments = UserRoleAssignment.query.filter_by(
            user_id=user.id, is_active=True
        ).filter(UserRoleAssignment.developer_role_id.isnot(None)).all()

        for assignment in existing_assignments:
            assignment.is_active = False

        for role_id in data.get("roles", []):
            existing = UserRoleAssignment.query.filter_by(
                user_id=user.id, developer_role_id=role_id
            ).first()
            if existing:
                existing.is_active = True
                existing.assigned_at = datetime.now(timezone.utc)
                existing.assigned_by = current_user.id
            else:
                db.session.add(
                    UserRoleAssignment(
                        user_id=user.id,
                        developer_role_id=role_id,
                        assigned_by=current_user.id,
                        is_active=True,
                    )
                )

        try:
            db.session.commit()
            return True, "Developer user updated successfully"
        except Exception as exc:  # pragma: no cover - defensive
            db.session.rollback()
            return False, str(exc)

    @staticmethod
    def reset_password(user: User, new_password: str) -> Tuple[bool, str]:
        if not new_password:
            return False, "New password is required"
        user.set_password(new_password)
        db.session.commit()
        return True, "Password reset successfully"

    @staticmethod
    def soft_delete_user(user: User) -> Tuple[bool, str]:
        if user.user_type == "developer":
            return False, "Cannot soft delete developer users"
        user.soft_delete(current_user)
        return True, "User soft deleted successfully"

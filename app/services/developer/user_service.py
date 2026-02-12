"""Developer user service helpers.

Synopsis:
Provides developer-only user management operations including profile updates,
role assignment orchestration, soft delete, and scoped hard-delete cleanup.

Glossary:
- Soft delete: Access revocation while retaining account record/history.
- Hard delete: Permanent account removal after FK cleanup.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Dict, Tuple

from flask_login import current_user

from app.extensions import db
from app.models import User


# --- User service class ---
# Purpose: Encapsulate developer-managed user lifecycle and account operations.
# Inputs: Method-level user rows and request payloads for profile/deletion workflows.
# Outputs: Query results plus tuple status messages and persisted user state changes.
class UserService:
    """Helper functions for developer-managed user operations."""

    # --- List customer users ---
    # Purpose: Fetch all non-developer users for developer management dashboards.
    # Inputs: None.
    # Outputs: Query result list of customer/team accounts.
    @staticmethod
    def list_customer_users():
        return User.query.filter(User.user_type != "developer").all()

    # --- List customer users with pagination ---
    # Purpose: Fetch non-developer users with deterministic ordering for paged views.
    # Inputs: page number and per-page size.
    # Outputs: Flask-SQLAlchemy Pagination object.
    @staticmethod
    def list_customer_users_paginated(page: int, per_page: int):
        return (
            User.query.filter(User.user_type != "developer")
            .order_by(User.created_at.desc(), User.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    # --- List developer users ---
    # Purpose: Fetch internal developer accounts for role/admin views.
    # Inputs: None.
    # Outputs: Query result list of developer users.
    @staticmethod
    def list_developer_users():
        return User.query.filter(User.user_type == "developer").all()

    # --- List developer users with pagination ---
    # Purpose: Fetch developer users with deterministic ordering for paged views.
    # Inputs: page number and per-page size.
    # Outputs: Flask-SQLAlchemy Pagination object.
    @staticmethod
    def list_developer_users_paginated(page: int, per_page: int):
        return (
            User.query.filter(User.user_type == "developer")
            .order_by(User.created_at.desc(), User.id.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

    # --- Update own profile ---
    # Purpose: Apply self-service profile edits for developer manage-users page.
    # Inputs: Current user row and JSON payload.
    # Outputs: Tuple(success flag, status message).
    @staticmethod
    def update_own_profile(user: User, data: Dict) -> Tuple[bool, str]:
        username = (data.get("username", user.username) or "").strip()
        if not username:
            return False, "Username is required"

        if len(username) > 64:
            return False, "Username must be 64 characters or fewer"

        if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
            return (
                False,
                "Username may only include letters, numbers, underscore, hyphen, and dot",
            )

        existing_user = User.query.filter(
            User.username == username,
            User.id != user.id,
        ).first()
        if existing_user:
            return False, "Username is already in use"

        user.username = username
        user.first_name = (data.get("first_name", user.first_name) or "").strip() or None
        user.last_name = (data.get("last_name", user.last_name) or "").strip() or None
        user.email = (data.get("email", user.email) or "").strip() or None
        user.phone = (data.get("phone", user.phone) or "").strip() or None

        if "timezone" in data:
            user.timezone = data.get("timezone")

        try:
            db.session.commit()
            return True, "Profile updated successfully"
        except Exception as exc:  # pragma: no cover - defensive
            db.session.rollback()
            return False, str(exc)

    # --- Toggle user active flag ---
    # Purpose: Flip active/inactive state for a user account.
    # Inputs: User row.
    # Outputs: Tuple(success flag, status message).
    @staticmethod
    def toggle_user_active(user: User) -> Tuple[bool, str]:
        user.is_active = not user.is_active
        db.session.commit()
        status = "activated" if user.is_active else "deactivated"
        return True, f"User {user.username} {status}"

    # --- Serialize user payload ---
    # Purpose: Build API-friendly user detail payload for modal editing UI.
    # Inputs: User row.
    # Outputs: Dict with user metadata fields.
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

    # --- Update customer user ---
    # Purpose: Apply editable profile/ownership fields for non-developer users.
    # Inputs: User row and JSON payload.
    # Outputs: Tuple(success flag, status message).
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

    # --- Update developer user ---
    # Purpose: Apply developer profile fields and active developer role assignments.
    # Inputs: Developer user row and JSON payload.
    # Outputs: Tuple(success flag, status message).
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

    # --- Reset user password ---
    # Purpose: Set a new password for a selected user account.
    # Inputs: User row and plaintext new password.
    # Outputs: Tuple(success flag, status message).
    @staticmethod
    def reset_password(user: User, new_password: str) -> Tuple[bool, str]:
        if not new_password:
            return False, "New password is required"
        user.set_password(new_password)
        db.session.commit()
        return True, "Password reset successfully"

    # --- Soft delete user ---
    # Purpose: Revoke account access while preserving historical data.
    # Inputs: User row.
    # Outputs: Tuple(success flag, status message).
    @staticmethod
    def soft_delete_user(user: User) -> Tuple[bool, str]:
        if user.user_type == "developer":
            return False, "Cannot soft delete developer users"
        user.soft_delete(current_user)
        return True, "User soft deleted successfully"

    # --- Hard delete user ---
    # Purpose: Permanently remove a non-developer account after FK cleanup.
    # Inputs: User row.
    # Outputs: Tuple(success flag, status message).
    @staticmethod
    def hard_delete_user(user: User) -> Tuple[bool, str]:
        if user.user_type == "developer":
            return False, "Cannot hard delete developer users"

        username = user.username
        try:
            from app.services.billing_service import BillingService
            from app.services.developer.deletion_utils import clear_user_foreign_keys

            stripe_cancelled = False
            org = user.organization
            if org and org.stripe_customer_id:
                remaining_customer_users = (
                    User.query.filter(
                        User.organization_id == org.id,
                        User.user_type == "customer",
                        User.id != user.id,
                        User.is_deleted.is_(False),
                    ).count()
                )
                # If this is the final customer account in the organization, cancel billing first.
                if remaining_customer_users == 0:
                    stripe_cancelled = BillingService.cancel_subscription(org.stripe_customer_id)
                    if not stripe_cancelled:
                        return (
                            False,
                            "Failed to cancel Stripe subscription before deleting final customer account.",
                        )

            clear_user_foreign_keys([user.id])
            db.session.delete(user)
            db.session.commit()
            message = f'User "{username}" permanently deleted'
            if stripe_cancelled:
                message += " Stripe subscription canceled."
            return True, message
        except Exception as exc:  # pragma: no cover - defensive
            db.session.rollback()
            return False, str(exc)

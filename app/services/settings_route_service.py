"""Settings-route service boundary.

Synopsis:
Encapsulates settings route data/session access so `settings/routes.py`
stays transport-focused.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import InventoryItem, User, UserPreferences


class SettingsRouteService:
    """Data/session helpers for settings route workflows."""

    @staticmethod
    def get_user_preferences_for_user(*, user_id: int) -> UserPreferences | None:
        return UserPreferences.get_for_user(user_id)

    @staticmethod
    def update_user_preferences_from_payload(
        *,
        user_prefs: UserPreferences,
        payload: dict[str, Any],
    ) -> None:
        for key, value in (payload or {}).items():
            if hasattr(user_prefs, key):
                setattr(user_prefs, key, value)
        user_prefs.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def save_profile_fields(
        *,
        user: User,
        username: str,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        timezone_name: str | None,
    ) -> None:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.phone = phone
        user.timezone = timezone_name
        db.session.commit()

    @staticmethod
    def set_user_password_hash(*, user: User, new_password: str) -> None:
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()

    @staticmethod
    def set_user_password(*, user: User, password: str) -> None:
        user.set_password(password)
        db.session.commit()

    @staticmethod
    def bulk_update_inventory_items(
        *,
        updates: list[dict[str, Any]],
        require_container_type: bool = False,
    ) -> int:
        updated_count = 0
        for item_data in updates or []:
            item_id = item_data.get("id")
            if not item_id:
                continue
            item = db.session.get(InventoryItem, item_id)
            if not item:
                continue
            if require_container_type and item.type != "container":
                continue

            if "name" in item_data:
                item.name = item_data["name"]
            if "unit" in item_data and not require_container_type:
                item.unit = item_data["unit"]
            if "capacity" in item_data:
                item.capacity = item_data.get("capacity")
            if "capacity_unit" in item_data:
                item.capacity_unit = item_data.get("capacity_unit")
            if "cost_per_unit" in item_data:
                item.cost_per_unit = item_data["cost_per_unit"]
            updated_count += 1

        db.session.commit()
        return updated_count

    @staticmethod
    def bulk_update_ingredients(*, updates: list[dict[str, Any]]) -> int:
        return SettingsRouteService.bulk_update_inventory_items(
            updates=updates,
            require_container_type=False,
        )

    @staticmethod
    def bulk_update_containers(*, updates: list[dict[str, Any]]) -> int:
        return SettingsRouteService.bulk_update_inventory_items(
            updates=updates,
            require_container_type=True,
        )

    @staticmethod
    def update_user_timezone(*, user: User, timezone_name: str) -> None:
        user.timezone = timezone_name
        db.session.commit()

    @staticmethod
    def update_single_preference(
        *,
        user_prefs: UserPreferences,
        key: str,
        value: Any,
    ) -> bool:
        if not hasattr(user_prefs, key):
            return False
        setattr(user_prefs, key, value)
        db.session.commit()
        return True

    @staticmethod
    def list_users_grouped_by_type() -> tuple[list[User], list[User]]:
        customer_users = User.query.filter(User.user_type != "developer").all()
        developer_users = User.query.filter(User.user_type == "developer").all()
        return customer_users, developer_users

    @staticmethod
    def list_user_management_groups() -> tuple[list[User], list[User]]:
        return SettingsRouteService.list_users_grouped_by_type()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()

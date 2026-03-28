"""Developer system-role service layer.

Synopsis:
Centralizes developer-only role and developer-user management workflows so
route handlers stay thin and do not own ORM/session transactions.

Glossary:
- System role: Cross-organization role template (`Role.is_system_role=True`).
- Developer role: Internal platform role built from developer permissions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Permission, Role, User
from app.models.developer_permission import DeveloperPermission
from app.models.developer_role import DeveloperRole
from app.models.user_role_assignment import UserRoleAssignment

logger = logging.getLogger(__name__)


class SystemRoleService:
    """Business logic for developer system-role management routes."""

    @staticmethod
    def get_manage_page_context() -> Dict[str, Any]:
        return {
            "roles": Role.query.filter_by(is_system_role=True).all(),
            "developer_roles": DeveloperRole.query.filter_by(is_active=True).all(),
            "developer_users": User.query.filter_by(user_type="developer").all(),
        }

    @staticmethod
    def create_system_role(data: Dict[str, Any], *, created_by: int) -> Dict[str, Any]:
        try:
            existing_role = Role.query.filter_by(
                name=data["name"], is_system_role=True
            ).first()
            if existing_role:
                return {
                    "success": False,
                    "error": "System role with this name already exists",
                }

            role = Role(
                name=data["name"],
                description=data.get("description"),
                is_system_role=True,
                organization_id=None,
                created_by=created_by,
            )
            permission_ids = data.get("permission_ids", [])
            permissions = Permission.query.filter(
                Permission.id.in_(permission_ids)
            ).all()
            role.permissions = permissions
            db.session.add(role)
            db.session.commit()
            return {
                "success": True,
                "message": f'System role "{role.name}" created successfully',
            }
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/services/developer/system_role_service.py:create_system_role",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_system_role_payload(role_id: int) -> Dict[str, Any]:
        role = Role.query.filter_by(id=role_id, is_system_role=True).first_or_404()
        return {
            "success": True,
            "role": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permission_ids": [perm.id for perm in role.permissions],
            },
        }

    @staticmethod
    def update_system_role(role_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            role = Role.query.filter_by(id=role_id, is_system_role=True).first_or_404()
            if role.name != "organization_owner":
                role.name = data.get("name", role.name)
            role.description = data.get("description", role.description)

            if "permission_ids" in data:
                permission_ids = data["permission_ids"]
                permissions = Permission.query.filter(
                    Permission.id.in_(permission_ids)
                ).all()
                role.permissions = permissions

            db.session.commit()
            return {
                "success": True,
                "message": f'System role "{role.name}" updated successfully',
            }
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/services/developer/system_role_service.py:update_system_role",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def delete_system_role(role_id: int) -> Dict[str, Any]:
        try:
            role = Role.query.filter_by(id=role_id, is_system_role=True).first_or_404()
            db.session.delete(role)
            db.session.commit()
            return {
                "success": True,
                "message": f'System role "{role.name}" deleted successfully',
            }
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/services/developer/system_role_service.py:delete_system_role",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def create_developer_role(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            existing_role = DeveloperRole.query.filter_by(name=data["name"]).first()
            if existing_role:
                return {
                    "success": False,
                    "error": "Developer role with this name already exists",
                }

            role = DeveloperRole(
                name=data["name"],
                description=data.get("description"),
                category=data.get("category", "developer"),
            )
            permission_ids = data.get("permission_ids", [])
            permissions = DeveloperPermission.query.filter(
                DeveloperPermission.id.in_(permission_ids)
            ).all()
            role.permissions = permissions
            db.session.add(role)
            db.session.commit()
            return {
                "success": True,
                "message": f'Developer role "{role.name}" created successfully',
            }
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/services/developer/system_role_service.py:create_developer_role",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_developer_role_payload(role_id: int) -> Dict[str, Any]:
        role = DeveloperRole.query.filter_by(id=role_id).first_or_404()
        return {
            "success": True,
            "role": {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "category": role.category,
                "permission_ids": [perm.id for perm in role.permissions],
            },
        }

    @staticmethod
    def update_developer_role(role_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            role = DeveloperRole.query.filter_by(id=role_id).first_or_404()
            role.name = data.get("name", role.name)
            role.description = data.get("description", role.description)
            role.category = data.get("category", role.category)
            if "permission_ids" in data:
                permission_ids = data["permission_ids"]
                permissions = DeveloperPermission.query.filter(
                    DeveloperPermission.id.in_(permission_ids)
                ).all()
                role.permissions = permissions
            db.session.commit()
            return {
                "success": True,
                "message": f'Developer role "{role.name}" updated successfully',
            }
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/services/developer/system_role_service.py:update_developer_role",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def delete_developer_role(role_id: int) -> Dict[str, Any]:
        try:
            role = DeveloperRole.query.filter_by(id=role_id).first_or_404()
            db.session.delete(role)
            db.session.commit()
            return {
                "success": True,
                "message": f'Developer role "{role.name}" deleted successfully',
            }
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/services/developer/system_role_service.py:delete_developer_role",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def create_developer_user(
        data: Dict[str, Any], *, assigned_by: int
    ) -> Dict[str, Any]:
        try:
            username = User.normalize_username(data.get("username"))
            email = User.normalize_email(data.get("email"))
            if not username or not data.get("password"):
                return {
                    "success": False,
                    "error": "Username and password are required",
                }

            if User.username_exists(username):
                return {"success": False, "error": "Username already exists"}
            if email and User.email_exists(email):
                return {"success": False, "error": "Email already exists"}

            user = User(
                username=username,
                password_hash=generate_password_hash(data["password"]),
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                email=email,
                user_type="developer",
                organization_id=None,
                is_active=True,
            )
            db.session.add(user)
            db.session.flush()

            developer_role_id = data.get("developer_role_id")
            if developer_role_id:
                developer_role = DeveloperRole.query.filter_by(
                    id=developer_role_id
                ).first()
                if developer_role:
                    db.session.add(
                        UserRoleAssignment(
                            user_id=user.id,
                            developer_role_id=developer_role.id,
                            organization_id=None,
                            assigned_by=assigned_by,
                            is_active=True,
                        )
                    )

            db.session.commit()
            return {
                "success": True,
                "message": f'Developer user "{user.username}" created successfully',
            }
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/services/developer/system_role_service.py:create_developer_user",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def update_developer_user_role(
        user_id: int, data: Dict[str, Any], *, assigned_by: int
    ) -> Dict[str, Any]:
        try:
            user = User.query.filter_by(
                id=user_id, user_type="developer"
            ).first_or_404()
            developer_role_id = data.get("developer_role_id")

            existing_assignments = (
                UserRoleAssignment.query.filter_by(user_id=user.id, is_active=True)
                .filter(UserRoleAssignment.developer_role_id.isnot(None))
                .all()
            )
            for assignment in existing_assignments:
                assignment.is_active = False

            developer_role = None
            if developer_role_id:
                developer_role = DeveloperRole.query.filter_by(
                    id=developer_role_id
                ).first()
                if developer_role:
                    db.session.add(
                        UserRoleAssignment(
                            user_id=user.id,
                            developer_role_id=developer_role.id,
                            organization_id=None,
                            assigned_by=assigned_by,
                            is_active=True,
                        )
                    )

            db.session.commit()
            role_name = (
                developer_role.name
                if developer_role_id and developer_role
                else "No role"
            )
            return {
                "success": True,
                "message": f'Developer user "{user.username}" assigned to role: {role_name}',
            }
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/services/developer/system_role_service.py:update_developer_user_role",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_developer_user_role(user_id: int) -> Dict[str, Any]:
        user = User.query.filter_by(id=user_id, user_type="developer").first_or_404()
        assignment = (
            UserRoleAssignment.query.filter_by(user_id=user.id, is_active=True)
            .filter(UserRoleAssignment.developer_role_id.isnot(None))
            .first()
        )
        current_role_id: Optional[int] = (
            assignment.developer_role_id if assignment else None
        )
        return {"success": True, "current_role_id": current_role_id}

    @staticmethod
    def delete_developer_user(
        user_id: int, *, current_user_obj: User
    ) -> Dict[str, Any]:
        try:
            user = User.query.filter_by(
                id=user_id, user_type="developer"
            ).first_or_404()
            if user.id == current_user_obj.id:
                return {"success": False, "error": "Cannot delete your own account"}
            user.soft_delete(deleted_by_user=current_user_obj)
            return {
                "success": True,
                "message": f'Developer user "{user.username}" deleted successfully',
            }
        except Exception as exc:
            logger.warning(
                "Suppressed exception fallback at app/services/developer/system_role_service.py:delete_developer_user",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_permissions_grouped() -> Dict[str, List[Dict[str, Any]]]:
        permissions = Permission.query.filter_by(is_active=True).all()
        categories: Dict[str, List[Dict[str, Any]]] = {}
        for perm in permissions:
            category = perm.category or "general"
            categories.setdefault(category, []).append(
                {"id": perm.id, "name": perm.name, "description": perm.description}
            )
        return categories

    @staticmethod
    def get_developer_permissions_grouped() -> Dict[str, List[Dict[str, Any]]]:
        permissions = DeveloperPermission.query.filter_by(is_active=True).all()
        categories: Dict[str, List[Dict[str, Any]]] = {}
        for perm in permissions:
            category = perm.category or "general"
            categories.setdefault(category, []).append(
                {"id": perm.id, "name": perm.name, "description": perm.description}
            )
        return categories

    @staticmethod
    def get_active_developer_roles_payload() -> List[Dict[str, Any]]:
        roles = DeveloperRole.query.filter_by(is_active=True).all()
        return [
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "category": role.category,
            }
            for role in roles
        ]

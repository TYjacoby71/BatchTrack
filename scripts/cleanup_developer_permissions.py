#!/usr/bin/env python3
"""Remove legacy app.* developer permissions (non-customer)."""

from __future__ import annotations

from app import create_app
from app.extensions import db
from app.models.developer_permission import DeveloperPermission
from app.models.developer_role import DeveloperRole


def cleanup_developer_permissions():
    app = create_app()
    with app.app_context():
        legacy_perms = DeveloperPermission.query.filter(
            DeveloperPermission.name.like("app.%")
        ).all()
        if not legacy_perms:
            print("ℹ️  No legacy app.* developer permissions found.")
            return

        legacy_ids = {perm.id for perm in legacy_perms}
        for perm in legacy_perms:
            db.session.delete(perm)

        roles = DeveloperRole.query.all()
        for role in roles:
            role.permissions = [p for p in role.permissions if p.id not in legacy_ids]

        db.session.commit()
        print(f"✅ Removed {len(legacy_perms)} legacy app.* developer permissions")


if __name__ == "__main__":
    cleanup_developer_permissions()

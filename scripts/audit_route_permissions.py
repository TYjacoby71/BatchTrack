#!/usr/bin/env python3
"""Audit routes for permission decorator coverage."""

from __future__ import annotations

from app import create_app
from app.route_access import RouteAccessConfig
from app.seeders.consolidated_permission_seeder import load_consolidated_permissions


def _is_public(rule) -> bool:
    if RouteAccessConfig.is_public_endpoint(rule.endpoint):
        return True
    if RouteAccessConfig.is_public_path(rule.rule):
        return True
    return False


def _format_methods(rule) -> str:
    methods = sorted(method for method in rule.methods or [] if method not in {"HEAD", "OPTIONS"})
    return ",".join(methods)


def audit_route_permissions() -> int:
    app = create_app()
    with app.app_context():
        catalog_permissions = set()
        try:
            data = load_consolidated_permissions()
            for category in data.get("organization_permissions", {}).values():
                for perm in category.get("permissions", []):
                    name = perm.get("name")
                    if name:
                        catalog_permissions.add(name)
            for category in data.get("developer_permissions", {}).values():
                for perm in category.get("permissions", []):
                    name = perm.get("name")
                    if name:
                        catalog_permissions.add(name)
            for perm in data.get("system_administration", {}).get("permissions", []):
                name = perm.get("name")
                if name:
                    catalog_permissions.add(name)
        except Exception as exc:
            print(f"⚠️  Unable to load permission catalog: {exc}")

        missing_permissions = []
        undefined_permissions = []

        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            if rule.endpoint == "static":
                continue
            if _is_public(rule):
                continue

            view_func = app.view_functions.get(rule.endpoint)
            required = getattr(view_func, "_required_permissions", None) if view_func else None
            if not required:
                missing_permissions.append((rule.rule, rule.endpoint, _format_methods(rule)))
                continue

            for permission_name in sorted(required):
                if catalog_permissions and permission_name not in catalog_permissions:
                    undefined_permissions.append((permission_name, rule.rule, rule.endpoint))

        if missing_permissions:
            print("❌ Routes missing permission decorators:")
            for rule, endpoint, methods in missing_permissions:
                print(f"  - {rule} [{methods}] -> {endpoint}")
        else:
            print("✅ All non-public routes declare permissions.")

        if undefined_permissions:
            print("\n❌ Permissions referenced but not in catalog:")
            for permission_name, rule, endpoint in undefined_permissions:
                print(f"  - {permission_name} on {rule} -> {endpoint}")
        else:
            print("\n✅ All referenced permissions exist in catalog.")

        return 1 if missing_permissions or undefined_permissions else 0


if __name__ == "__main__":
    raise SystemExit(audit_route_permissions())

#!/usr/bin/env python3
"""Audit routes for permission decorator coverage."""

from __future__ import annotations

from app import create_app
from app.route_access import RouteAccessConfig
from app.utils.permissions import permission_exists_in_catalog


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
                if not permission_exists_in_catalog(permission_name):
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

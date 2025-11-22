"""
Helper utilities to bootstrap load-test data (organization, users, seed data)
and to read the generated credentials file for Locust.
"""

from __future__ import annotations

import json
import os
import random
import re
from typing import Dict, List

DEFAULT_PASSWORD = "test123"
USERNAME_PATTERN = re.compile(r"^test(\d+)$", re.IGNORECASE)


def load_mutation_accounts(accounts_file: str) -> List[Dict[str, str]]:
    """Load previously generated mutation accounts from disk."""
    if not accounts_file or not os.path.exists(accounts_file):
        return []

    try:
        with open(accounts_file, "r", encoding="utf-8") as fh:
            payload = json.load(fh) or {}
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"⚠️  Unable to read load-test accounts file '{accounts_file}': {exc}")
        return []

    users = payload.get("users") or []
    cleaned: List[Dict[str, str]] = []

    for entry in users:
        if not isinstance(entry, dict):
            continue
        username = entry.get("username")
        if not username:
            continue
        cleaned.append(
            {
                "username": username,
                "password": entry.get("password", DEFAULT_PASSWORD),
                "role": entry.get("role", "worker"),
            }
        )

    return cleaned


def bootstrap_loadtest_org(accounts_file: str) -> Dict[str, object]:
    """
    Create a fresh organization with two staged users (owner + worker),
    seed inventory/recipes via the living test data seeder, and write the
    resulting credentials to disk so Locust can rotate through them.
    """

    from app import create_app

    app = create_app()
    with app.app_context():
        return _bootstrap_within_context(accounts_file)


def _bootstrap_within_context(accounts_file: str) -> Dict[str, object]:
    from werkzeug.security import generate_password_hash

    from app.extensions import db
    from app.models import Organization, Role, SubscriptionTier, User
    from app.models.user_role_assignment import UserRoleAssignment
    from app.seeders.test_data_seeder import seed_test_data
    from app.seeders.user_seeder import seed_users_and_organization

    # Ensure base admin + tiers exist so the seeders have what they expect.
    if not SubscriptionTier.query.count():
        raise RuntimeError("No subscription tiers found. Run subscription tier seeder before bootstrapping load tests.")

    if not User.query.filter_by(username="admin").first():
        seed_users_and_organization()
        db.session.commit()

    tier = SubscriptionTier.query.filter_by(name="Exempt Plan").first() or SubscriptionTier.query.first()
    if not tier:
        raise RuntimeError("Unable to locate a subscription tier for the new load-test organization.")

    next_suffix = _next_test_suffix()
    owner_username = f"test{next_suffix}"
    worker_username = f"test{next_suffix + 1}"

    org = Organization(
        name=f"LoadTest Org {owner_username}",
        subscription_tier_id=tier.id,
        signup_source="loadtest",
        is_active=True,
    )
    db.session.add(org)
    db.session.flush()

    phone_pool: set[str] = set()

    owner_user = _build_user(owner_username, org.id, generate_password_hash, phone_pool)
    owner_user.is_organization_owner = True
    db.session.add(owner_user)
    db.session.flush()

    worker_user = _build_user(worker_username, org.id, generate_password_hash, phone_pool)
    db.session.add(worker_user)
    db.session.flush()

    _assign_roles(owner_user, worker_user, org.id)

    if not org.contact_email:
        org.contact_email = owner_user.email

    db.session.commit()

    # Seed inventories + recipes for this organization.
    seed_test_data(organization_id=org.id)
    db.session.commit()

    payload = {
        "organization_id": org.id,
        "organization_name": org.name,
        "users": [
            {"username": owner_user.username, "password": DEFAULT_PASSWORD, "role": "owner"},
            {"username": worker_user.username, "password": DEFAULT_PASSWORD, "role": "worker"},
        ],
    }

    _write_accounts_file(accounts_file, payload)
    print(
        f"✅ Bootstrapped load-test org '{org.name}' with users "
        f"{', '.join(user['username'] for user in payload['users'])}"
    )
    return payload


def _next_test_suffix() -> int:
    from app.models import User

    max_suffix = 0
    usernames = User.query.with_entities(User.username).filter(User.username.ilike("test%")).all()
    for (username,) in usernames:
        if not username:
            continue
        match = USERNAME_PATTERN.match(username.strip())
        if match:
            max_suffix = max(max_suffix, int(match.group(1)))
    return max_suffix + 1


def _build_user(username: str, organization_id: int, hash_fn, phone_pool: set[str]) -> "User":
    from app.models import User

    phone = _unique_phone(phone_pool)
    user = User(
        username=username,
        password_hash=hash_fn(DEFAULT_PASSWORD),
        first_name=username,
        last_name="test",
        email=f"{username}@gmail.com",
        phone=phone,
        organization_id=organization_id,
        user_type="customer",
        is_active=True,
    )
    user.is_verified = True  # sync email_verified flag
    return user


def _unique_phone(pool: set[str]) -> str:
    while True:
        digits = f"{random.randint(100_000_000, 999_999_999):09d}"
        if digits not in pool:
            pool.add(digits)
            return digits


def _assign_roles(owner_user, worker_user, organization_id: int):
    from app.extensions import db
    from app.models import Role
    from app.models.user_role_assignment import UserRoleAssignment

    owner_role = Role.query.filter_by(name="organization_owner", is_system_role=True).first()
    worker_roles = Role.query.filter(Role.name.in_(["manager", "operator"])).all()

    assignments: List[UserRoleAssignment] = []
    if owner_role:
        assignments.append(
            UserRoleAssignment(
                user_id=owner_user.id,
                role_id=owner_role.id,
                organization_id=organization_id,
                is_active=True,
            )
        )

    for role in worker_roles:
        assignments.append(
            UserRoleAssignment(
                user_id=worker_user.id,
                role_id=role.id,
                organization_id=organization_id,
                is_active=True,
            )
        )

    if assignments:
        db.session.add_all(assignments)


def _write_accounts_file(path: str, payload: Dict[str, object]):
    if not path:
        return
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


"""User email uniqueness guard.

Synopsis:
Normalize existing user emails to lowercase and enforce a unique email
constraint so account creation paths cannot create duplicate identities.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from migrations.postgres_helpers import (
    constraint_exists,
    ensure_unique_constraint_or_index,
    is_postgresql,
    safe_drop_index,
)


revision = "0032_user_email_uniqueness"
down_revision = "0031_sub_tier_marketing_copy"
branch_labels = None
depends_on = None


def _normalize_user_emails() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            UPDATE "user"
            SET email = lower(trim(email))
            WHERE email IS NOT NULL
            """
        )
    )


def _assert_no_duplicate_emails() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        text(
            """
            SELECT email, COUNT(*) AS duplicate_count
            FROM "user"
            WHERE email IS NOT NULL
            GROUP BY email
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC, email ASC
            LIMIT 10
            """
        )
    ).fetchall()
    if not rows:
        return
    sample = ", ".join(f"{row[0]} ({row[1]})" for row in rows)
    raise RuntimeError(
        "Cannot enforce unique user emails; duplicates exist after normalization: "
        f"{sample}"
    )


def upgrade():
    _normalize_user_emails()
    _assert_no_duplicate_emails()
    ensure_unique_constraint_or_index("user", "uq_user_email", ["email"], verbose=False)


def downgrade():
    if is_postgresql():
        if constraint_exists("user", "uq_user_email"):
            op.drop_constraint("uq_user_email", "user", type_="unique")
    else:
        safe_drop_index("uq_user_email", table_name="user", verbose=False)

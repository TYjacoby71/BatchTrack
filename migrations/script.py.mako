"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

_MAX_REVISION_ID_LENGTH = 32
if not isinstance(revision, str) or not revision.strip():
    raise ValueError("Alembic migration `revision` must be a non-empty string")
if len(revision) > _MAX_REVISION_ID_LENGTH:
    raise ValueError(
        f"Alembic migration `revision` must be <= {_MAX_REVISION_ID_LENGTH} chars: {revision!r}"
    )


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}

"""Tag manager service boundary.

Synopsis:
Encapsulates organization-scoped tag read/write operations so route handlers
remain transport-focused and avoid direct persistence calls.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Tag


class TagManagerService:
    """Service-layer operations for tag manager routes."""

    @staticmethod
    def list_tags(*, active_only: bool = False) -> list[Tag]:
        query = Tag.scoped()
        if active_only:
            query = query.filter_by(is_active=True)
        return query.all()

    @staticmethod
    def create_tag(
        *,
        organization_id: int | None,
        created_by: int | None,
        name: str,
        color: str | None = None,
        description: str | None = None,
    ) -> Tag:
        tag = Tag(
            name=name,
            color=color or "#6c757d",
            description=description or "",
            organization_id=organization_id,
            created_by=created_by,
        )
        db.session.add(tag)
        db.session.commit()
        return tag

    @staticmethod
    def get_tag_or_404(tag_id: int) -> Tag:
        return Tag.scoped().filter_by(id=tag_id).first_or_404()

    @staticmethod
    def update_tag(
        tag: Tag,
        *,
        name: str,
        color: str | None = None,
        description: str | None = None,
    ) -> Tag:
        tag.name = name
        if color is not None:
            tag.color = color
        if description is not None:
            tag.description = description
        db.session.commit()
        return tag

    @staticmethod
    def soft_delete_tag(tag: Tag) -> None:
        tag.is_active = False
        db.session.commit()

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from ..extensions import db
from ..models import Batch, Organization, Recipe
from ..models.addon import Addon
from ..models.retention import RetentionDeletionQueue


class RetentionService:
    """Tier-driven data retention evaluation and deletion queueing."""

    @staticmethod
    def get_org_retention_days(org: Organization) -> int | None:
        if not org or not org.tier:
            return None
        # Included retention via tier-included add-on OR purchased add-on
        try:
            # Included on tier?
            included = getattr(org.tier, "included_addons", []) if org.tier else []
            if any(
                getattr(a, "function_key", None) == "retention" for a in included or []
            ):
                return None
        except Exception:
            pass

        try:
            # Purchased via Stripe?
            from ..models.addon import OrganizationAddon

            active_org_addons = OrganizationAddon.query.filter_by(
                organization_id=org.id, active=True
            ).all()
            addon_ids = [oa.addon_id for oa in active_org_addons]
            if addon_ids:
                has_retention_addon = (
                    Addon.query.filter(
                        Addon.id.in_(addon_ids), Addon.function_key == "retention"
                    ).count()
                    > 0
                )
                if has_retention_addon:
                    return None
        except Exception:
            pass

        # Default baseline: without a retention add-on (included or purchased), keep 1-year retention
        return 365

    @staticmethod
    def find_at_risk_recipes(org: Organization) -> List[Recipe]:
        """Find recipes older than org tier retention and safe to delete (no batch references)."""
        if not org:
            return []
        retention_days = RetentionService.get_org_retention_days(org)
        if not retention_days or retention_days <= 0:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        # Exclude any recipe that is referenced by a batch
        # Join-free approach: get recipe ids used by batches, then exclude
        used_recipe_ids = set(
            r[0] for r in db.session.query(Batch.recipe_id).distinct().all()
        )

        query = Recipe.query.filter(
            Recipe.organization_id == org.id, Recipe.created_at < cutoff
        )

        results: List[Recipe] = []
        for r in query.all():
            if r.id in used_recipe_ids:
                continue
            results.append(r)

        return results

    @staticmethod
    def get_pending_drawer_items(org: Organization) -> List[Recipe]:
        """Return at-risk recipes that are not yet acknowledged for this org."""
        at_risk = RetentionService.find_at_risk_recipes(org)
        if not at_risk:
            return []

        # Filter out ones already acknowledged/queued
        queued_ids = set(
            r.recipe_id
            for r in RetentionDeletionQueue.query.filter_by(
                organization_id=org.id
            ).all()
        )
        return [r for r in at_risk if r.id not in queued_ids]

    @staticmethod
    def acknowledge_and_queue(
        org: Organization, recipe_ids: List[int]
    ) -> Tuple[int, int]:
        """Mark given recipes as acknowledged and add to deletion queue with delete_after_at window (retention + 15d)."""
        if not org or not recipe_ids:
            return 0, 0

        retention_days = RetentionService.get_org_retention_days(org)
        if not retention_days or retention_days <= 0:
            return 0, 0

        now = datetime.now(timezone.utc)
        delete_after = now + timedelta(days=15)

        created = 0
        skipped = 0
        for rid in recipe_ids:
            existing = RetentionDeletionQueue.query.filter_by(
                organization_id=org.id, recipe_id=rid
            ).first()
            if existing:
                skipped += 1
                continue

            entry = RetentionDeletionQueue(
                organization_id=org.id,
                recipe_id=rid,
                status="queued",
                acknowledged_at=now,
                delete_after_at=delete_after,
            )
            db.session.add(entry)
            created += 1

        db.session.commit()
        return created, skipped

    @staticmethod
    def export_at_risk(org: Organization, format_: str = "json") -> Tuple[str, str]:
        """Return (mimetype, content) for export of at-risk items pending drawer acknowledgment."""
        import csv
        import io
        import json

        items = RetentionService.get_pending_drawer_items(org)
        data = [
            {
                "id": r.id,
                "name": r.name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "predicted_yield": r.predicted_yield,
                "predicted_yield_unit": r.predicted_yield_unit,
            }
            for r in items
        ]

        if format_ == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=(
                    list(data[0].keys())
                    if data
                    else [
                        "id",
                        "name",
                        "created_at",
                        "predicted_yield",
                        "predicted_yield_unit",
                    ]
                ),
            )
            writer.writeheader()
            for row in data:
                writer.writerow(row)
            return "text/csv", output.getvalue()

        return "application/json", json.dumps(data)

    @staticmethod
    def nightly_sweep_delete_due() -> int:
        """Delete recipes whose queue entry is past delete_after_at and still safe."""
        now = datetime.now(timezone.utc)
        due = RetentionDeletionQueue.query.filter(
            RetentionDeletionQueue.status == "queued",
            RetentionDeletionQueue.delete_after_at <= now,
        ).all()

        deleted = 0
        for entry in due:
            # Safety check: ensure not batch-referenced
            used = (
                db.session.query(Batch.id)
                .filter(Batch.recipe_id == entry.recipe_id)
                .first()
            )
            if used:
                # Cancel if it became referenced (belt-and-suspenders)
                entry.status = "canceled"
                continue

            # Delete recipe and cascade children (ingredients/consumables use delete-orphan on the relationship)
            recipe = db.session.get(Recipe, entry.recipe_id)
            if recipe:
                try:
                    db.session.delete(recipe)
                    entry.status = "deleted"
                    deleted += 1
                except Exception:
                    entry.status = "canceled"

        db.session.commit()
        return deleted

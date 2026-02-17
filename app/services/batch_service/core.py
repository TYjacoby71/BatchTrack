import logging

from flask_login import current_user
from sqlalchemy.orm.attributes import set_committed_value

from app.models import Batch, BatchTimer, Recipe, db
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class BatchService(BaseService):
    """Core batch service for basic CRUD operations and queries"""

    @classmethod
    def get_batch_by_identifier(cls, batch_identifier):
        """Get batch by ID or label code with proper scoping"""
        try:
            print(f"DEBUG: get_batch_by_identifier called with: {batch_identifier}")
            print(
                f"DEBUG: Current user organization_id: {current_user.organization_id}"
            )

            if str(batch_identifier).isdigit():
                # Check if batch exists without scoping first for debugging
                batch_exists = Batch.query.filter_by(id=int(batch_identifier)).first()
                print(f"DEBUG: Batch exists (unscoped): {batch_exists is not None}")
                if batch_exists:
                    print(
                        f"DEBUG: Batch organization_id: {batch_exists.organization_id}"
                    )

                batch = Batch.scoped().filter_by(id=int(batch_identifier)).first()
            else:
                batch = (
                    Batch.scoped().filter_by(label_code=str(batch_identifier)).first()
                )

            if batch:
                print(f"DEBUG: Found batch: {batch.label_code}, status: {batch.status}")

            return batch

        except Exception as e:
            print(f"DEBUG: Error in get_batch_by_identifier: {str(e)}")
            logger.error(
                f"Error getting batch by identifier {batch_identifier}: {str(e)}"
            )
            return None

    @classmethod
    def get_batches_with_filters(
        cls,
        status=None,
        recipe_id=None,
        start_date=None,
        end_date=None,
        sort_by="date_desc",
    ):
        """Get filtered and sorted batches"""
        try:
            # Build base query with organization scoping
            base_query = Batch.scoped()

            # Apply filters
            if status and status != "all":
                base_query = base_query.filter_by(status=status)
            if recipe_id:
                base_query = base_query.filter_by(recipe_id=recipe_id)
            if start_date:
                base_query = base_query.filter(Batch.started_at >= start_date)
            if end_date:
                base_query = base_query.filter(Batch.started_at <= end_date)

            # Apply sorting
            if sort_by == "date_asc":
                base_query = base_query.order_by(Batch.started_at.asc())
            elif sort_by == "date_desc":
                base_query = base_query.order_by(Batch.started_at.desc())
            elif sort_by == "recipe_asc":
                base_query = base_query.join(Recipe).order_by(Recipe.name.asc())
            elif sort_by == "recipe_desc":
                base_query = base_query.join(Recipe).order_by(Recipe.name.desc())
            elif sort_by == "status_asc":
                base_query = base_query.order_by(Batch.status.asc())
            else:
                base_query = base_query.order_by(Batch.started_at.desc())

            return base_query

        except Exception as e:
            logger.error(f"Error getting filtered batches: {str(e)}")
            raise

    @classmethod
    def get_paginated_batches(
        cls, status_filter, per_page=10, page=1, sort_by="date_desc"
    ):
        """Get paginated batches for a specific status"""
        try:
            query = cls.get_batches_with_filters(status=status_filter, sort_by=sort_by)
            return query.paginate(page=page, per_page=per_page, error_out=False)
        except Exception as e:
            logger.error(f"Error getting paginated batches: {str(e)}")
            raise

    @classmethod
    def get_adjacent_batches(cls, batch, status=None):
        """Get previous and next batches for navigation"""
        try:
            target_status = status or batch.status

            prev_batch = (
                Batch.scoped()
                .filter(Batch.status == target_status, Batch.id < batch.id)
                .order_by(Batch.id.desc())
                .first()
            )

            next_batch = (
                Batch.scoped()
                .filter(Batch.status == target_status, Batch.id > batch.id)
                .order_by(Batch.id.asc())
                .first()
            )

            return prev_batch, next_batch

        except Exception as e:
            logger.error(f"Error getting adjacent batches: {str(e)}")
            return None, None

    @classmethod
    def calculate_batch_costs(cls, batches):
        """Calculate total costs for a list of batches"""
        try:
            for batch in batches:
                ingredient_total = sum(
                    (ing.quantity_used or 0) * (ing.cost_per_unit or 0)
                    for ing in batch.batch_ingredients
                )
                container_total = sum(
                    (c.quantity_used or 0) * (c.cost_each or 0)
                    for c in batch.containers
                )
                # Consumables
                try:
                    consumable_total = sum(
                        (c.quantity_used or 0) * (c.cost_per_unit or 0)
                        for c in getattr(batch, "consumables", []) or []
                    )
                except Exception:
                    consumable_total = 0

                # Extras
                extra_ingredient_total = sum(
                    (e.quantity_used or 0) * (e.cost_per_unit or 0)
                    for e in batch.extra_ingredients
                )
                extra_container_total = sum(
                    (e.quantity_used or 0) * (e.cost_each or 0)
                    for e in batch.extra_containers
                )
                try:
                    extra_consumable_total = sum(
                        (e.quantity_used or 0) * (e.cost_per_unit or 0)
                        for e in getattr(batch, "extra_consumables", []) or []
                    )
                except Exception:
                    extra_consumable_total = 0

                total_cost = (
                    ingredient_total
                    + container_total
                    + consumable_total
                    + extra_ingredient_total
                    + extra_container_total
                    + extra_consumable_total
                )
                # Avoid persisting recalculated cost on read paths.
                set_committed_value(batch, "total_cost", total_cost)

            return batches

        except Exception as e:
            logger.error(f"Error calculating batch costs: {str(e)}")
            raise

    @classmethod
    def update_batch_notes_and_tags(cls, batch_id, notes=None, tags=None):
        """Update batch notes and tags"""
        try:
            batch = Batch.scoped().filter_by(id=batch_id).first()
            if not batch:
                return False, "Batch not found"

            # Validate ownership
            if (
                batch.created_by != current_user.id
                and batch.organization_id != current_user.organization_id
            ):
                return False, "Permission denied"

            # Update fields
            if notes is not None:
                batch.notes = notes
            if tags is not None:
                batch.tags = tags

            db.session.commit()
            return True, "Batch updated successfully"

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating batch notes/tags: {str(e)}")
            return False, str(e)

    @classmethod
    def get_batch_remaining_details(cls, batch_id):
        """Get detailed remaining inventory for a specific batch"""
        try:
            batch = db.session.get(Batch, batch_id)
            if not batch:
                return None, "Batch not found"

            # For now, return empty data - this can be expanded when ProductInventory is implemented
            remaining_data = []

            return {
                "success": True,
                "batch_label": batch.label_code,
                "remaining_items": remaining_data,
            }, None

        except Exception as e:
            logger.error(f"Error getting batch remaining details: {str(e)}")
            return None, str(e)

    @classmethod
    def get_batch_timers(cls, batch_id):
        """Get timers for a batch with proper organization scoping"""
        try:
            batch = Batch.scoped().filter_by(id=batch_id).first()
            if not batch:
                return [], False

            # Query timers - match batch organization
            timers = BatchTimer.query.filter_by(
                batch_id=batch.id, organization_id=batch.organization_id
            ).all()

            # Check for active timers
            has_active_timers = any(timer.status == "active" for timer in timers)

            logger.info(f"Found {len(timers)} timers for batch {batch.id}")
            return timers, has_active_timers

        except Exception as e:
            logger.error(f"Error getting batch timers: {str(e)}")
            return [], False

    @classmethod
    def validate_batch_access(cls, batch, operation="view"):
        """Validate user access to batch operations"""
        try:
            if not batch:
                return False, "Batch not found"

            # Check organization access
            if batch.organization_id != current_user.organization_id:
                return False, "Access denied - wrong organization"

            # For edit operations, check creator or organization ownership
            if operation in ["edit", "cancel", "complete"]:
                if (
                    batch.created_by != current_user.id
                    and batch.organization_id != current_user.organization_id
                ):
                    return False, "Permission denied - not batch creator"

            # For in-progress operations, ensure batch is still in progress
            if operation == "edit" and batch.status != "in_progress":
                return False, "Batch is no longer in progress"

            return True, None

        except Exception as e:
            logger.error(f"Error validating batch access: {str(e)}")
            return False, str(e)

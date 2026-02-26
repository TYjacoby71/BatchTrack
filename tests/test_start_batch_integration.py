"""Integration tests for starting batches.

Synopsis:
Ensures batch creation uses plan snapshots and lineage IDs.

Glossary:
- Plan snapshot: Immutable plan payload used to start a batch.
- Lineage ID: Recipe version identifier stored on batch.
"""

from flask_login import login_user

from app.extensions import db
from app.models.models import Organization, User
from app.models.recipe import Recipe
from app.services.batch_service.batch_operations import BatchOperationsService
from app.services.production_planning.service import PlanProductionService
from app.utils.timezone_utils import TimezoneUtils


def test_start_batch_uses_generator_and_persists_label(app):
    with app.app_context():
        current_year = TimezoneUtils.utc_now().year

        # Create org and user to satisfy current_user requirements
        org = Organization(name="OrgX")
        db.session.add(org)
        db.session.flush()

        user = User(
            email="user@x.com",
            username="userx",
            organization_id=org.id,
            is_verified=True,
        )
        db.session.add(user)
        db.session.commit()

        # Perform login and start_batch within the same request context
        with app.test_request_context("/"):
            login_user(user)

            # Create recipe with prefix
            recipe = Recipe(
                name="Soap",
                label_prefix="SOAP",
                predicted_yield=10.0,
                predicted_yield_unit="oz",
                created_by=user.id,
                organization_id=org.id,
            )
            db.session.add(recipe)
            db.session.commit()
            recipe_id = recipe.id

            snapshot = PlanProductionService.build_plan(
                recipe=recipe,
                scale=1.0,
                batch_type="ingredient",
                notes="test",
                containers=[],
            )
            batch, errors = BatchOperationsService.start_batch(snapshot.to_dict())
            batch_id = batch.id if batch else None

        assert errors == []
        assert batch_id is not None
        from app.models import Batch

        fresh_batch = db.session.get(Batch, batch_id)
        assert fresh_batch is not None
        assert fresh_batch.label_code.startswith(f"SOAP1-{current_year}-")
        assert fresh_batch.label_code.endswith("001")
        assert fresh_batch.recipe_id == recipe_id
        assert fresh_batch.lineage_id is not None
        assert fresh_batch.batch_type == "ingredient"

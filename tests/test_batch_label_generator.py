"""Tests for batch label generation.

Synopsis:
Validates batch label format and batch sequence usage.

Glossary:
- Batch label: Human-readable identifier for a batch.
- Sequence: Global counter for batch labels.
"""

from app.utils.code_generator import generate_batch_label_code
from app.services.lineage_service import generate_group_prefix
from app.models.recipe import Recipe
from app.models.batch import BatchSequence
from app.extensions import db
from app.utils.timezone_utils import TimezoneUtils
from app.models.models import Organization


def test_generate_batch_label_code_defaults(app):
    with app.app_context():
        current_year = TimezoneUtils.utc_now().year
        org = Organization.query.first()
        if not org:
            org = Organization(name="Label Test Org")
            db.session.add(org)
            db.session.flush()

        recipe = Recipe(
            name="Test",
            predicted_yield=1.0,
            predicted_yield_unit="oz",
            organization_id=org.id if org else None,
        )
        db.session.add(recipe)
        db.session.commit()

        code = generate_batch_label_code(recipe)
        prefix = generate_group_prefix("Test", org.id if org else None)
        assert code == f"{prefix}1-{current_year}-001"


def test_generate_batch_label_code_with_prefix_and_sequence(app):
    with app.app_context():
        current_year = TimezoneUtils.utc_now().year
        org = Organization.query.first()
        if not org:
            org = Organization(name="Label Seq Org")
            db.session.add(org)
            db.session.flush()

        recipe = Recipe(
            name="Soap",
            label_prefix="soap",
            predicted_yield=1.0,
            predicted_yield_unit="oz",
            organization_id=org.id if org else None,
        )
        db.session.add(recipe)
        db.session.flush()

        # Seed the org-year counter to simulate existing batches
        counter = BatchSequence(
            organization_id=org.id if org else None,
            year=current_year,
            current_sequence=2,
        )
        db.session.add(counter)
        db.session.commit()

        code = generate_batch_label_code(recipe)
        assert code == f"SOAP1-{current_year}-003"


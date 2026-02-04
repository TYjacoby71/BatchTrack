from app.utils.code_generator import generate_batch_label_code
from app.models.recipe import Recipe
from app.models import Organization
from app.extensions import db
from app.utils.timezone_utils import TimezoneUtils


def test_generate_batch_label_code_defaults(app):
    with app.app_context():
        current_year = TimezoneUtils.utc_now().year
        org = Organization(name="Label Org A")
        db.session.add(org)
        db.session.flush()

        recipe = Recipe(name="Test", predicted_yield=1.0, predicted_yield_unit="oz", organization_id=org.id)
        db.session.add(recipe)
        db.session.commit()

        code = generate_batch_label_code(recipe)
        assert code.startswith(f"TEST-{current_year}-")
        assert code.endswith("001")


def test_generate_batch_label_code_with_prefix_and_sequence(app):
    with app.app_context():
        current_year = TimezoneUtils.utc_now().year
        org = Organization(name="Label Org B")
        db.session.add(org)
        db.session.flush()

        recipe = Recipe(name="Soap", label_prefix="soap", predicted_yield=1.0, predicted_yield_unit="oz", organization_id=org.id)
        db.session.add(recipe)
        db.session.flush()

        # Generate twice to advance counter
        first = generate_batch_label_code(recipe)
        second = generate_batch_label_code(recipe)
        third = generate_batch_label_code(recipe)
        assert first == f"SOAP-{current_year}-001"
        assert second == f"SOAP-{current_year}-002"
        assert third == f"SOAP-{current_year}-003"


from app.utils.code_generator import generate_batch_label_code
from app.models.recipe import Recipe
from app.models.batch import Batch
from app.extensions import db
from app.utils.timezone_utils import TimezoneUtils


def test_generate_batch_label_code_defaults(app):
    with app.app_context():
        current_year = TimezoneUtils.utc_now().year

        recipe = Recipe(name="Test", predicted_yield=1.0, predicted_yield_unit="oz")
        db.session.add(recipe)
        db.session.commit()

        code = generate_batch_label_code(recipe)
        # Default prefix derives from recipe name
        assert code.startswith(f"TEST-{current_year}-")
        assert code.endswith("001")


def test_generate_batch_label_code_with_prefix_and_sequence(app):
    with app.app_context():
        current_year = TimezoneUtils.utc_now().year

        recipe = Recipe(name="Soap", label_prefix="soap", predicted_yield=1.0, predicted_yield_unit="oz")
        db.session.add(recipe)
        db.session.flush()

        # Create two batches to simulate existing ones this year
        b1 = Batch(recipe_id=recipe.id, label_code=f"SOAP-{current_year}-001", batch_type='ingredient')
        b2 = Batch(recipe_id=recipe.id, label_code=f"SOAP-{current_year}-002", batch_type='ingredient')
        b1.started_at = TimezoneUtils.utc_now()
        b2.started_at = TimezoneUtils.utc_now()
        db.session.add_all([b1, b2])
        db.session.commit()

        code = generate_batch_label_code(recipe)
        assert code == f"SOAP-{current_year}-003"


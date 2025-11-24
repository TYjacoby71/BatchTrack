import pytest


def test_auto_fill_containers_uses_available_capacity(app, db_session):
    from app.models import Recipe, InventoryItem, Unit, Organization, ProductCategory
    from app.services.production_planning._container_management import analyze_container_options

    with app.app_context():
        org = Organization.query.first()
        if not org:
            org = Organization(name='Auto Fill Org')
            db_session.add(org)
            db_session.flush()

        category = ProductCategory.query.first()
        if not category:
            category = ProductCategory(name='Auto Fill Category')
            db_session.add(category)
            db_session.flush()

        def ensure_unit(name: str, unit_type: str):
            unit = Unit.query.filter_by(name=name).first()
            if not unit:
                unit = Unit(
                    name=name,
                    symbol=name,
                    unit_type=unit_type,
                    conversion_factor=1.0,
                    base_unit=name,
                    is_active=True,
                    is_custom=False
                )
                db_session.add(unit)
                db_session.flush()
            return unit

        ensure_unit('fl oz', 'volume')
        ensure_unit('count', 'count')

        recipe = Recipe(
            name='Auto Fill Test Recipe',
            predicted_yield=12.0,
            predicted_yield_unit='fl oz',
            category_id=category.id,
            organization_id=org.id
        )
        db_session.add(recipe)
        db_session.flush()

        container = InventoryItem(
            name='4 fl oz Jar',
            type='container',
            organization_id=org.id,
            quantity=10,
            unit='count',
            capacity=4.0,
            capacity_unit='fl oz'
        )
        db_session.add(container)
        db_session.flush()

        recipe.allowed_containers = [container.id]
        db_session.commit()

        strategy, container_options = analyze_container_options(
            recipe=recipe,
            scale=1.0,
            organization_id=org.id,
            api_format=False
        )

        assert strategy is not None, "Strategy should be generated for matching container units"
        selection = strategy.get('container_selection') or []
        assert len(selection) == 1, "Expected one container selection"
        assert selection[0]['container_id'] == container.id
        assert selection[0]['containers_needed'] == 3, "12 fl oz yield should use three 4 fl oz containers"
        assert pytest.approx(selection[0]['capacity'], rel=1e-5) == 4.0
        assert strategy.get('containment_percentage') == 100.0

import pytest
from flask_login import login_user
from app.models import InventoryItem
from app.services.inventory_adjustment import process_inventory_adjustment


@pytest.mark.usefixtures("app", "db_session", "test_user", "test_org")
class TestInventoryCostingToggleAndWAC:
    def test_wac_updates_after_restock_and_deduct_fifo_mode(self, app, db_session, test_user, test_org):
        with app.test_request_context():
            # Ensure org is in FIFO mode
            test_org.inventory_cost_method = 'fifo'
            db_session.add(test_org)

            login_user(test_user)

            # Create an ingredient
            item = InventoryItem(
                name="Olive Oil",
                type="ingredient",
                unit="ml",
                quantity=0.0,
                organization_id=test_org.id,
                created_by=test_user.id,
                cost_per_unit=0.0
            )
            db_session.add(item)
            db_session.flush()

            # Restock 100 ml at $1.00
            ok, _ = process_inventory_adjustment(
                item_id=item.id,
                quantity=100.0,
                change_type="restock",
                notes="restock 1",
                created_by=test_user.id,
                unit=item.unit,
                # per-unit cost
                cost_override=1.0
            )
            assert ok is True

            # Restock another 100 ml at $3.00 (different cost layer)
            ok, _ = process_inventory_adjustment(
                item_id=item.id,
                quantity=100.0,
                change_type="restock",
                notes="restock 2",
                created_by=test_user.id,
                unit=item.unit,
                cost_override=3.0
            )
            assert ok is True

            db_session.commit()

            # After two lots: WAC should be (100*1 + 100*3) / 200 = 2.0
            fresh_item = db_session.get(InventoryItem, item.id)
            assert pytest.approx(fresh_item.cost_per_unit, rel=1e-9) == 2.0

            # Deduct 50 ml (FIFO uses cheapest first lot's unit_cost for event, but WAC remains weighted by remaining lots)
            ok, _ = process_inventory_adjustment(
                item_id=item.id,
                quantity=-50.0,
                change_type="use",
                notes="deduct 50",
                created_by=test_user.id,
                unit=item.unit
            )
            assert ok is True

            db_session.commit()

            # Remaining quantities: 50 ml from $1 lot and 100 ml from $3 lot => total 150
            # New WAC = (50*1 + 100*3) / 150 = (50 + 300) / 150 = 350/150 ≈ 2.333333...
            fresh_item = db_session.get(InventoryItem, item.id)
            assert pytest.approx(fresh_item.cost_per_unit, rel=1e-9) == pytest.approx(350.0 / 150.0, rel=1e-9)

    def test_wac_updates_after_restock_average_mode(self, app, db_session, test_user, test_org):
        with app.test_request_context():
            # Switch org to Average mode
            test_org.inventory_cost_method = 'average'
            db_session.add(test_org)

            login_user(test_user)

            # Create an ingredient
            item = InventoryItem(
                name="Sugar",
                type="ingredient",
                unit="g",
                quantity=0.0,
                organization_id=test_org.id,
                created_by=test_user.id,
                cost_per_unit=0.0
            )
            db_session.add(item)
            db_session.flush()

            # Restock 10 g at total $1.00 (use total cost style: set cost_override to per-unit here = 0.1)
            ok, _ = process_inventory_adjustment(
                item_id=item.id,
                quantity=10.0,
                change_type="restock",
                notes="restock 1",
                created_by=test_user.id,
                unit=item.unit,
                cost_override=0.1
            )
            assert ok is True

            # Restock 30 g at $0.2 per g
            ok, _ = process_inventory_adjustment(
                item_id=item.id,
                quantity=30.0,
                change_type="restock",
                notes="restock 2",
                created_by=test_user.id,
                unit=item.unit,
                cost_override=0.2
            )
            assert ok is True

            db_session.commit()

            # WAC after two restocks: (10*0.1 + 30*0.2) / 40 = (1 + 6) / 40 = 0.175
            fresh_item = db_session.get(InventoryItem, item.id)
            assert pytest.approx(fresh_item.cost_per_unit, rel=1e-9) == 0.175


from datetime import timedelta, timezone

from flask_login import login_user

from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.inventory_lot import InventoryLot
from app.models.models import Organization, User
from app.services.event_emitter import EventEmitter
from app.services.stock_check.core import UniversalStockCheckService
from app.services.stock_check.types import InventoryCategory, StockStatus
from app.utils.timezone_utils import TimezoneUtils


def test_stock_check_perishable_lots_with_null_expiration_do_not_fail(app, monkeypatch):
    with app.app_context():
        org = Organization(name="Perishable Regression Org")
        db.session.add(org)
        db.session.flush()

        user = User(
            email="perishable-regression@example.com",
            username="perishable-regression-user",
            organization_id=org.id,
            is_verified=True,
        )
        db.session.add(user)
        db.session.flush()

        ingredient = InventoryItem(
            name="Lavender Oil",
            unit="g",
            quantity=0,
            quantity_base=0,
            organization_id=org.id,
            type="ingredient",
            is_perishable=True,
            is_tracked=True,
            density=1.0,
        )
        db.session.add(ingredient)
        db.session.flush()

        now_utc = TimezoneUtils.utc_now()
        lots = [
            InventoryLot(
                inventory_item_id=ingredient.id,
                remaining_quantity=30.0,
                original_quantity=30.0,
                remaining_quantity_base=30,
                original_quantity_base=30,
                unit="g",
                unit_cost=1.0,
                source_type="restock",
                organization_id=org.id,
                expiration_date=None,
            ),
            InventoryLot(
                inventory_item_id=ingredient.id,
                remaining_quantity=20.0,
                original_quantity=20.0,
                remaining_quantity_base=20,
                original_quantity_base=20,
                unit="g",
                unit_cost=1.0,
                source_type="restock",
                organization_id=org.id,
                expiration_date=now_utc + timedelta(days=3),
            ),
            InventoryLot(
                inventory_item_id=ingredient.id,
                remaining_quantity=999.0,
                original_quantity=999.0,
                remaining_quantity_base=999,
                original_quantity_base=999,
                unit="g",
                unit_cost=1.0,
                source_type="restock",
                organization_id=org.id,
                expiration_date=now_utc - timedelta(days=1),
            ),
        ]
        db.session.add_all(lots)
        db.session.commit()

        # Keep this focused on perishable-lot filtering instead of tier policy setup.
        monkeypatch.setattr(
            "app.services.stock_check.handlers.ingredient_handler.org_allows_inventory_quantity_tracking",
            lambda organization=None: True,
        )

        with app.test_request_context():
            login_user(user)
            result = UniversalStockCheckService().check_single_item(
                item_id=ingredient.id,
                quantity_needed=10.0,
                unit="g",
                category=InventoryCategory.INGREDIENT,
            )

        assert result.item_name == "Lavender Oil"
        assert result.status == StockStatus.OK
        assert result.available_quantity == 50.0
        assert result.error_message is None


def test_event_emitter_enrichment_handles_naive_first_login(monkeypatch):
    naive_first_login = TimezoneUtils.utc_now().replace(tzinfo=None) - timedelta(
        minutes=5
    )
    occurred_at = TimezoneUtils.utc_now().astimezone(timezone.utc)

    monkeypatch.setattr(
        EventEmitter,
        "_safe_event_count",
        lambda **kwargs: (0, 0),
    )
    monkeypatch.setattr(
        EventEmitter,
        "_first_login_at",
        lambda user_id: naive_first_login,
    )

    enriched = EventEmitter._enrich_usage_properties(
        event_name="stock_check_run",
        user_id=42,
        org_id=99,
        properties={},
        occurred_at=occurred_at,
    )

    assert enriched["seconds_since_first_login"] >= 299
    assert enriched["first_login_observed_at"].endswith("+00:00")

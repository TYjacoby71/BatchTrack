from app.extensions import db
from app.models import GlobalItem, InventoryItem
from app.services.inventory_search import InventorySearchService


def _seed_inventory_item(org_id: int, name: str) -> InventoryItem:
    item = InventoryItem(
        name=name,
        organization_id=org_id,
        unit="gram",
        quantity=5,
        type="ingredient",
    )
    db.session.add(item)
    db.session.commit()
    return item


def _seed_global_item(name: str) -> GlobalItem:
    item = GlobalItem(name=name, item_type="ingredient", default_unit="oz")
    db.session.add(item)
    db.session.commit()
    return item


def test_inventory_search_scoped_to_local_items_for_negative_changes(app, test_user):
    with app.app_context():
        _seed_inventory_item(test_user.organization_id, "Local Shea Butter")
        _seed_global_item("Global Shea Butter")

        results = InventorySearchService.search_inventory_items(
            query_text="Shea",
            inventory_type=None,
            organization_id=test_user.organization_id,
            change_type="spoil",
            limit=5,
        )

        assert results
        assert all(entry["source"] == "inventory" for entry in results)


def test_inventory_search_includes_global_items_for_create(app, test_user):
    with app.app_context():
        _seed_inventory_item(test_user.organization_id, "Local Beeswax")
        _seed_global_item("Global Beeswax")

        results = InventorySearchService.search_inventory_items(
            query_text="Beeswax",
            inventory_type=None,
            organization_id=test_user.organization_id,
            change_type="create",
            limit=10,
        )

        assert any(entry["source"] == "inventory" for entry in results)
        assert any(entry["source"] == "global" for entry in results)

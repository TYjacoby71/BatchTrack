from types import SimpleNamespace

from app.services.recipe_marketplace_service import RecipeMarketplaceService


def test_default_payload_private():
    form = {}
    ok, payload = RecipeMarketplaceService.extract_submission(form, {})
    assert ok
    marketplace = payload["marketplace"]
    assert marketplace["sharing_scope"] == "private"
    assert marketplace["is_public"] is False
    assert marketplace["is_for_sale"] is False
    assert marketplace["sale_price"] is None


def test_public_sale_payload():
    form = {
        "sharing_scope": "public",
        "sale_mode": "sale",
        "sale_price": "19.99",
        "product_group_id": "3",
        "product_store_url": "https://example.com/product/soap",
        "skin_opt_in": "true",
        "marketplace_notes": "Includes premium SKIN data",
        "public_description": "This is a high-level teaser",
    }
    ok, payload = RecipeMarketplaceService.extract_submission(form, {})
    assert ok
    marketplace = payload["marketplace"]
    assert marketplace["is_public"] is True
    assert marketplace["is_for_sale"] is True
    assert marketplace["sale_price"] == "19.99"
    assert marketplace["product_group_id"] == 3
    assert marketplace["product_store_url"] == "https://example.com/product/soap"
    assert marketplace["skin_opt_in"] is True
    assert marketplace["public_description"] == "This is a high-level teaser"


def test_existing_recipe_defaults_when_fields_missing():
    existing = SimpleNamespace(
        sharing_scope="public",
        is_public=True,
        is_for_sale=True,
        sale_price="12.00",
        product_group_id=7,
        product_store_url="https://existing/link",
        marketplace_notes="Legacy note",
        public_description="Legacy description",
        skin_opt_in=False,
    )
    form = {}
    ok, payload = RecipeMarketplaceService.extract_submission(form, {}, existing=existing)
    assert ok
    marketplace = payload["marketplace"]
    assert marketplace["is_public"] is True
    assert marketplace["is_for_sale"] is True
    assert marketplace["sale_price"] == "12.00"
    assert marketplace["product_group_id"] == 7
    assert marketplace["product_store_url"] == "https://existing/link"
    assert marketplace["marketplace_notes"] == "Legacy note"
    assert marketplace["skin_opt_in"] is False
    assert marketplace["public_description"] == "Legacy description"

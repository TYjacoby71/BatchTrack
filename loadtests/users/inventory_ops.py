"""Inventory browsing and ingredient lookup load tests."""

import random

from locust import task, between

from loadtests.common import (
    BaseAuthenticatedUser,
    GLOBAL_ITEM_SEARCH_TERMS,
    LOCUST_DASHBOARD_PATH,
    LOCUST_ENABLE_BROWSE_USERS,
)


class InventoryOpsUser(BaseAuthenticatedUser):
    """Inventory browsing + ingredient lookup."""

    abstract = not LOCUST_ENABLE_BROWSE_USERS
    wait_time = between(6, 14)
    weight = 3

    @task(6)
    def view_inventory_list(self):
        self._authed_get("/inventory/", name="inventory_list")

    @task(5)
    def search_inventory(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        params = {"q": query, "type": "ingredient"}
        self._authed_get(
            "/inventory/api/search",
            params=params,
            name="inventory_search",
        )

    @task(3)
    def view_inventory_item(self):
        item_id = self._pick_id(self._get_ingredient_ids())
        if not item_id:
            return
        self._authed_get(
            f"/api/inventory/item/{item_id}",
            name="inventory_item_detail",
        )

    @task(3)
    def ingredient_categories(self):
        self._authed_get("/api/ingredients/categories", name="ingredient_categories")

    @task(2)
    def ingredient_definition_search(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        self._authed_get(
            "/api/ingredients/ingredients/search",
            params={"q": query},
            name="ingredient_definition_search",
        )

    @task(2)
    def refresh_ingredient_list(self):
        self._authed_get("/api/ingredients", name="ingredients_list")

    @task(1)
    def unit_converter(self):
        payload = {
            "from_amount": 1000,
            "from_unit": "g",
            "to_unit": "kg",
        }
        ingredient_id = self._pick_id(self._get_ingredient_ids())
        if ingredient_id:
            payload["ingredient_id"] = ingredient_id
        headers = self._csrf_headers(referer_path=LOCUST_DASHBOARD_PATH)
        self._authed_post("/api/unit-converter", json=payload, headers=headers, name="unit_converter")

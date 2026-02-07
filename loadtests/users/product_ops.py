"""Product inventory and SKU management load tests."""

import random

from locust import task, between

from loadtests.common import (
    BaseAuthenticatedUser,
    GLOBAL_ITEM_SEARCH_TERMS,
    LOCUST_ENABLE_BROWSE_USERS,
)


class ProductOpsUser(BaseAuthenticatedUser):
    """Product inventory + SKU management."""

    abstract = not LOCUST_ENABLE_BROWSE_USERS
    wait_time = between(6, 14)
    weight = 2

    @task(6)
    def view_products_list(self):
        self._authed_get("/products/", name="products_list")

    @task(4)
    def view_product_detail(self):
        product_id = self._pick_id(self._get_product_ids())
        if not product_id:
            return
        self._authed_get(f"/products/{product_id}", name="product_detail")

    @task(3)
    def search_products(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        self._authed_get(
            "/api/products/search",
            params={"q": query},
            name="product_search",
        )

    @task(2)
    def low_stock_summary(self):
        self._authed_get(
            "/api/products/low-stock",
            params={"threshold": 1.0},
            name="product_low_stock",
        )

    @task(2)
    def product_alerts(self):
        self._authed_get("/products/alerts", name="product_alerts")

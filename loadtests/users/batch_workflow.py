"""Batch workflow load tests (start, cancel, fail, complete)."""

import random
import re
import time

from locust import SequentialTaskSet, task, between
from locust.exception import StopUser

from loadtests.common import (
    LOGGER,
    GLOBAL_ITEM_SEARCH_TERMS,
    LOCUST_DASHBOARD_PATH,
    LOCUST_ENABLE_BROWSE_USERS,
    BaseAuthenticatedUser,
)


class BatchWorkflowSequence(SequentialTaskSet):
    def on_start(self):
        self.milk_item_id = None
        self.custom_item_id = None
        self.recipe_id = None
        self._suffix = f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
        self._milk_item_name = f"Milk (Locust {self._suffix})"
        self._custom_item_name = f"Custom Pickle {self._suffix}"
        self._recipe_name = f"Locust Milk Pickle Recipe {self._suffix}"
        self._milk_unit = "gallon"
        self._pickle_unit = "count"

    def _authed_get(self, path: str, **kwargs):
        return self.user._authed_get(path, **kwargs)

    def _authed_post(self, path: str, **kwargs):
        return self.user._authed_post(path, **kwargs)

    def _require(self, value, label):
        if value:
            return value
        LOGGER.warning("Locust batch workflow missing %s", label)
        raise StopUser()

    def _restock_item(self, item_id: int, unit: str, name: str) -> None:
        token = self.user._ensure_csrf_token("/inventory/")
        data = {
            "change_type": "restock",
            "quantity": "10",
            "input_unit": unit,
            "notes": "Locust restock",
        }
        if token:
            data["csrf_token"] = token
        headers = self.user._csrf_headers(referer_path="/inventory/")
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Accept"] = "application/json"
        response = self._authed_post(
            f"/inventory/adjust/{item_id}",
            data=data,
            headers=headers,
            name=name,
        )
        if response is None:
            raise StopUser()
        payload = self.user._safe_json(response)
        if response.status_code >= 400 or (payload and not payload.get("success", True)):
            LOGGER.warning("Locust restock failed (%s): %s", name, payload or response.text)
            raise StopUser()

    def _start_batch(self, request_name: str) -> int:
        payload = {
            "recipe_id": self.recipe_id,
            "scale": 1.0,
            "batch_type": "ingredient",
            "notes": "Locust batch workflow",
            "force_start": False,
        }
        headers = self.user._csrf_headers(referer_path="/batches/")
        response = self._authed_post(
            "/batches/api/start-batch",
            json=payload,
            headers=headers,
            name=request_name,
        )
        if response is None:
            raise StopUser()
        data = self.user._safe_json(response)
        if data and data.get("success") and data.get("batch_id"):
            return int(data["batch_id"])
        LOGGER.warning("Batch start failed: %s", data or response.text)
        raise StopUser()

    @task
    def browse_public_pages(self):
        self.client.get("/", name="homepage")
        self.client.get("/tools/", name="tools_index")
        self.client.get("/global-items", name="global_items")
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        self.client.get(
            "/api/public/global-items/search",
            params={"q": query, "type": "ingredient", "group": "ingredient"},
            name="public_global_item_search",
        )
        self.client.get("/auth/signup", name="signup_page")
        self.client.get("/api/public/units", name="public_units")

    @task
    def browse_authenticated_pages(self):
        self._authed_get(LOCUST_DASHBOARD_PATH, name="user_dashboard")
        self._authed_get("/recipes/", name="recipes_list")
        self._authed_get("/batches/", name="batches_list")
        self._authed_get("/inventory/", name="inventory_list")
        self._authed_get("/products/", name="products_list")
        self._authed_get("/global-items", name="global_items")

    @task
    def fetch_bootstrap_endpoints(self):
        self._authed_get("/api/bootstrap/recipes", name="bootstrap_recipes")
        self._authed_get("/api/bootstrap/products", name="bootstrap_products")

    @task
    def browse_search_endpoints(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        self._authed_get(
            "/api/ingredients/global-items/search",
            params={"q": query, "type": "ingredient", "group": "ingredient"},
            name="auth_global_item_search",
        )
        self._authed_get(
            "/inventory/api/search",
            params={"q": query, "type": "ingredient"},
            name="inventory_search",
        )
        self._authed_get("/api/ingredients/categories", name="ingredient_categories")
        self._authed_get(
            "/api/ingredients/ingredients/search",
            params={"q": query},
            name="ingredient_definition_search",
        )
        self._authed_get("/api/ingredients", name="ingredients_list")
        self._authed_get(
            "/api/products/search",
            params={"q": query},
            name="product_search",
        )
        self._authed_get(
            "/api/products/low-stock",
            params={"threshold": 1.0},
            name="product_low_stock",
        )
        self._authed_get("/products/alerts", name="product_alerts")

    @task
    def browse_detail_endpoints(self):
        recipe_ids = self.user._get_recipe_ids()
        product_ids = self.user._get_product_ids()
        ingredient_ids = self.user._get_ingredient_ids()

        recipe_id = self.user._pick_id(recipe_ids)
        if recipe_id:
            self._authed_get(f"/recipes/{recipe_id}/view", name="recipe_detail")
            self._authed_get(
                f"/batches/api/available-ingredients/{recipe_id}",
                name="batch_available_ingredients",
            )

        product_id = self.user._pick_id(product_ids)
        if product_id:
            self._authed_get(f"/products/{product_id}", name="product_detail")

        ingredient_id = self.user._pick_id(ingredient_ids)
        if ingredient_id:
            self._authed_get(
                f"/api/inventory/item/{ingredient_id}",
                name="inventory_item_detail",
            )

    @task
    def unit_converter(self):
        payload = {
            "from_amount": 1000,
            "from_unit": "g",
            "to_unit": "kg",
        }
        ingredient_id = self.user._pick_id(self.user._get_ingredient_ids())
        if ingredient_id:
            payload["ingredient_id"] = ingredient_id
        self.user._ensure_csrf_token(LOCUST_DASHBOARD_PATH)
        headers = self.user._csrf_headers(referer_path=LOCUST_DASHBOARD_PATH)
        self._authed_post("/api/unit-converter", json=payload, headers=headers, name="unit_converter")

    @task
    def create_custom_milk_inventory(self):
        payload = {
            "name": self._milk_item_name,
            "type": "ingredient",
            "unit": self._milk_unit,
        }
        headers = self.user._csrf_headers(referer_path="/inventory/")
        response = self._authed_post(
            "/api/ingredients/ingredients/create-or-link",
            json=payload,
            headers=headers,
            name="create_custom_milk_inventory",
        )
        if response is None:
            raise StopUser()
        data = self.user._safe_json(response)
        item = (data or {}).get("item") if isinstance(data, dict) else None
        self.milk_item_id = item.get("id") if isinstance(item, dict) else None
        self._require(self.milk_item_id, "milk inventory item id")

    @task
    def create_custom_pickle_inventory(self):
        payload = {
            "name": self._custom_item_name,
            "type": "ingredient",
            "unit": self._pickle_unit,
        }
        headers = self.user._csrf_headers(referer_path="/inventory/")
        response = self._authed_post(
            "/api/ingredients/ingredients/create-or-link",
            json=payload,
            headers=headers,
            name="create_custom_pickle_inventory",
        )
        if response is None:
            raise StopUser()
        data = self.user._safe_json(response)
        item = (data or {}).get("item") if isinstance(data, dict) else None
        self.custom_item_id = item.get("id") if isinstance(item, dict) else None
        self._require(self.custom_item_id, "custom pickle item id")

    @task
    def restock_milk_and_pickle(self):
        self._require(self.milk_item_id, "milk inventory item id")
        self._require(self.custom_item_id, "custom pickle item id")
        self._restock_item(self.milk_item_id, self._milk_unit, "restock_custom_milk")
        self._restock_item(self.custom_item_id, self._pickle_unit, "restock_custom_pickle")

    @task
    def create_recipe(self):
        self._require(self.milk_item_id, "milk inventory item id")
        self._require(self.custom_item_id, "custom pickle item id")
        token = self.user._ensure_csrf_token("/recipes/new")
        form_data = [
            ("csrf_token", token or ""),
            ("name", self._recipe_name),
            ("instructions", "Locust recipe using milk + custom pickle"),
            ("predicted_yield", "1"),
            ("predicted_yield_unit", "count"),
            ("ingredient_ids[]", str(self.custom_item_id)),
            ("ingredient_ids[]", str(self.milk_item_id)),
            ("global_item_ids[]", ""),
            ("global_item_ids[]", ""),
            ("amounts[]", "1"),
            ("amounts[]", "1"),
            ("units[]", self._pickle_unit),
            ("units[]", self._milk_unit),
        ]
        headers = self.user._csrf_headers(referer_path="/recipes/new")
        response = self._authed_post(
            "/recipes/new",
            data=form_data,
            headers=headers,
            allow_redirects=False,
            name="create_recipe",
        )
        if response is None:
            raise StopUser()
        if response.status_code >= 400:
            LOGGER.warning("Create recipe failed: %s", response.text)
            raise StopUser()
        location = response.headers.get("Location", "")
        if not location:
            LOGGER.warning("Create recipe missing redirect: %s", response.text)
            raise StopUser()
        match = re.search(r"/recipes/(\d+)", location)
        self.recipe_id = int(match.group(1)) if match else None
        self._require(self.recipe_id, "recipe id")

    @task
    def view_created_recipe(self):
        self._require(self.recipe_id, "recipe id")
        self._authed_get(f"/recipes/{self.recipe_id}/view", name="recipe_detail")
        self._authed_get(
            f"/batches/api/available-ingredients/{self.recipe_id}",
            name="batch_available_ingredients",
        )

    @task
    def start_and_cancel_batch(self):
        self._require(self.recipe_id, "recipe id")
        batch_id = self._start_batch("start_batch_for_cancel")
        token = self.user._ensure_csrf_token("/batches/")
        data = {"csrf_token": token} if token else {}
        headers = self.user._csrf_headers(referer_path=f"/batches/{batch_id}")
        response = self._authed_post(
            f"/batches/cancel/{batch_id}",
            data=data,
            headers=headers,
            allow_redirects=False,
            name="cancel_batch",
        )
        if response is None:
            raise StopUser()
        if response.status_code >= 400:
            LOGGER.warning("Cancel batch failed: %s", response.text)
            raise StopUser()

    @task
    def start_and_fail_batch(self):
        self._require(self.recipe_id, "recipe id")
        batch_id = self._start_batch("start_batch_for_fail")
        headers = self.user._csrf_headers(referer_path=f"/batches/in-progress/{batch_id}")
        response = self._authed_post(
            f"/batches/finish-batch/{batch_id}/fail",
            json={"reason": "Locust workflow failure"},
            headers=headers,
            name="fail_batch",
        )
        if response is None:
            raise StopUser()
        if response.status_code >= 400:
            LOGGER.warning("Fail batch failed: %s", response.text)
            raise StopUser()

    @task
    def start_and_complete_batch(self):
        self._require(self.recipe_id, "recipe id")
        batch_id = self._start_batch("start_batch_for_complete")
        token = self.user._ensure_csrf_token("/batches/")
        data = {
            "output_type": "ingredient",
            "final_quantity": "1",
            "output_unit": "count",
        }
        if token:
            data["csrf_token"] = token
        headers = self.user._csrf_headers(referer_path=f"/batches/in-progress/{batch_id}")
        response = self._authed_post(
            f"/batches/finish-batch/{batch_id}/complete",
            data=data,
            headers=headers,
            allow_redirects=False,
            name="complete_batch",
        )
        if response is None:
            raise StopUser()
        if response.status_code >= 400:
            LOGGER.warning("Complete batch failed: %s", response.text)
            raise StopUser()
        raise StopUser()


class BatchWorkflowUser(BaseAuthenticatedUser):
    wait_time = between(1, 3)
    tasks = [BatchWorkflowSequence]
    weight = 1

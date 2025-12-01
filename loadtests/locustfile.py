"""
Locust scenarios that exercise concurrent recipe planning, batch creation,
inventory adjustments, SKU updates, and public-library browsing with
per-user session isolation to avoid session guard collisions.
"""

import json
import os
import queue
import random
import re
import time
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from locust import HttpUser, between, task
from locust.exception import RescheduleTask


CACHE_TTL_SECONDS = int(os.getenv("LOCUST_CACHE_TTL", "120"))
DEFAULT_PASSWORD = os.getenv("LOCUST_USER_PASSWORD", "loadtest123")
DEFAULT_USERNAME_BASE = os.getenv("LOCUST_USER_BASE", "loadtest_user")
DEFAULT_USER_COUNT = int(os.getenv("LOCUST_USER_COUNT", "10000"))


def _load_credential_source() -> List[Dict[str, str]]:
    """Load credential definitions from env or fall back to sequential pattern."""
    raw = os.getenv("LOCUST_USER_CREDENTIALS")
    if raw:
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, list):
                credentials = [
                    creds for creds in loaded
                    if isinstance(creds, dict) and {"username", "password"} <= set(creds.keys())
                ]
                print(f"📋 Loaded {len(credentials)} credentials from LOCUST_USER_CREDENTIALS")
                return credentials
        except json.JSONDecodeError:
            print("❌ Failed to parse LOCUST_USER_CREDENTIALS JSON")

    # Fall back to sequential pattern
    credentials = [
        {"username": f"{DEFAULT_USERNAME_BASE}{i}", "password": DEFAULT_PASSWORD}
        for i in range(1, DEFAULT_USER_COUNT + 1)
    ]
    print(f"📋 Generated {len(credentials)} sequential credentials ({DEFAULT_USERNAME_BASE}1-{DEFAULT_USER_COUNT})")
    return credentials


class CredentialPool:
    """Queue-backed pool to guarantee one active session per test user."""

    def __init__(self):
        self._pool = queue.Queue()
        credentials = _load_credential_source()
        
        if not credentials:
            raise RuntimeError("❌ No credentials available! Run: python loadtests/test_user_generator.py create --count=10000")
            
        for creds in credentials:
            self._pool.put(creds)
        
        print(f"✅ Credential pool initialized with {len(credentials)} users")
        print(f"   Pattern: {credentials[0]['username']} ... {credentials[-1]['username']}")
        print(f"   Password: {credentials[0]['password']}")

    def acquire(self) -> Dict[str, str]:
        try:
            return self._pool.get(timeout=5)
        except queue.Empty as exc:  # pragma: no cover - defensive
            remaining_size = self._pool.qsize()
            raise RuntimeError(f"No available load-test users (pool size: {remaining_size}). You may need more test users or fewer concurrent Locust users.") from exc

    def release(self, creds: Optional[Dict[str, str]]) -> None:
        if creds:
            self._pool.put(creds)


CREDENTIAL_POOL = CredentialPool()


def _extract_csrf_token(html: str) -> Optional[str]:
    """Pull CSRF token from a login form or meta tag."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        field = soup.find("input", {"name": "csrf_token"})
        if field and field.get("value"):
            return field.get("value")
        meta = soup.find("meta", {"name": "csrf-token"})
        if meta and meta.get("content"):
            return meta.get("content")
    except Exception:
        return None
    return None


def _extract_ids(pattern: str, text: str) -> List[int]:
    """Helper to extract integer IDs from HTML snippets."""
    ids = set()
    for match in re.findall(pattern, text):
        try:
            ids.add(int(match))
        except ValueError:
            continue
    return sorted(ids)


class AuthenticatedMixin:
    """Reusable auth + caching helpers for stateful users."""

    credential: Optional[Dict[str, str]] = None
    recipe_ids: List[int]
    library_recipe_ids: List[int]
    inventory_item_ids: List[int]
    product_ids: List[int]
    sku_inventory_ids: List[int]
    _cache_refreshed_at: float

    def on_start(self):
        """Claim a test account, log in, and seed caches."""
        try:
            self.credential = CREDENTIAL_POOL.acquire()
            print(f"🔐 {self.__class__.__name__} acquired credential: {self.credential['username']}")
        except RuntimeError as exc:
            print(f"❌ {self.__class__.__name__} failed to acquire credential: {exc}")
            raise RescheduleTask(str(exc)) from exc

        try:
            self._login_with_credential()
            print(f"✅ {self.__class__.__name__} logged in successfully: {self.credential['username']}")
        except Exception as exc:
            print(f"❌ {self.__class__.__name__} login failed for {self.credential['username']}: {exc}")
            raise
            
        self.recipe_ids = []
        self.library_recipe_ids = []
        self.inventory_item_ids = []
        self.product_ids = []
        self.sku_inventory_ids = []
        self._cache_refreshed_at = 0.0
        self.ensure_domain_cache(force=True)

    def on_stop(self):
        """Release the credential so another simulated user can reuse it."""
        if self.credential:
            CREDENTIAL_POOL.release(self.credential)
            self.credential = None

    def _login_with_credential(self) -> None:
        """Execute the login form flow with CSRF handling."""
        login_page = self.client.get("/auth/login", name="auth.login.page")
        if login_page.status_code != 200:
            print(f"❌ Login page unavailable: {login_page.status_code}")
            raise RescheduleTask("Login page unavailable")

        token = _extract_csrf_token(login_page.text)
        payload = {
            "username": self.credential["username"],
            "password": self.credential["password"],
        }
        if token:
            payload["csrf_token"] = token

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "/auth/login",
        }

        response = self.client.post("/auth/login", data=payload, headers=headers, name="auth.login")
        if response.status_code not in (200, 302):
            print(f"❌ Login failed for {payload['username']}: status={response.status_code}, response={response.text[:200]}...")
            CREDENTIAL_POOL.release(self.credential)
            self.credential = None
            raise RescheduleTask(f"Login failed for {payload['username']}: {response.status_code}")
        else:
            print(f"✅ Login successful for {payload['username']}: status={response.status_code}")

    # -----------------------
    # Cached ID lookups
    # -----------------------
    def ensure_domain_cache(self, *, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self._cache_refreshed_at) < CACHE_TTL_SECONDS:
            return

        self.recipe_ids = self._fetch_recipe_ids()
        self.library_recipe_ids = self._fetch_recipe_library_ids()
        self.inventory_item_ids = self._fetch_inventory_item_ids()
        self.product_ids, self.sku_inventory_ids = self._fetch_product_and_sku_ids()
        self._cache_refreshed_at = now

    def _fetch_recipe_ids(self) -> List[int]:
        resp = self.client.get("/recipes", name="bootstrap.recipes", allow_redirects=True)
        return _extract_ids(r"/recipes/(\d+)/view", resp.text) if resp.status_code == 200 else []

    def _fetch_recipe_library_ids(self) -> List[int]:
        resp = self.client.get("/recipes/library", name="bootstrap.recipe_library", allow_redirects=True)
        return _extract_ids(r"/recipes/library/(\d+)", resp.text) if resp.status_code == 200 else []

    def _fetch_inventory_item_ids(self) -> List[int]:
        resp = self.client.get("/api/ingredients", name="bootstrap.inventory.api")
        if resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except json.JSONDecodeError:
            return []
        return [item["id"] for item in data if isinstance(item, dict) and item.get("id")]

    def _fetch_product_and_sku_ids(self) -> Tuple[List[int], List[int]]:
        resp = self.client.get("/products", name="bootstrap.products", allow_redirects=True)
        if resp.status_code != 200:
            return [], []
        product_ids = _extract_ids(r"/products/(\d+)", resp.text)
        sku_ids = _extract_ids(r"/sku/(\d+)", resp.text)
        return product_ids, sku_ids

    # -----------------------
    # Random selection helpers
    # -----------------------
    def pick_recipe_id(self) -> Optional[int]:
        if not self.recipe_ids:
            self.ensure_domain_cache(force=True)
        return random.choice(self.recipe_ids) if self.recipe_ids else None

    def pick_library_recipe_id(self) -> Optional[int]:
        if not self.library_recipe_ids:
            self.ensure_domain_cache(force=True)
        return random.choice(self.library_recipe_ids) if self.library_recipe_ids else None

    def pick_inventory_item_id(self) -> Optional[int]:
        if not self.inventory_item_ids:
            self.ensure_domain_cache(force=True)
        return random.choice(self.inventory_item_ids) if self.inventory_item_ids else None

    def pick_product_id(self) -> Optional[int]:
        if not self.product_ids:
            self.ensure_domain_cache(force=True)
        return random.choice(self.product_ids) if self.product_ids else None

    def pick_sku_inventory_id(self) -> Optional[int]:
        if not self.sku_inventory_ids:
            self.ensure_domain_cache(force=True)
        return random.choice(self.sku_inventory_ids) if self.sku_inventory_ids else None


class RecipeOpsUser(AuthenticatedMixin, HttpUser):
    """
    Simulates users that plan recipes, import library entries, and spin up batches.
    """

    wait_time = between(1, 3)
    weight = 4

    @task(4)
    def view_dashboard(self):
        self.client.get("/dashboard", name="dashboard")

    @task(4)
    def list_recipes(self):
        self.client.get("/recipes", name="recipes.list")

    @task(3)
    def plan_recipe(self):
        recipe_id = self.pick_recipe_id()
        if not recipe_id:
            return
        payload = {"scale": round(random.uniform(0.5, 3.0), 2)}
        self.client.post(
            f"/production-planning/recipe/{recipe_id}/plan",
            json=payload,
            name="production.plan",
        )

    @task(3)
    def auto_fill_containers(self):
        recipe_id = self.pick_recipe_id()
        if not recipe_id:
            return
        payload = {
            "scale": round(random.uniform(0.75, 2.5), 2),
            "product_density": round(random.uniform(0.4, 1.4), 2),
            "fill_pct": random.randint(70, 98),
        }
        self.client.post(
            f"/production-planning/recipe/{recipe_id}/auto-fill-containers",
            json=payload,
            name="production.auto_fill",
        )

    @task(4)
    def start_batch(self):
        recipe_id = self.pick_recipe_id()
        if not recipe_id:
            return
        payload = {
            "recipe_id": recipe_id,
            "scale": round(random.uniform(0.5, 4.0), 2),
            "batch_type": random.choice(["ingredient", "product"]),
            "notes": "Locust load-test batch",
            "containers": [],
            "force_start": random.choice([True, False]),
        }
        with self.client.post(
            "/batches/api/start-batch",
            json=payload,
            name="batches.api.start",
            catch_response=True,
        ) as response:
            if response.status_code >= 500:
                response.failure(f"Batch start failed ({response.status_code})")
            else:
                response.success()

    @task(2)
    def view_batch_list(self):
        self.client.get("/batches", name="batches.list")

    @task(2)
    def view_recipe_details(self):
        recipe_id = self.pick_recipe_id()
        if not recipe_id:
            return
        self.client.get(f"/recipes/{recipe_id}/view", name="recipes.detail")

    @task(2)
    def browse_recipe_library(self):
        params = {}
        if random.random() < 0.5:
            params["search"] = random.choice(["soap", "balm", "cookie", "toner"])
        self.client.get("/recipes/library", params=params, name="recipes.library.list")

    @task(1)
    def preview_recipe_import(self):
        library_id = self.pick_library_recipe_id()
        if not library_id:
            return
        # Recipe library detail requires both ID and slug - use placeholder slug for load testing
        self.client.get(f"/recipes/library/{library_id}-test-recipe", name="recipes.library.detail")
        with self.client.get(
            f"/recipes/{library_id}/import",
            name="recipes.import",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 302, 303, 403, 404):
                response.success()
            else:
                response.failure(f"Unexpected import status {response.status_code}")


class InventoryOpsUser(AuthenticatedMixin, HttpUser):
    """
    Simulates inventory managers restocking, spoiling, trashing, and auditing items.
    """

    wait_time = between(2, 5)
    weight = 3

    @task(4)
    def inventory_dashboard(self):
        self.client.get("/inventory", name="inventory.list")

    @task(3)
    def view_inventory_item(self):
        item_id = self.pick_inventory_item_id()
        if not item_id:
            return
        self.client.get(f"/inventory/view/{item_id}", name="inventory.view")

    @task(4)
    def adjust_inventory(self):
        item_id = self.pick_inventory_item_id()
        if not item_id:
            return
        change_type = random.choice(["restock", "spoil", "trash"])
        quantity = round(random.uniform(0.25, 5.0), 2)
        payload = {
            "change_type": change_type,
            "quantity": str(quantity),
            "input_unit": "count",
            "notes": f"Locust {change_type}",
        }
        if change_type == "restock":
            payload["cost_entry_type"] = "per_unit"
            payload["cost_per_unit"] = str(round(random.uniform(0.1, 10.0), 2))
        headers = {"X-Requested-With": "XMLHttpRequest"}
        with self.client.post(
            f"/inventory/adjust/{item_id}",
            data=payload,
            headers=headers,
            name=f"inventory.adjust.{change_type}",
            catch_response=True,
        ) as response:
            if response.status_code >= 500:
                response.failure("Inventory adjustment failed")
            else:
                response.success()

    @task(2)
    def expiration_summary(self):
        self.client.get("/expiration/api/summary", name="expiration.summary")

    @task(2)
    def global_items_lookup(self):
        params = {}
        if random.random() < 0.5:
            params["type"] = random.choice(["ingredient", "container", "consumable"])
        self.client.get("/global-items", params=params, name="global.items")


class ProductOpsUser(AuthenticatedMixin, HttpUser):
    """Simulates SKU managers updating finished goods and reconciling product lots."""

    wait_time = between(2, 6)
    weight = 2

    @task(3)
    def list_products(self):
        params = {}
        if random.random() < 0.4:
            params["sort"] = random.choice(["name", "popular", "stock"])
        self.client.get("/products", params=params, name="products.list")

    @task(2)
    def view_product_detail(self):
        product_id = self.pick_product_id()
        if not product_id:
            return
        self.client.get(f"/products/{product_id}", name="products.detail")

    @task(2)
    def view_sku_detail(self):
        sku_id = self.pick_sku_inventory_id()
        if not sku_id:
            return
        self.client.get(f"/sku/{sku_id}", name="sku.detail")

    @task(3)
    def adjust_product_inventory(self):
        sku_id = self.pick_sku_inventory_id()
        if not sku_id:
            return
        change_type = random.choice(["restock", "sale", "spoil", "trash"])
        payload = {
            "change_type": change_type,
            "quantity": round(random.uniform(1, 10), 2),
            "unit": "count",
            "notes": f"Locust {change_type}",
        }
        if change_type == "sale":
            payload["sale_price"] = round(random.uniform(5, 75), 2)
        headers = {"Content-Type": "application/json"}
        with self.client.post(
            f"/products/inventory/adjust/{sku_id}",
            json=payload,
            headers=headers,
            name=f"products.inventory.{change_type}",
            catch_response=True,
        ) as response:
            if response.status_code >= 500:
                response.failure("Product inventory adjustment failed")
            else:
                response.success()


class AnonymousUser(HttpUser):
    """Public-only traffic to keep cache warm without authentication."""

    wait_time = between(3, 8)
    weight = 1

    @task(4)
    def view_homepage(self):
        self.client.get("/", name="public.homepage")

    @task(3)
    def view_tools_index(self):
        self.client.get("/tools", name="public.tools")

    @task(3)
    def browse_global_items(self):
        params = {}
        if random.random() < 0.5:
            params["type"] = random.choice(["ingredient", "container"])
        self.client.get("/global-items", params=params, name="public.global_items")

    @task(2)
    def recipe_library_public(self):
        self.client.get("/recipes/library", name="public.recipe_library")

    @task(1)
    def signup_page(self):
        self.client.get("/auth/signup", name="public.signup")
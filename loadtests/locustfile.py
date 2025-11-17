
"""
Locust Load Testing Configuration

Comprehensive load testing scenarios to validate 10k+ concurrent user capacity.

Usage:
    # Basic load test
    locust -f loadtests/locustfile.py --host=http://localhost:5000

    # High-load simulation  
    locust -f loadtests/locustfile.py --host=https://your-app.replit.app -u 1000 -r 50

    # Authenticated user flows
    locust -f loadtests/locustfile.py AuthenticatedUser --host=https://your-app.replit.app

    # 5k concurrent user endurance test (headless)
    locust -f loadtests/locustfile.py --headless --shape-class FiveKUserLoadShape \
        --host=https://your-app.replit.app --run-time=45m

    # Mutating workflows (staging only – requires dedicated test data)
    LOCUST_ENABLE_MUTATIONS=1 LOCUST_MUTATION_USERNAME=loadtest+mutations@example.com \
        LOCUST_MUTATION_PASSWORD=replace-me locust -f loadtests/locustfile.py DataMutationUser \
        --headless --host=https://staging.your-app.example
"""

import os
import random
import re
import time
from collections import deque
from typing import Optional

from bs4 import BeautifulSoup
from locust import HttpUser, LoadTestShape, between, task
from locust.exception import StopUser


def _parse_id_list(env_key: str) -> list[int]:
    """Safely parse comma-delimited env vars into integer ID lists."""
    raw = os.environ.get(env_key, "")
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def _env_flag(name: str, default: str = "0") -> bool:
    return (os.environ.get(name, default) or "").strip().lower() in {"1", "true", "yes", "on"}


MUTATION_SCENARIOS_ENABLED = _env_flag("LOCUST_ENABLE_MUTATIONS")
try:
    DEFAULT_MUTATION_WEIGHT = float(os.environ.get("LOCUST_MUTATION_WEIGHT",
                                                 "0.2" if MUTATION_SCENARIOS_ENABLED else "0"))
except ValueError:
    DEFAULT_MUTATION_WEIGHT = 0.0

MUTATION_USERNAME = os.environ.get("LOCUST_MUTATION_USERNAME", "loadtest+mutations@example.com")
MUTATION_PASSWORD = os.environ.get("LOCUST_MUTATION_PASSWORD", "replace-me")
SEEDED_RECIPE_IDS = _parse_id_list("LOCUST_MUTATION_RECIPE_IDS")
SEEDED_INVENTORY_IDS = _parse_id_list("LOCUST_MUTATION_INVENTORY_IDS")

class AnonymousUser(HttpUser):
    """Anonymous user browsing public content."""
    
    wait_time = between(2, 8)
    weight = 3  # 75% of traffic
    
    @task(5)
    def view_homepage(self):
        """Load homepage and public content."""
        self.client.get("/", name="homepage")
    
    @task(3) 
    def view_tools(self):
        """Browse public tools."""
        tools = ["/tools", "/tools/soap", "/tools/candles", "/tools/lotions"]
        tool = random.choice(tools)
        self.client.get(tool, name="public_tools")
    
    @task(2)
    def view_global_library(self):
        """Browse global item library."""
        self.client.get("/library/global_items", name="global_library")
    
    @task(1)
    def attempt_signup(self):
        """Simulate signup page visits."""
        self.client.get("/auth/signup", name="signup_page")

class AuthenticatedMixin:
    """Shared helpers for users that require authentication."""

    login_username: str = ""
    login_password: str = ""
    login_name: str = "login"
    csrf_token: Optional[str] = None

    def _extract_csrf(self, response) -> Optional[str]:
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            token_field = soup.find("input", {"name": "csrf_token"})
            if token_field:
                return token_field.get("value")
        except Exception:
            return None
        return None

    def _extract_meta_csrf(self, html: str) -> Optional[str]:
        try:
            soup = BeautifulSoup(html, "html.parser")
            meta_tag = soup.find("meta", {"name": "csrf-token"})
            if meta_tag:
                return meta_tag.get("content")
        except Exception:
            return None
        return None

    def _perform_login(self, username: str, password: str, name: str):
        login_page = self.client.get("/auth/login", name="login_page")
        token = self._extract_csrf(login_page)

        payload = {
            "username": username,
            "password": password,
        }
        if token:
            payload["csrf_token"] = token
        response = self.client.post("/auth/login", data=payload, name=name)
        if response.status_code >= 400:
            response.failure(f"Login failed ({response.status_code})")
        return response

    def _refresh_csrf_token(self, seed_path: str = "/user_dashboard", metric_name: str = "csrf_seed"):
        """Fetch a page after login to capture the CSRF meta tag for API posts."""
        response = self.client.get(seed_path, name=metric_name)
        token = self._extract_meta_csrf(response.text)
        if token:
            self.csrf_token = token
        return token

    def _csrf_headers(self) -> dict[str, str]:
        if self.csrf_token:
            return {"X-CSRFToken": self.csrf_token}
        return {}

class AuthenticatedUser(AuthenticatedMixin, HttpUser):
    """Authenticated user performing typical app operations."""
    
    wait_time = between(3, 12)
    weight = 1  # 25% of traffic
    login_username = "loadtest@example.com"
    login_password = "replace-me"
    
    def on_start(self):
        """Login before starting tasks."""
        self._perform_login(self.login_username, self.login_password, "login")
    
    @task(8)
    def view_dashboard(self):
        """Load user dashboard."""
        self.client.get("/user_dashboard", name="dashboard")
    
    @task(5)
    def view_inventory(self):
        """Browse inventory sections."""
        self.client.get("/inventory/view", name="inventory_main")
        
        # Simulate browsing different inventory types
        inventory_sections = [
            "/inventory/view?type=ingredients",
            "/inventory/view?type=containers", 
            "/inventory/view?type=products"
        ]
        section = random.choice(inventory_sections)
        self.client.get(section, name="inventory_browse")
    
    @task(4)
    def view_products(self):
        """Browse and view products."""
        self.client.get("/products/list", name="products_list")
        
        # Simulate viewing individual products (if any exist)
        product_id = random.randint(1, 10)
        self.client.get(f"/products/{product_id}", 
                       name="product_detail", catch_response=True)
    
    @task(3)
    def view_recipes(self):
        """Browse recipes."""
        self.client.get("/recipes/list", name="recipes_list")
    
    @task(2)
    def view_batches(self):
        """Check batch status."""
        self.client.get("/batches/list", name="batches_list")
    
    @task(2)
    def production_planning(self):
        """Access production planning."""
        self.client.get("/production_planning/plan_production", 
                       name="production_planning")
    
    @task(1)
    def view_settings(self):
        """Access settings."""
        self.client.get("/settings", name="settings")

class AdminUser(AuthenticatedMixin, HttpUser):
    """Admin user performing administrative tasks."""
    
    wait_time = between(5, 20)
    weight = 0.1  # 2.5% of traffic
    login_username = "admin@example.com"
    login_password = "replace-me"
    
    def on_start(self):
        """Login as admin."""
        self._perform_login(self.login_username, self.login_password, "admin_login")
    
    @task(3)
    def organization_dashboard(self):
        """View organization dashboard."""
        self.client.get("/organization/dashboard", name="org_dashboard")
    
    @task(2)
    def user_management(self):
        """Access user management."""
        self.client.get("/organization/dashboard#users", name="user_mgmt")
    
    @task(1)
    def billing_status(self):
        """Check billing status."""
        self.client.get("/organization/dashboard#billing", name="billing_status")

class HighFrequencyUser(AuthenticatedMixin, HttpUser):
    """Simulates rapid API usage patterns."""
    
    wait_time = between(0.5, 2)
    weight = 0.5  # 12.5% of traffic
    login_username = "api@example.com"
    login_password = "replace-me"
    
    def on_start(self):
        """Quick login for API-like usage."""
        self._perform_login(self.login_username, self.login_password, "api_login")
    
    @task(10)
    def rapid_dashboard_checks(self):
        """Frequent dashboard polling."""
        self.client.get("/user_dashboard", name="rapid_dashboard")
    
    @task(5) 
    def inventory_api_calls(self):
        """Simulate frequent inventory checks."""
        self.client.get("/api/inventory/summary", name="api_inventory")
    
    @task(3)
    def batch_status_checks(self):
        """Check batch status frequently."""
        self.client.get("/api/batches/active", name="api_batches")

# Load testing scenarios for different purposes
class StressTest(HttpUser):
    """High-intensity stress testing."""
    
    wait_time = between(0.1, 1)
    
    tasks = [
        AnonymousUser.view_homepage,
        AuthenticatedUser.view_dashboard,
        AuthenticatedUser.view_inventory
    ]


class TimerHeavyUser(AuthenticatedMixin, HttpUser):
    """Focus on timer endpoints and dashboard polling to stress check the timer service."""

    wait_time = between(1, 4)
    weight = 0.2  # optional addition to traffic mix
    login_username = "loadtest@example.com"
    login_password = "replace-me"

    def on_start(self):
        self._perform_login(self.login_username, self.login_password, "timer_login")

    @task(6)
    def heartbeat(self):
        self.client.get("/api/server-time", name="server_time")

    @task(4)
    def dashboard_alerts(self):
        self.client.get("/api/dashboard-alerts", name="dashboard_alerts")

    @task(3)
    def timer_summary(self):
        self.client.get("/api/timer-summary", name="timer_summary")

    @task(2)
    def expired_timers(self):
        self.client.get("/timers/api/expired-timers", name="expired_timers")

    @task(1)
    def auto_expire(self):
        self.client.post("/timers/api/auto-expire-timers", name="auto_expire_timers")


class DataMutationUser(AuthenticatedMixin, HttpUser):
    """
    Executes write-heavy workflows (start batches, fail batches, adjust inventory,
    update settings) to exercise database mutations. Enable via LOCUST_ENABLE_MUTATIONS=1
    and point to a staging environment with disposable data.
    """

    wait_time = between(5, 15)
    weight = DEFAULT_MUTATION_WEIGHT if MUTATION_SCENARIOS_ENABLED else 0.0
    login_username = MUTATION_USERNAME
    login_password = MUTATION_PASSWORD

    def __init__(self, environment):
        super().__init__(environment)
        self.known_recipe_ids: list[int] = list(SEEDED_RECIPE_IDS)
        self.inventory_item_ids: list[int] = list(SEEDED_INVENTORY_IDS)
        self.inventory_cache: dict[int, dict] = {}
        self.active_batches: deque[int] = deque(maxlen=25)

    def on_start(self):
        if not MUTATION_SCENARIOS_ENABLED:
            raise StopUser("Mutating flows disabled (set LOCUST_ENABLE_MUTATIONS=1 to enable).")
        self._perform_login(self.login_username, self.login_password, "mutator_login")
        self._refresh_csrf_token(seed_path="/settings", metric_name="mutator_csrf_seed")
        self._prime_recipe_ids()
        self._prime_inventory_ids()

    def _prime_recipe_ids(self):
        if self.known_recipe_ids:
            return
        response = self.client.get("/recipes", name="mutator_recipes_seed")
        if response.status_code == 200:
            ids = {int(match) for match in re.findall(r"/recipes/(\d+)", response.text)}
            if ids:
                self.known_recipe_ids.extend(ids)

    def _prime_inventory_ids(self):
        if self.inventory_item_ids:
            return
        # Use an arbitrary 2-letter search to satisfy search minimum
        for query in ("aa", "li", "ba"):
            response = self.client.get(f"/inventory/api/search?q={query}", name="mutator_inventory_seed")
            if response.status_code != 200:
                continue
            try:
                data = response.json() or {}
                results = data.get("results") or []
                for item in results:
                    item_id = item.get("id")
                    if item_id:
                        self.inventory_item_ids.append(int(item_id))
            except Exception:
                continue
        # Deduplicate
        self.inventory_item_ids = list(dict.fromkeys(self.inventory_item_ids))

    def _choose_recipe_id(self) -> Optional[int]:
        if not self.known_recipe_ids:
            self._prime_recipe_ids()
        return random.choice(self.known_recipe_ids) if self.known_recipe_ids else None

    def _choose_inventory_item(self) -> Optional[int]:
        if not self.inventory_item_ids:
            self._prime_inventory_ids()
        return random.choice(self.inventory_item_ids) if self.inventory_item_ids else None

    def _get_inventory_details(self, item_id: int) -> dict:
        if item_id in self.inventory_cache:
            return self.inventory_cache[item_id]
        response = self.client.get(
            f"/inventory/api/get-item/{item_id}", name="mutator_inventory_detail"
        )
        if response.status_code == 200:
            try:
                payload = response.json() or {}
            except Exception:
                payload = {}
        else:
            payload = {}
        self.inventory_cache[item_id] = payload
        return payload

    def _ensure_csrf(self):
        if not self.csrf_token:
            self._refresh_csrf_token(metric_name="mutator_csrf_refresh")

    @task(5)
    def start_batch_flow(self):
        recipe_id = self._choose_recipe_id()
        if not recipe_id:
            return
        payload = {
            "recipe_id": recipe_id,
            "scale": random.choice([0.5, 1.0, 1.5]),
            "batch_type": random.choice(["ingredient", "product"]),
            "notes": f"locust-start-{int(time.time())}",
            "containers": [],
            "force_start": True,
        }
        response = self.client.post(
            "/batches/api/start-batch",
            json=payload,
            name="mutate_start_batch",
        )
        if response.status_code >= 400:
            response.failure(f"Start batch failed ({response.status_code})")
            return
        try:
            data = response.json() or {}
        except Exception:
            data = {}
        if data.get("success") and data.get("batch_id"):
            self.active_batches.append(int(data["batch_id"]))

    @task(3)
    def fail_batch_flow(self):
        if not self.active_batches:
            return
        batch_id = random.choice(list(self.active_batches))
        self._ensure_csrf()
        response = self.client.post(
            f"/batches/finish-batch/{batch_id}/fail",
            json={"reason": "Load-test auto-fail"},
            headers=self._csrf_headers(),
            name="mutate_fail_batch",
        )
        if response.status_code < 400:
            try:
                self.active_batches.remove(batch_id)
            except ValueError:
                pass

    @task(3)
    def inventory_adjustments(self):
        item_id = self._choose_inventory_item()
        if not item_id:
            return
        item = self._get_inventory_details(item_id)
        unit = item.get("unit") or "count"
        change_type = random.choice(["restock", "use"])
        quantity = round(random.uniform(0.5, 3.0), 2)
        form_data = {
            "change_type": change_type,
            "quantity": str(quantity),
            "input_unit": unit,
            "notes": f"locust-{change_type}-{int(time.time())}",
            "cost_entry_type": "no_change",
        }
        response = self.client.post(
            f"/inventory/adjust/{item_id}",
            data=form_data,
            name="mutate_inventory_adjust",
        )
        if response.status_code >= 400:
            response.failure(f"Inventory adjust failed ({response.status_code})")

    @task(2)
    def create_custom_unit(self):
        self._ensure_csrf()
        headers = {"Content-Type": "application/json"}
        headers.update(self._csrf_headers())
        unit_name = f"locust-unit-{random.randint(1000, 9999)}"
        payload = {
            "name": unit_name,
            "unit_type": random.choice(["count", "weight", "volume"]),
        }
        response = self.client.post(
            "/api/units",
            json=payload,
            headers=headers,
            name="mutate_create_unit",
        )
        if response.status_code >= 400:
            response.failure(f"Create unit failed ({response.status_code})")

    @task(2)
    def update_profile_preferences(self):
        self._ensure_csrf()
        headers = {"Content-Type": "application/json"}
        headers.update(self._csrf_headers())
        suffix = random.randint(1000, 9999)
        payload = {
            "first_name": "Load",
            "last_name": f"Tester{suffix}",
            "email": self.login_username,
            "phone": f"+1-555-{suffix:04d}",
            "timezone": "UTC",
        }
        response = self.client.post(
            "/settings/profile/save",
            json=payload,
            headers=headers,
            name="mutate_profile_update",
        )
        if response.status_code >= 400:
            response.failure(f"Profile update failed ({response.status_code})")

    @task(1)
    def global_library_reads(self):
        self.client.get("/library/global_items", name="mutate_global_library")

class FiveKUserLoadShape(LoadTestShape):
    """
    Structured load shape that ramps to 5k concurrent users, sustains the load,
    and then ramps back down. Use with --shape-class FiveKUserLoadShape.
    """

    stages = [
        {"duration": 120, "users": 500, "spawn_rate": 200},    # warm-up (~2m)
        {"duration": 240, "users": 2000, "spawn_rate": 400},   # rapid ramp (~4m)
        {"duration": 360, "users": 3500, "spawn_rate": 300},   # approach peak (~6m)
        {"duration": 900, "users": 5000, "spawn_rate": 200},   # sustain peak (~15m)
        {"duration": 300, "users": 3000, "spawn_rate": 150},   # controlled cooldown (~5m)
        {"duration": 180, "users": 0, "spawn_rate": 300},      # ramp down (~3m)
    ]

    def tick(self):
        run_time = self.get_run_time()
        elapsed = 0

        for stage in self.stages:
            elapsed += stage["duration"]
            if run_time < elapsed:
                return stage["users"], stage["spawn_rate"]

        return None

if __name__ == "__main__":
    print("Load test scenarios available:")
    print("- AnonymousUser: Public browsing (75% weight)")
    print("- AuthenticatedUser: Logged-in usage (25% weight)")  
    print("- AdminUser: Administrative tasks (2.5% weight)")
    print("- HighFrequencyUser: Rapid API usage (12.5% weight)")
    print("- TimerHeavyUser: Timer-heavy polling (optional, add explicitly)")
    print("- StressTest: High-intensity testing")
    print("- FiveKUserLoadShape: Ramp/hold/ramp-down to 5k concurrent virtual users")
    print("- DataMutationUser: Write-heavy workflows (requires LOCUST_ENABLE_MUTATIONS=1)")


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
"""

import random
import time
from typing import Optional

from bs4 import BeautifulSoup
from locust import HttpUser, task, between

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
        self.client.get("/global-items", name="global_library")

    @task(1)
    def attempt_signup(self):
        """Simulate signup page visits."""
        self.client.get("/auth/signup", name="signup_page")

class AuthenticatedMixin:
    """Shared helpers for users that require authentication."""

    login_username: str = ""
    login_password: str = ""
    login_name: str = "login"

    def _extract_csrf(self, response) -> Optional[str]:
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            token_field = soup.find("input", {"name": "csrf_token"})
            if token_field:
                return token_field.get("value")
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

        with self.client.post("/auth/login", data=payload, name=name, catch_response=True) as response:
            if response.status_code >= 400:
                response.failure(f"Login failed ({response.status_code})")
            elif "Invalid username or password" in response.text:
                response.failure("Invalid credentials")
            else:
                response.success()
        return response


class AuthenticatedUser(AuthenticatedMixin, HttpUser):
    """Authenticated user performing typical app operations."""

    wait_time = between(3, 12)
    weight = 1  # 25% of traffic
    login_username = "test@example.com"
    login_password = "testpassword123"

    def on_start(self):
        """Login before starting tasks."""
        self._perform_login(self.login_username, self.login_password, "login")

    @task(8)
    def view_dashboard(self):
        """Load user dashboard."""
        self.client.get("/dashboard", name="dashboard")

    @task(5)
    def view_inventory(self):
        """Browse inventory sections."""
        self.client.get("/inventory", name="inventory_main")

        # Simulate browsing different inventory types
        inventory_sections = [
            "/inventory?type=ingredient",
            "/inventory?type=container", 
            "/inventory?type=consumable"
        ]
        section = random.choice(inventory_sections)
        self.client.get(section, name="inventory_browse")

    @task(4)
    def view_products(self):
        """Browse and view products."""
        self.client.get("/products", name="products_list")

        # Simulate viewing individual products (if any exist)
        product_id = random.randint(1, 10)
        self.client.get(f"/products/{product_id}", 
                       name="product_detail", catch_response=True)

    @task(3)
    def view_recipes(self):
        """Browse recipes."""
        self.client.get("/recipes", name="recipes_list")

    @task(2)
    def view_batches(self):
        """Check batch status."""
        self.client.get("/batches", name="batches_list")

    @task(2)
    def production_planning(self):
        """Access production planning."""
        # Try to access a recipe for planning
        recipe_id = random.randint(1, 5)
        self.client.get(f"/production-planning/recipe/{recipe_id}/plan", 
                       name="production_planning", catch_response=True)

    @task(1)
    def view_settings(self):
        """Access settings."""
        self.client.get("/settings", name="settings")

class AdminUser(AuthenticatedMixin, HttpUser):
    """Admin user performing administrative tasks."""

    wait_time = between(5, 20)
    weight = 0.1  # 2.5% of traffic
    login_username = "dev"
    login_password = "devpassword123"

    def on_start(self):
        """Login as admin."""
        self._perform_login(self.login_username, self.login_password, "admin_login")

    @task(3)
    def organization_dashboard(self):
        """View organization dashboard."""
        self.client.get("/organization/dashboard", name="org_dashboard")

    @task(2)
    def developer_dashboard(self):
        """Access developer dashboard."""
        self.client.get("/developer/dashboard", name="dev_dashboard")

    @task(1)
    def view_users(self):
        """Check user management."""
        self.client.get("/developer/users", name="user_mgmt")

class HighFrequencyUser(AuthenticatedMixin, HttpUser):
    """Simulates rapid API usage patterns."""

    wait_time = between(0.5, 2)
    weight = 0.5  # 12.5% of traffic
    login_username = "test@example.com"
    login_password = "testpassword123"

    def on_start(self):
        """Quick login for API-like usage."""
        self._perform_login(self.login_username, self.login_password, "api_login")

    @task(10)
    def rapid_dashboard_checks(self):
        """Frequent dashboard polling."""
        self.client.get("/dashboard", name="rapid_dashboard")

    @task(5) 
    def api_calls(self):
        """Simulate API calls."""
        api_endpoints = [
            "/api/server-time",
            "/api/dashboard-alerts",
        ]
        endpoint = random.choice(api_endpoints)
        self.client.get(endpoint, name="api_calls")

    @task(3)
    def inventory_checks(self):
        """Check inventory frequently."""
        self.client.get("/inventory", name="inventory_check")

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
    login_username = "test@example.com"
    login_password = "testpassword123"

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

if __name__ == "__main__":
    print("Load test scenarios available:")
    print("- AnonymousUser: Public browsing (75% weight)")
    print("- AuthenticatedUser: Logged-in usage (25% weight)")  
    print("- AdminUser: Administrative tasks (2.5% weight)")
    print("- HighFrequencyUser: Rapid API usage (12.5% weight)")
    print("- TimerHeavyUser: Timer-heavy polling (optional, add explicitly)")
    print("- StressTest: High-intensity testing")

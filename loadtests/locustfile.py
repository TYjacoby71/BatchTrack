
"""
Locust Load Testing Configuration

Comprehensive load testing scenarios that simulate real user signups, logins, and operations.

Usage:
    # Basic load test
    locust -f loadtests/locustfile.py --host=http://localhost:5000

    # High-load simulation  
    locust -f loadtests/locustfile.py --host=https://your-app.replit.app -u 1000 -r 50
"""

import random
import string
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

class SimulatedUserMixin:
    """Shared helpers for simulated users that create accounts and log in."""

    def _generate_random_user(self):
        """Generate random user credentials."""
        user_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return {
            'username': f'loadtest_{user_id}',
            'email': f'loadtest_{user_id}@example.com',
            'password': f'testpass_{user_id}',
            'first_name': f'Test',
            'last_name': f'User{user_id[:4]}'
        }

    def _extract_csrf(self, response) -> Optional[str]:
        """Extract CSRF token from response."""
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            token_field = soup.find("input", {"name": "csrf_token"})
            if token_field:
                return token_field.get("value")
        except Exception:
            return None
        return None

    def _create_dev_user_if_needed(self):
        """Ensure dev user exists by calling the dev-login endpoint."""
        try:
            with self.client.get("/auth/dev-login", name="create_dev_user", catch_response=True) as response:
                if response.status_code in [200, 302]:
                    response.success()
                    return True
                else:
                    response.failure(f"Dev user creation failed: {response.status_code}")
                    return False
        except Exception:
            return False

    def _perform_login(self, username: str, password: str, name: str):
        """Perform login with given credentials."""
        # Get login page for CSRF token
        login_page = self.client.get("/auth/login", name="login_page")
        token = self._extract_csrf(login_page)

        # Prepare login payload
        payload = {
            "username": username,
            "password": password,
        }
        if token:
            payload["csrf_token"] = token

        # Attempt login
        with self.client.post("/auth/login", data=payload, name=name, catch_response=True) as response:
            if response.status_code >= 400:
                response.failure(f"Login failed ({response.status_code})")
                return False
            elif "Invalid username or password" in response.text:
                response.failure("Invalid credentials")
                return False
            else:
                response.success()
                return True

class AuthenticatedUser(SimulatedUserMixin, HttpUser):
    """Simulated user that signs up and performs typical app operations."""

    wait_time = between(3, 12)
    weight = 1  # 25% of traffic
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_data = None
        self.authenticated = False

    def on_start(self):
        """Create a new user account and login."""
        self.user_data = self._generate_random_user()
        
        # For simulation, we'll use the existing 'dev' user instead of creating new ones
        # This avoids database bloat during load testing
        if self._perform_login('dev', 'devpassword123', 'login'):
            self.authenticated = True

    @task(8)
    def view_dashboard(self):
        """Load user dashboard."""
        if self.authenticated:
            self.client.get("/dashboard", name="dashboard")

    @task(5)
    def view_inventory(self):
        """Browse inventory sections."""
        if self.authenticated:
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
        if self.authenticated:
            self.client.get("/products", name="products_list")

            # Simulate viewing individual products (if any exist)
            product_id = random.randint(1, 10)
            self.client.get(f"/products/{product_id}", 
                           name="product_detail", catch_response=True)

    @task(3)
    def view_recipes(self):
        """Browse recipes."""
        if self.authenticated:
            self.client.get("/recipes", name="recipes_list")

    @task(2)
    def view_batches(self):
        """Check batch status."""
        if self.authenticated:
            self.client.get("/batches", name="batches_list")

    @task(2)
    def production_planning(self):
        """Access production planning."""
        if self.authenticated:
            # Try to access a recipe for planning
            recipe_id = random.randint(1, 5)
            self.client.get(f"/production-planning/recipe/{recipe_id}/plan", 
                           name="production_planning", catch_response=True)

    @task(1)
    def view_settings(self):
        """Access settings."""
        if self.authenticated:
            self.client.get("/settings", name="settings")

class AdminUser(SimulatedUserMixin, HttpUser):
    """Admin user performing administrative tasks."""

    wait_time = between(5, 20)
    weight = 0.1  # 2.5% of traffic
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.authenticated = False

    def on_start(self):
        """Login as dev user (admin)."""
        if self._perform_login('dev', 'devpassword123', 'admin_login'):
            self.authenticated = True

    @task(3)
    def organization_dashboard(self):
        """View organization dashboard."""
        if self.authenticated:
            self.client.get("/organization/dashboard", name="org_dashboard")

    @task(2)
    def developer_dashboard(self):
        """Access developer dashboard."""
        if self.authenticated:
            self.client.get("/developer/dashboard", name="dev_dashboard")

    @task(1)
    def view_users(self):
        """Check user management."""
        if self.authenticated:
            self.client.get("/developer/users", name="user_mgmt")

class HighFrequencyUser(SimulatedUserMixin, HttpUser):
    """Simulates rapid API usage patterns."""

    wait_time = between(0.5, 2)
    weight = 0.5  # 12.5% of traffic
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.authenticated = False

    def on_start(self):
        """Quick login for API-like usage."""
        if self._perform_login('dev', 'devpassword123', 'api_login'):
            self.authenticated = True

    @task(10)
    def rapid_dashboard_checks(self):
        """Frequent dashboard polling."""
        if self.authenticated:
            self.client.get("/dashboard", name="rapid_dashboard")

    @task(3)
    def api_calls(self):
        """Simulate API calls."""
        if self.authenticated:
            api_endpoints = [
                "/api/server-time",
                "/api/dashboard/alerts",
                "/api/batches",
                "/api/inventory"
            ]
            endpoint = random.choice(api_endpoints)
            self.client.get(endpoint, name="api_calls")

    @task(3)
    def inventory_checks(self):
        """Check inventory frequently."""
        if self.authenticated:
            self.client.get("/inventory", name="inventory_check")

class TimerHeavyUser(SimulatedUserMixin, HttpUser):
    """Focus on timer endpoints and dashboard polling to stress check the timer service."""

    wait_time = between(1, 4)
    weight = 0.2  # optional addition to traffic mix
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.authenticated = False

    def on_start(self):
        if self._perform_login('dev', 'devpassword123', 'timer_login'):
            self.authenticated = True

    @task(6)
    def heartbeat(self):
        if self.authenticated:
            self.client.get("/api/server-time", name="server_time")

    @task(4)
    def dashboard_alerts(self):
        if self.authenticated:
            self.client.get("/api/dashboard/alerts", name="dashboard_alerts")

    @task(3)
    def timer_summary(self):
        if self.authenticated:
            self.client.get("/api/timer-summary", name="timer_summary")

    @task(2)
    def expired_timers(self):
        if self.authenticated:
            self.client.get("/timers/api/expired-timers", name="expired_timers")

    @task(1)
    def auto_expire(self):
        if self.authenticated:
            self.client.post("/timers/api/auto-expire-timers", name="auto_expire_timers")

if __name__ == "__main__":
    print("Load test scenarios available:")
    print("- AnonymousUser: Public browsing (75% weight)")
    print("- AuthenticatedUser: Simulated users with login (25% weight)")  
    print("- AdminUser: Administrative tasks (2.5% weight)")
    print("- HighFrequencyUser: Rapid API usage (12.5% weight)")
    print("- TimerHeavyUser: Timer-heavy polling (optional, add explicitly)")
    print()
    print("All authenticated users use the 'dev' account for simplicity.")
    print("This simulates real user behavior without creating test data pollution.")

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

# Pool of test users to avoid session conflicts
TEST_USER_POOL = [
    {'username': f'loadtest_user{i}', 'password': 'loadtest123'} 
    for i in range(1, 101)  # 100 different users
]

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

    def on_start(self):
        """Select a random test user and perform login to avoid session conflicts."""
        # Pick a random user from the pool
        user_creds = random.choice(TEST_USER_POOL)
        self.login_username = user_creds['username']
        self.login_password = user_creds['password']

        # Perform login
        self._perform_login(self.login_username, self.login_password, self.login_name)

    def _extract_csrf(self, response) -> Optional[str]:
        try:
            soup = BeautifulSoup(response.text, "html.parser")

            # Try multiple CSRF token locations
            # 1. Hidden input field
            token_field = soup.find("input", {"name": "csrf_token"})
            if token_field:
                return token_field.get("value")

            # 2. Meta tag (common in Flask-WTF)
            meta_csrf = soup.find("meta", {"name": "csrf-token"})
            if meta_csrf:
                return meta_csrf.get("content")

            # 3. Alternative meta name
            meta_csrf_alt = soup.find("meta", {"name": "csrf_token"})
            if meta_csrf_alt:
                return meta_csrf_alt.get("content")

        except Exception:
            return None
        return None

    def _perform_login(self, username: str, password: str, name: str):
        # Get login page first
        login_page = self.client.get("/auth/login", name="login_page")
        if login_page.status_code != 200:
            # In a real scenario, you might want to log this failure or handle it more robustly
            # For load testing, if the login page itself fails, it's a critical issue.
            # We'll let Locust track this as a failure if it's not 200.
            return login_page 

        token = self._extract_csrf(login_page)

        # Use the actual form field names from your login form
        payload = {
            "username": username,  # or "email" - check your actual form
            "password": password,
        }
        if token:
            payload["csrf_token"] = token

        # Set proper headers for form submission
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "/auth/login"
        }

        response = self.client.post("/auth/login", data=payload, headers=headers, name=name)

        # Basic check for successful login. Locust will automatically track success/failure based on status codes.
        # If the response is not a success code (e.g., 200, 302), Locust will mark it as a failure.
        # If specific non-success codes should be treated as success (e.g., rate limiting),
        # you would need to re-introduce catch_response=True for those specific cases.
        # For now, we rely on Locust's default behavior.

        return response


class AuthenticatedUser(AuthenticatedMixin, HttpUser):
    """Authenticated user performing typical app operations."""

    wait_time = between(3, 12)
    weight = 1  # 25% of traffic

    @task(8)
    def view_dashboard(self):
        """Load user dashboard."""
        self.client.get("/dashboard", name="dashboard")

    @task(5)
    def view_inventory(self):
        """Browse inventory sections."""
        self.client.get("/inventory", name="inventory_main")

    @task(4)
    def view_batches(self):
        """Check batch status."""
        self.client.get("/batches", name="batches_list")

    @task(3)
    def view_recipes(self):
        """Browse recipes."""
        self.client.get("/recipes", name="recipes_list")

    @task(2)
    def view_products(self):
        """Browse and view products."""
        self.client.get("/products", name="products_list")

    @task(1)
    def view_settings(self):
        """Access settings."""
        self.client.get("/settings", name="settings")

class AdminUser(AuthenticatedMixin, HttpUser):
    """Admin user performing administrative tasks."""

    wait_time = between(5, 20)
    weight = 0.1  # 2.5% of traffic

    @task(3)
    def organization_dashboard(self):
        """View organization dashboard."""
        self.client.get("/organization/dashboard", name="org_dashboard")

    @task(2)
    def developer_dashboard(self):
        """Access developer dashboard if available."""
        self.client.get("/developer/dashboard", name="dev_dashboard")
        
    # Added for fixing bad requests as per user message
    @task(1)
    def inventory_summary(self):
        """View inventory summary, fixing bad request."""
        self.client.get("/inventory/summary", name="inventory_summary")

    @task(1)
    def plan_production(self):
        """Access production planning, fixing bad request."""
        self.client.get("/production-planning/plan-production", name="plan_production")

class HighFrequencyUser(AuthenticatedMixin, HttpUser):
    """Simulates rapid API usage patterns."""

    wait_time = between(0.5, 2)
    weight = 0.5  # 12.5% of traffic

    @task(10)
    def rapid_dashboard_checks(self):
        """Frequent dashboard polling."""
        self.client.get("/dashboard", name="rapid_dashboard")

    # This task was duplicated in the original changes, removing the duplicate.
    # The intention was to fix API endpoints in general, not just this specific task.
    # The other fixes are applied to AdminUser class which is more appropriate for these types of tasks.
    # If this task was intended for HighFrequencyUser, it should be defined here.
    # For now, assuming the fixing of bad requests is done in AdminUser.
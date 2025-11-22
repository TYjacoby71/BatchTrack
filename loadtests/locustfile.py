"""
Locust Load Testing Configuration - Clean Version

Fixed version that only hits valid endpoints with proper authentication.
"""

import random
import time
from typing import Optional

from bs4 import BeautifulSoup
from locust import HttpUser, task, between

# Smaller pool to avoid rate limiting
TEST_USER_POOL = [
    {'username': f'loadtest_user{i}', 'password': 'loadtest123'}
    for i in range(1, 11)  # Only 10 users
]

class AnonymousUser(HttpUser):
    """Anonymous user browsing public content only."""

    wait_time = between(5, 15)  # Longer waits to avoid rate limits
    weight = 4  # Most traffic

    @task(5)
    def view_homepage(self):
        """Load homepage."""
        self.client.get("/", name="homepage")

    @task(3)
    def view_tools_index(self):
        """Browse tools index page."""
        self.client.get("/tools", name="tools_index")

    @task(2)
    def view_global_items(self):
        """Browse global items library."""
        self.client.get("/global-items", name="global_items")

    @task(1)
    def view_signup(self):
        """View signup page."""
        self.client.get("/auth/signup", name="signup_page")


class AuthenticatedMixin:
    """Shared helpers for authenticated users."""

    login_username: str = ""
    login_password: str = ""

    def on_start(self):
        """Perform login with a random test user."""
        # Pick a random user from the pool
        user_creds = random.choice(TEST_USER_POOL)
        self.login_username = user_creds['username']
        self.login_password = user_creds['password']

        # Perform simple login without catch_response
        self._perform_login(self.login_username, self.login_password)

    def _extract_csrf(self, response) -> Optional[str]:
        """Extract CSRF token from login page."""
        try:
            soup = BeautifulSoup(response.text, "html.parser")

            # Try hidden input field
            token_field = soup.find("input", {"name": "csrf_token"})
            if token_field:
                return token_field.get("value")

            # Try meta tag
            meta_csrf = soup.find("meta", {"name": "csrf-token"})
            if meta_csrf:
                return meta_csrf.get("content")

        except Exception:
            return None
        return None

    def _perform_login(self, username: str, password: str):
        """Simple login without manual success/failure handling."""
        # Get login page
        login_page = self.client.get("/auth/login", name="login_page")
        if login_page.status_code != 200:
            return

        # Extract CSRF token
        token = self._extract_csrf(login_page)

        # Prepare login data
        payload = {
            "username": username,
            "password": password,
        }
        if token:
            payload["csrf_token"] = token

        # Set proper headers
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "/auth/login"
        }

        # Perform login - let Locust handle success/failure automatically
        self.client.post("/auth/login", data=payload, headers=headers, name="login_submit")


class AuthenticatedUser(AuthenticatedMixin, HttpUser):
    """Authenticated user with realistic usage patterns."""

    wait_time = between(8, 20)  # Longer waits to avoid rate limits
    weight = 1  # Lower weight

    @task(10)
    def view_dashboard(self):
        """Load user dashboard."""
        self.client.get("/dashboard", name="dashboard")

    @task(6)
    def view_inventory_list(self):
        """Browse inventory list."""
        self.client.get("/inventory", name="inventory_list")

    @task(5)
    def view_batches_list(self):
        """Check batches list."""
        self.client.get("/batches", name="batches_list")

    @task(4)
    def view_recipes_list(self):
        """Browse recipes."""
        self.client.get("/recipes", name="recipes_list")

    @task(3)
    def view_products_list(self):
        """Browse products."""
        self.client.get("/products", name="products_list")

    @task(2)
    def view_settings(self):
        """Access settings."""
        self.client.get("/settings", name="settings")

    @task(1)
    def check_server_time(self):
        """Check server time API."""
        self.client.get("/api/server-time", name="server_time")


class LightLoadUser(AuthenticatedMixin, HttpUser):
    """Very light load user for testing basic functionality."""

    wait_time = between(15, 30)  # Very long waits
    weight = 0.5

    @task(5)
    def dashboard_only(self):
        """Only check dashboard."""
        self.client.get("/dashboard", name="light_dashboard")

    @task(2)
    def inventory_only(self):
        """Only check inventory."""
        self.client.get("/inventory", name="light_inventory")

    @task(1)
    def api_health_check(self):
        """API health check."""
        self.client.get("/api", name="api_health")
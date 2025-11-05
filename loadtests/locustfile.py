"""Baseline Locust scenarios for BatchTrack.

Run with:

    locust -f loadtests/locustfile.py --host=https://your-env.example.com

Use this as a starting point—extend with authenticated flows once you have
token/bootstrap endpoints scripted.
"""

from locust import HttpUser, between, task


class UnauthenticatedBrowse(HttpUser):
    """Exercises public endpoints, homepage, and tools without authentication."""

    wait_time = between(1, 5)

    @task(3)
    def homepage(self):
        self.client.get("/")

    @task(1)
    def tools(self):
        self.client.get("/tools")

    @task(1)
    def healthcheck(self):
        self.client.get("/healthz", name="healthz")


class AuthenticatedUser(HttpUser):
    """Simulates an authenticated dashboard workflow using session cookies."""

    wait_time = between(2, 6)

    def on_start(self):
        # Replace with real credentials in a secure secret store for load testing.
        payload = {"username": "loadtest@example.com", "password": "replace-me"}
        response = self.client.post("/auth/login", data=payload, name="login")
        if response.status_code >= 400:
            self.environment.runner.quit()

    @task(4)
    def dashboard(self):
        self.client.get("/dashboard", name="dashboard")

    @task(2)
    def inventory(self):
        self.client.get("/inventory", name="inventory")

    @task(1)
    def batches(self):
        self.client.get("/batches", name="batches")

"""
Load testing scenarios for BatchTrack 10k concurrent user target

Run with: locust -f loadtests/locustfile.py --host=http://localhost:5000
"""

from locust import HttpUser, task, between
import random
import json

class AnonymousUser(HttpUser):
    """Unauthenticated user browsing public pages"""
    weight = 3
    wait_time = between(2, 8)
    
    @task(3)
    def visit_homepage(self):
        self.client.get("/", name="homepage")
    
    @task(2) 
    def visit_public_tools(self):
        tools = ["soap", "lotions", "candles", "herbal", "baker"]
        tool = random.choice(tools)
        self.client.get(f"/tools/{tool}", name="public_tools")
        
    @task(1)
    def visit_global_library(self):
        self.client.get("/library/public", name="global_library")
        
    @task(1)
    def visit_login_page(self):
        self.client.get("/auth/login", name="login_page")

class AuthenticatedUser(HttpUser):
    """Authenticated user performing typical operations"""
    weight = 7 
    wait_time = between(1, 5)
    
    def on_start(self):
        """Login at start of test"""
        payload = {
            "username": "loadtest@example.com", 
            "password": "replace-me"  # Update with actual test credentials
        }
        response = self.client.post("/auth/login", data=payload, name="login")
        if response.status_code != 200:
            print(f"Login failed: {response.status_code}")
    
    @task(5)
    def view_dashboard(self):
        self.client.get("/user_dashboard", name="dashboard")
        
    @task(4)
    def view_inventory_list(self):
        self.client.get("/inventory/list", name="inventory_list")
        
    @task(3) 
    def view_products_list(self):
        self.client.get("/products/list", name="products_list")
        
    @task(2)
    def view_batches_list(self):
        self.client.get("/batches/list", name="batches_list")
        
    @task(2)
    def view_recipes_list(self):
        self.client.get("/recipes/list", name="recipes_list")
        
    @task(2)
    def check_alerts(self):
        """Check dashboard alerts (cached endpoint)"""
        self.client.get("/api/dashboard/alerts", name="api_alerts")
        
    @task(1)
    def view_settings(self):
        self.client.get("/settings", name="settings")
        
    @task(1)
    def quick_inventory_add(self):
        """Simulate adding inventory item"""
        payload = {
            "name": f"Test Item {random.randint(1, 1000)}",
            "quantity": random.randint(1, 100), 
            "unit": "g",
            "cost_per_unit": round(random.uniform(0.1, 10.0), 2)
        }
        self.client.post("/inventory/add", 
                        json=payload, 
                        headers={"Content-Type": "application/json"},
                        name="inventory_add")

class HighVolumeAPIUser(HttpUser):
    """Heavy API usage simulating integrations or power users"""
    weight = 2
    wait_time = between(0.5, 2)
    
    def on_start(self):
        """Login for API access"""
        payload = {
            "username": "api-user@example.com",
            "password": "api-test-password"  # Update with actual credentials
        }
        self.client.post("/auth/login", data=payload, name="api_login")
    
    @task(3)
    def api_dashboard_data(self):
        """High-frequency dashboard data requests"""
        self.client.get("/api/dashboard/data", name="api_dashboard_data")
        
    @task(2) 
    def api_inventory_search(self):
        """Search inventory via API"""
        search_terms = ["oil", "butter", "extract", "jar", "bottle"]
        term = random.choice(search_terms)
        self.client.get(f"/api/inventory/search?q={term}", name="api_inventory_search")
        
    @task(2)
    def api_bulk_operations(self):
        """Bulk inventory operations"""
        payload = {
            "items": [
                {"id": random.randint(1, 100), "quantity": random.randint(1, 50)}
                for _ in range(5)
            ]
        }
        self.client.post("/api/inventory/bulk-update", 
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        name="api_bulk_update")
        
    @task(1)
    def api_export_data(self):
        """Data export requests"""
        formats = ["csv", "json"] 
        fmt = random.choice(formats)
        self.client.get(f"/api/export/inventory?format={fmt}", name="api_export")

class AdminUser(HttpUser):
    """Admin performing management operations"""
    weight = 1
    wait_time = between(3, 10)
    
    def on_start(self):
        """Login as admin"""
        payload = {
            "username": "admin@example.com",
            "password": "admin-password"  # Update with actual credentials  
        }
        self.client.post("/auth/login", data=payload, name="admin_login")
        
    @task(2)
    def view_admin_dashboard(self):
        self.client.get("/admin/dashboard", name="admin_dashboard")
        
    @task(1) 
    def view_user_management(self):
        self.client.get("/organization/dashboard", name="user_management")
        
    @task(1)
    def view_billing_status(self):
        self.client.get("/billing/status", name="billing_status")
        
    @task(1)
    def system_statistics(self):
        """View system performance metrics"""
        self.client.get("/admin/statistics", name="admin_statistics")

# Test scenarios for different load patterns
class BurstTrafficUser(HttpUser):
    """Simulates burst traffic patterns"""
    weight = 1
    wait_time = between(0.1, 1)  # Very aggressive
    
    @task
    def rapid_requests(self):
        """Rapid-fire requests to test rate limiting"""
        endpoints = ["/", "/user_dashboard", "/inventory/list", "/products/list"]
        endpoint = random.choice(endpoints)
        self.client.get(endpoint, name="burst_request")


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
        self.client.get("/library/global_items", name="global_library")
    
    @task(1)
    def attempt_signup(self):
        """Simulate signup page visits."""
        self.client.get("/auth/signup", name="signup_page")

class AuthenticatedUser(HttpUser):
    """Authenticated user performing typical app operations."""
    
    wait_time = between(3, 12)
    weight = 1  # 25% of traffic
    
    def on_start(self):
        """Login before starting tasks."""
        # Replace with actual test credentials
        payload = {
            "username": "loadtest@example.com",
            "password": "replace-me"
        }
        response = self.client.post("/auth/login", data=payload, name="login")
        if response.status_code != 200:
            print(f"Login failed: {response.status_code}")
    
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

class AdminUser(AuthenticatedUser):
    """Admin user performing administrative tasks."""
    
    wait_time = between(5, 20)
    weight = 0.1  # 2.5% of traffic
    
    def on_start(self):
        """Login as admin."""
        payload = {
            "username": "admin@example.com", 
            "password": "replace-me"
        }
        self.client.post("/auth/login", data=payload, name="admin_login")
    
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

class HighFrequencyUser(HttpUser):
    """Simulates rapid API usage patterns."""
    
    wait_time = between(0.5, 2)
    weight = 0.5  # 12.5% of traffic
    
    def on_start(self):
        """Quick login for API-like usage."""
        payload = {"username": "api@example.com", "password": "replace-me"}
        self.client.post("/auth/login", data=payload, name="api_login")
    
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

if __name__ == "__main__":
    print("Load test scenarios available:")
    print("- AnonymousUser: Public browsing (75% weight)")
    print("- AuthenticatedUser: Logged-in usage (25% weight)")  
    print("- AdminUser: Administrative tasks (2.5% weight)")
    print("- HighFrequencyUser: Rapid API usage (12.5% weight)")
    print("- StressTest: High-intensity testing")

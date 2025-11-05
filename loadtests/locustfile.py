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


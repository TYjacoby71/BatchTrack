"""Anonymous browsing load tests."""

import random

from locust import HttpUser, task, between

from loadtests.common import GLOBAL_ITEM_SEARCH_TERMS, LOCUST_ENABLE_BROWSE_USERS


class AnonymousUser(HttpUser):
    """Anonymous user browsing public content only."""

    abstract = not LOCUST_ENABLE_BROWSE_USERS
    wait_time = between(4, 12)
    weight = 1

    @task(5)
    def view_homepage(self):
        """Load homepage."""
        self.client.get("/", name="homepage")

    @task(3)
    def view_tools_index(self):
        """Browse tools index page."""
        self.client.get("/tools/", name="tools_index")

    @task(2)
    def view_global_items(self):
        """Browse global items library."""
        self.client.get("/global-items", name="global_items")

    @task(2)
    def search_public_global_items(self):
        """Exercise the public global item search endpoint."""
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        params = {"q": query, "type": "ingredient", "group": "ingredient"}
        self.client.get(
            "/api/public/global-items/search",
            params=params,
            name="public_global_item_search",
        )

    @task(1)
    def view_signup(self):
        """View signup page."""
        self.client.get("/auth/signup", name="signup_page")

    @task(1)
    def view_public_units(self):
        """Hit public units endpoint."""
        self.client.get("/api/public/units", name="public_units")

"""Recipe and batch browsing load tests."""

import random

from locust import task, between

from loadtests.common import (
    BaseAuthenticatedUser,
    GLOBAL_ITEM_SEARCH_TERMS,
    LOCUST_DASHBOARD_PATH,
    LOCUST_ENABLE_BROWSE_USERS,
)


class RecipeOpsUser(BaseAuthenticatedUser):
    """Recipe planning + batch workflow."""

    abstract = not LOCUST_ENABLE_BROWSE_USERS
    wait_time = between(6, 14)
    weight = 4

    @task(7)
    def view_dashboard(self):
        self._authed_get(LOCUST_DASHBOARD_PATH, name="user_dashboard")

    @task(6)
    def view_recipes_list(self):
        self._authed_get("/recipes/", name="recipes_list")

    @task(4)
    def view_recipe_detail(self):
        recipe_id = self._pick_id(self._get_recipe_ids())
        if not recipe_id:
            return
        self._authed_get(f"/recipes/{recipe_id}/view", name="recipe_detail")

    @task(3)
    def view_batches_list(self):
        self._authed_get("/batches/", name="batches_list")

    @task(2)
    def view_global_items(self):
        self._authed_get("/global-items", name="global_items")

    @task(2)
    def search_global_items(self):
        query = random.choice(GLOBAL_ITEM_SEARCH_TERMS)
        params = {"q": query, "type": "ingredient", "group": "ingredient"}
        self._authed_get(
            "/api/ingredients/global-items/search",
            params=params,
            name="auth_global_item_search",
        )

    @task(1)
    def view_batch_available_ingredients(self):
        recipe_id = self._pick_id(self._get_recipe_ids())
        if not recipe_id:
            return
        self._authed_get(
            f"/batches/api/available-ingredients/{recipe_id}",
            name="batch_available_ingredients",
        )

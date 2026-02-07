"""Locust Load Testing Configuration - Production Mix."""

from loadtests.common import _sanitize_cli_args
from loadtests.users.anonymous import AnonymousUser
from loadtests.users.batch_workflow import BatchWorkflowUser
from loadtests.users.inventory_ops import InventoryOpsUser
from loadtests.users.product_ops import ProductOpsUser
from loadtests.users.recipe_ops import RecipeOpsUser


_sanitize_cli_args()


user_classes = [
    BatchWorkflowUser,
    RecipeOpsUser,
    InventoryOpsUser,
    ProductOpsUser,
    AnonymousUser,
]

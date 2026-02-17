"""
Statistics Service Package

Modular statistics system following production_planning pattern.
Coordinates between different statistical domains.
"""

from ._batch_stats import BatchStatisticsService
from ._core import StatisticsService
from ._inventory_stats import InventoryStatisticsService
from ._recipe_stats import RecipeStatisticsService
from ._reporting import ReportingService
from .analytics_service import AnalyticsDataService
from .catalog import AnalyticsCatalogError, AnalyticsCatalogService

__all__ = [
    "StatisticsService",
    "BatchStatisticsService",
    "RecipeStatisticsService",
    "InventoryStatisticsService",
    "ReportingService",
    "AnalyticsCatalogService",
    "AnalyticsCatalogError",
    "AnalyticsDataService",
]

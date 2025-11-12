"""
Statistics Service Package

Modular statistics system following production_planning pattern.
Coordinates between different statistical domains.
"""

from ._core import StatisticsService
from ._batch_stats import BatchStatisticsService
from ._recipe_stats import RecipeStatisticsService
from ._inventory_stats import InventoryStatisticsService
from ._reporting import ReportingService
from .catalog import AnalyticsCatalogService, AnalyticsCatalogError
from .analytics_service import AnalyticsDataService

__all__ = [
    'StatisticsService',
    'BatchStatisticsService', 
    'RecipeStatisticsService',
    'InventoryStatisticsService',
    'ReportingService',
    'AnalyticsCatalogService',
    'AnalyticsCatalogError',
    'AnalyticsDataService'
]
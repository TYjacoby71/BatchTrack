"""Statistics models for reporting and leaderboards.

Synopsis:
Tracks user and organization stats for reporting and badges.

Glossary:
- UserStats: Per-user counts used for performance tracking.
- OrganizationStats: Aggregated org counts for dashboards.
"""

from datetime import datetime, timedelta
from sqlalchemy import func, extract
from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils

class UserStats(ScopedModelMixin, db.Model):
    """Track user statistics for reporting and gamification"""
    __tablename__ = 'user_stats'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

    # Batch statistics
    total_batches = db.Column(db.Integer, default=0)
    completed_batches = db.Column(db.Integer, default=0)
    failed_batches = db.Column(db.Integer, default=0)
    cancelled_batches = db.Column(db.Integer, default=0)

    # Recipe statistics
    total_recipes = db.Column(db.Integer, default=0)
    recipes_created = db.Column(db.Integer, default=0)
    master_recipes_created = db.Column(db.Integer, default=0)
    variation_recipes_created = db.Column(db.Integer, default=0)
    tests_created = db.Column(db.Integer, default=0)

    # Inventory statistics
    inventory_adjustments = db.Column(db.Integer, default=0)
    inventory_items_created = db.Column(db.Integer, default=0)

    # Product statistics
    products_created = db.Column(db.Integer, default=0)
    total_products_made = db.Column(db.Float, default=0.0)

    # Time tracking
    last_updated = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Relationships
    user = db.relationship('User', backref='stats')

    @classmethod
    def get_or_create(cls, user_id, organization_id):
        """Get existing stats or create new ones"""
        stats = cls.query.filter_by(user_id=user_id, organization_id=organization_id).first()
        if not stats:
            stats = cls(user_id=user_id, organization_id=organization_id)
            db.session.add(stats)
            db.session.commit()
        return stats

    def refresh_from_database(self):
        """Recalculate all statistics from actual data"""
        from .models import Batch, Recipe, InventoryItem, InventoryHistory
        from .product import Product

        # Batch statistics - use explicit column references for consistency
        user_batches = Batch.query.filter(
            Batch.created_by == self.user_id,
            Batch.organization_id == self.organization_id
        )
        self.total_batches = user_batches.count()
        self.completed_batches = user_batches.filter(Batch.status == 'completed').count()
        self.failed_batches = user_batches.filter(Batch.status == 'failed').count()
        self.cancelled_batches = user_batches.filter(Batch.status == 'cancelled').count()

        # Recipe statistics - use explicit column references for consistency
        user_recipes = Recipe.query.filter(
            Recipe.created_by == self.user_id,
            Recipe.organization_id == self.organization_id
        )
        self.total_recipes = user_recipes.count()
        self.recipes_created = user_recipes.count()
        self.master_recipes_created = user_recipes.filter(
            Recipe.is_master.is_(True),
            Recipe.test_sequence.is_(None),
        ).count()
        self.variation_recipes_created = user_recipes.filter(
            Recipe.is_master.is_(False),
            Recipe.test_sequence.is_(None),
        ).count()
        self.tests_created = user_recipes.filter(
            Recipe.test_sequence.is_not(None),
        ).count()

        # Inventory statistics - use explicit column references for consistency
        user_inventory = InventoryItem.query.filter(
            InventoryItem.created_by == self.user_id,
            InventoryItem.organization_id == self.organization_id
        )
        self.inventory_items_created = user_inventory.count()

        user_adjustments = InventoryHistory.query.filter(
            InventoryHistory.created_by == self.user_id,
            InventoryHistory.organization_id == self.organization_id
        )
        self.inventory_adjustments = user_adjustments.count()

        # Product statistics - use explicit column references for consistency
        user_products = Product.query.filter(
            Product.created_by == self.user_id,
            Product.organization_id == self.organization_id
        )
        self.products_created = user_products.count()

        self.last_updated = TimezoneUtils.utc_now()
        db.session.commit()

    def get_monthly_stats(self, year=None, month=None):
        """Get statistics for a specific month"""
        if not year or not month:
            now = TimezoneUtils.utc_now()
            if not year:
                year = now.year
            if not month:
                month = now.month

        from .models import Batch

        monthly_batches = Batch.query.filter(
            Batch.created_by == self.user_id,
            Batch.organization_id == self.organization_id,
            extract('year', Batch.started_at) == year,
            extract('month', Batch.started_at) == month
        ).count()

        return {
            'year': year,
            'month': month,
            'batches': monthly_batches,
            'user_id': self.user_id
        }

class OrganizationStats(db.Model):
    """Track organization-wide statistics"""
    __tablename__ = 'organization_stats'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False, unique=True)

    # Batch statistics
    total_batches = db.Column(db.Integer, default=0)
    completed_batches = db.Column(db.Integer, default=0)
    failed_batches = db.Column(db.Integer, default=0)
    cancelled_batches = db.Column(db.Integer, default=0)

    # User statistics
    total_users = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)

    # Recipe statistics
    total_recipes = db.Column(db.Integer, default=0)
    total_master_recipes = db.Column(db.Integer, default=0)
    total_variation_recipes = db.Column(db.Integer, default=0)
    total_test_recipes = db.Column(db.Integer, default=0)

    # Inventory statistics
    total_inventory_items = db.Column(db.Integer, default=0)
    total_inventory_value = db.Column(db.Float, default=0.0)

    # Product statistics
    total_products = db.Column(db.Integer, default=0)
    total_products_made = db.Column(db.Float, default=0.0)

    # Time tracking
    last_updated = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Relationships
    organization = db.relationship('Organization', backref='stats')

    @classmethod
    def get_or_create(cls, organization_id):
        """Get existing stats or create new ones"""
        stats = cls.query.filter_by(organization_id=organization_id).first()
        if not stats:
            stats = cls(organization_id=organization_id)
            db.session.add(stats)
            db.session.commit()
        return stats

    def refresh_from_database(self):
        """Refresh statistics from current database state"""
        try:
            from .models import Batch, User, InventoryItem, Recipe
            from .product import Product

            # Batch statistics - use direct organization_id filtering since we're not in a request context
            # Note: We can't use Batch.scoped() here because it relies on current_user being available
            batch_query = Batch.query.filter(Batch.organization_id == self.organization_id)
            self.total_batches = batch_query.count()
            self.completed_batches = batch_query.filter(Batch.status == 'completed').count()
            self.failed_batches = batch_query.filter(Batch.status == 'failed').count()
            self.cancelled_batches = batch_query.filter(Batch.status == 'cancelled').count()

            # User statistics - exclude developers from organization counts
            self.total_users = User.query.filter(
                User.organization_id == self.organization_id,
                User.user_type != 'developer'
            ).count()
            self.active_users = User.query.filter(
                User.organization_id == self.organization_id,
                User.is_active == True,
                User.user_type != 'developer'
            ).count()

            # Recipe statistics - scoped by organization
            self.total_recipes = Recipe.query.filter(Recipe.organization_id == self.organization_id).count()
            self.total_master_recipes = Recipe.query.filter(
                Recipe.organization_id == self.organization_id,
                Recipe.is_master.is_(True),
                Recipe.test_sequence.is_(None),
                Recipe.is_archived.is_(False),
                Recipe.is_current.is_(True),
            ).count()
            self.total_variation_recipes = Recipe.query.filter(
                Recipe.organization_id == self.organization_id,
                Recipe.is_master.is_(False),
                Recipe.test_sequence.is_(None),
                Recipe.is_archived.is_(False),
                Recipe.is_current.is_(True),
            ).count()
            self.total_test_recipes = Recipe.query.filter(
                Recipe.organization_id == self.organization_id,
                Recipe.test_sequence.is_not(None),
                Recipe.is_archived.is_(False),
            ).count()

            # Inventory statistics - already scoped by organization
            self.total_inventory_items = InventoryItem.query.filter(InventoryItem.organization_id == self.organization_id).count()
            total_value = db.session.query(func.sum(InventoryItem.quantity * InventoryItem.cost_per_unit))\
                .filter(InventoryItem.organization_id == self.organization_id).scalar()
            self.total_inventory_value = total_value or 0.0

            # Product statistics - already scoped by organization
            self.total_products = Product.query.filter(Product.organization_id == self.organization_id).count()
            # Note: ProductInventory calculation needs to be implemented when ProductInventory model is available

            self.last_updated = TimezoneUtils.utc_now()
            db.session.commit()

        except Exception as e:
            print(f"Error refreshing organization stats: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            # Set default values if refresh fails
            self.total_batches = 0
            self.completed_batches = 0
            self.failed_batches = 0
            self.cancelled_batches = 0

    def get_monthly_stats(self, year=None, month=None):
        """Get statistics for a specific month"""
        if not year or not month:
            now = TimezoneUtils.utc_now()
            if not year:
                year = now.year
            if not month:
                month = now.month

        from .models import Batch

        monthly_batches = Batch.query.filter(
            Batch.organization_id == self.organization_id,
            extract('year', Batch.started_at) == year,
            extract('month', Batch.started_at) == month
        ).count()

        return {
            'year': year,
            'month': month,
            'batches': monthly_batches,
            'organization_id': self.organization_id
        }

class Leaderboard:
    """Service class for generating leaderboards and competitions"""

    @staticmethod
    def get_top_users_by_batches(organization_id=None, time_period='all_time', limit=10):
        """Get top users by batch count"""
        from .models import User

        query = db.session.query(
            UserStats.user_id,
            User.username,
            User.first_name,
            User.last_name,
            UserStats.total_batches
        ).join(User, UserStats.user_id == User.id)

        if organization_id:
            query = query.filter(UserStats.organization_id == organization_id)

        if time_period == 'monthly':
            # For monthly, we'd need to calculate from actual batch data
            # This is a simplified version
            pass

        return query.order_by(UserStats.total_batches.desc()).limit(limit).all()

    @staticmethod
    def get_top_organizations_by_batches(time_period='all_time', limit=10):
        """Get top organizations by batch count"""
        from .models import Organization

        query = db.session.query(
            OrganizationStats.organization_id,
            Organization.name,
            OrganizationStats.total_batches
        ).join(Organization, OrganizationStats.organization_id == Organization.id)

        return query.order_by(OrganizationStats.total_batches.desc()).limit(limit).all()

    @staticmethod
    def get_monthly_batch_leaders(year=None, month=None, limit=10):
        """Get monthly batch leaders across all organizations"""
        if not year or not month:
            now = TimezoneUtils.utc_now()
            if not year:
                year = now.year
            if not month:
                month = now.month

        from .models import Batch, User, Organization

        # Get monthly batch counts by user
        monthly_stats = db.session.query(
            Batch.created_by,
            User.username,
            User.first_name,
            User.last_name,
            Organization.name.label('organization_name'),
            func.count(Batch.id).label('batch_count')
        ).join(User, Batch.created_by == User.id)\
         .join(Organization, Batch.organization_id == Organization.id)\
         .filter(
            extract('year', Batch.started_at) == year,
            extract('month', Batch.started_at) == month
        ).group_by(Batch.created_by, User.username, User.first_name, User.last_name, Organization.name)\
         .order_by(func.count(Batch.id).desc())\
         .limit(limit).all()

        return monthly_stats


class BatchStats(ScopedModelMixin, db.Model):
    """Track detailed statistics for each batch"""
    __tablename__ = 'batch_stats'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False, unique=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

    # Planning vs Actual Efficiency
    planned_fill_efficiency = db.Column(db.Float, default=0.0)  # From production planning
    actual_fill_efficiency = db.Column(db.Float, default=0.0)   # From completed batch
    efficiency_variance = db.Column(db.Float, default=0.0)      # Difference between planned/actual

    # Yield Tracking
    planned_yield_amount = db.Column(db.Float, default=0.0)
    planned_yield_unit = db.Column(db.String(50))
    actual_yield_amount = db.Column(db.Float, default=0.0)
    actual_yield_unit = db.Column(db.String(50))
    yield_variance_percentage = db.Column(db.Float, default=0.0)

    # Cost Tracking
    planned_ingredient_cost = db.Column(db.Float, default=0.0)
    actual_ingredient_cost = db.Column(db.Float, default=0.0)
    planned_container_cost = db.Column(db.Float, default=0.0)
    actual_container_cost = db.Column(db.Float, default=0.0)
    total_planned_cost = db.Column(db.Float, default=0.0)
    total_actual_cost = db.Column(db.Float, default=0.0)
    cost_variance_percentage = db.Column(db.Float, default=0.0)

    # Spoilage & Waste Tracking
    ingredient_spoilage_cost = db.Column(db.Float, default=0.0)
    product_spoilage_cost = db.Column(db.Float, default=0.0)
    waste_percentage = db.Column(db.Float, default=0.0)

    # Time Tracking
    planned_duration_minutes = db.Column(db.Integer, default=0)
    actual_duration_minutes = db.Column(db.Integer, default=0)
    duration_variance_percentage = db.Column(db.Float, default=0.0)

    # Status & Timestamps
    batch_status = db.Column(db.String(50))  # completed, failed, cancelled
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    completed_at = db.Column(db.DateTime)
    last_updated = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Relationships
    batch = db.relationship('Batch', backref='stats')
    user = db.relationship('User')
    recipe = db.relationship('Recipe')

    @classmethod
    def create_from_planned_batch(cls, batch_id, planned_efficiency, planned_yield, planned_costs):
        """Create batch stats from production planning data"""
        from ..models import Batch
        from ..extensions import db
        batch = db.session.get(Batch, batch_id)
        if not batch:
            return None

        stats = cls(
            batch_id=batch_id,
            organization_id=batch.organization_id,
            user_id=batch.created_by,
            recipe_id=batch.recipe_id,
            planned_fill_efficiency=planned_efficiency,
            planned_yield_amount=planned_yield.get('amount', 0),
            planned_yield_unit=planned_yield.get('unit', ''),
            planned_ingredient_cost=planned_costs.get('ingredient_cost', 0),
            planned_container_cost=planned_costs.get('container_cost', 0),
            total_planned_cost=planned_costs.get('total_cost', 0),
            batch_status='planned'
        )
        db.session.add(stats)
        return stats

    def update_actual_data(self, actual_efficiency, actual_yield, actual_costs):
        """Update with actual completion data"""
        self.actual_fill_efficiency = actual_efficiency
        self.actual_yield_amount = actual_yield.get('amount', 0)
        self.actual_yield_unit = actual_yield.get('unit', '')
        self.actual_ingredient_cost = actual_costs.get('ingredient_cost', 0)
        self.actual_container_cost = actual_costs.get('container_cost', 0)
        self.total_actual_cost = actual_costs.get('total_cost', 0)
        self.completed_at = TimezoneUtils.utc_now()

        # Calculate variances
        if self.planned_fill_efficiency > 0:
            self.efficiency_variance = self.actual_fill_efficiency - self.planned_fill_efficiency
        
        if self.planned_yield_amount > 0:
            self.yield_variance_percentage = ((self.actual_yield_amount - self.planned_yield_amount) / self.planned_yield_amount) * 100
        
        if self.total_planned_cost > 0:
            self.cost_variance_percentage = ((self.total_actual_cost - self.total_planned_cost) / self.total_planned_cost) * 100

        self.last_updated = TimezoneUtils.utc_now()


class RecipeStats(ScopedModelMixin, db.Model):
    """Track performance statistics for recipes across all batches"""
    __tablename__ = 'recipe_stats'

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False, unique=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

    # Usage Statistics
    total_batches_planned = db.Column(db.Integer, default=0)
    total_batches_completed = db.Column(db.Integer, default=0)
    total_batches_failed = db.Column(db.Integer, default=0)
    success_rate_percentage = db.Column(db.Float, default=0.0)

    # Efficiency Averages
    avg_fill_efficiency = db.Column(db.Float, default=0.0)
    avg_yield_variance = db.Column(db.Float, default=0.0)
    avg_cost_variance = db.Column(db.Float, default=0.0)

    # Cost Analysis
    avg_cost_per_batch = db.Column(db.Float, default=0.0)
    avg_cost_per_unit = db.Column(db.Float, default=0.0)
    total_spoilage_cost = db.Column(db.Float, default=0.0)

    # Container Usage
    most_used_container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'))
    avg_containers_needed = db.Column(db.Float, default=0.0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    last_batch_date = db.Column(db.DateTime)
    last_updated = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Relationships
    recipe = db.relationship('Recipe', backref='stats')
    most_used_container = db.relationship('InventoryItem', foreign_keys=[most_used_container_id])

    @classmethod
    def get_or_create(cls, recipe_id, organization_id):
        """Get existing stats or create new ones"""
        stats = cls.query.filter_by(recipe_id=recipe_id, organization_id=organization_id).first()
        if not stats:
            stats = cls(recipe_id=recipe_id, organization_id=organization_id)
            db.session.add(stats)
        return stats

    def recalculate_from_batches(self):
        """Recalculate all stats from completed batch data"""
        completed_batches = BatchStats.query.filter(
            BatchStats.recipe_id == self.recipe_id,
            BatchStats.organization_id == self.organization_id,
            BatchStats.batch_status == 'completed'
        ).all()

        if not completed_batches:
            return

        # Usage stats
        self.total_batches_completed = len(completed_batches)
        failed_batches = BatchStats.query.filter(
            BatchStats.recipe_id == self.recipe_id,
            BatchStats.batch_status == 'failed'
        ).count()
        
        total = self.total_batches_completed + failed_batches
        if total > 0:
            self.success_rate_percentage = (self.total_batches_completed / total) * 100

        # Averages
        if completed_batches:
            self.avg_fill_efficiency = sum(b.actual_fill_efficiency for b in completed_batches) / len(completed_batches)
            self.avg_yield_variance = sum(b.yield_variance_percentage for b in completed_batches) / len(completed_batches)
            self.avg_cost_variance = sum(b.cost_variance_percentage for b in completed_batches) / len(completed_batches)
            self.avg_cost_per_batch = sum(b.total_actual_cost for b in completed_batches) / len(completed_batches)
            self.total_spoilage_cost = sum(b.ingredient_spoilage_cost + b.product_spoilage_cost for b in completed_batches)

        self.last_updated = TimezoneUtils.utc_now()


class InventoryEfficiencyStats(ScopedModelMixin, db.Model):
    """Track inventory usage efficiency and spoilage"""
    __tablename__ = 'inventory_efficiency_stats'

    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False, unique=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

    # Usage Statistics
    total_purchased_quantity = db.Column(db.Float, default=0.0)
    total_used_quantity = db.Column(db.Float, default=0.0)
    total_spoiled_quantity = db.Column(db.Float, default=0.0)
    total_wasted_quantity = db.Column(db.Float, default=0.0)  # damaged, trash, etc.

    # Efficiency Metrics
    utilization_percentage = db.Column(db.Float, default=0.0)  # used / purchased
    spoilage_rate = db.Column(db.Float, default=0.0)          # spoiled / purchased
    waste_rate = db.Column(db.Float, default=0.0)             # wasted / purchased

    # Cost Impact
    total_purchase_cost = db.Column(db.Float, default=0.0)
    total_spoilage_cost = db.Column(db.Float, default=0.0)
    total_waste_cost = db.Column(db.Float, default=0.0)
    effective_cost_per_unit = db.Column(db.Float, default=0.0)  # Adjusted for spoilage/waste

    # Freshness Tracking
    avg_days_to_use = db.Column(db.Float, default=0.0)
    avg_days_to_spoil = db.Column(db.Float, default=0.0)
    freshness_score = db.Column(db.Float, default=100.0)  # 0-100 based on usage patterns

    # Timestamps
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    last_updated = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Relationships
    inventory_item = db.relationship('InventoryItem', backref='efficiency_stats')

    def recalculate_efficiency(self):
        """Recalculate all efficiency metrics"""
        if self.total_purchased_quantity > 0:
            self.utilization_percentage = (self.total_used_quantity / self.total_purchased_quantity) * 100
            self.spoilage_rate = (self.total_spoiled_quantity / self.total_purchased_quantity) * 100
            self.waste_rate = (self.total_wasted_quantity / self.total_purchased_quantity) * 100
            
            # Effective cost includes spoilage and waste impact
            if self.total_used_quantity > 0:
                self.effective_cost_per_unit = self.total_purchase_cost / self.total_used_quantity
        
        self.last_updated = TimezoneUtils.utc_now()


class OrganizationLeaderboardStats(db.Model):
    """Track organization-level statistics for leaderboards"""
    __tablename__ = 'organization_leaderboard_stats'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False, unique=True)

    # Recipe Stats
    total_recipes = db.Column(db.Integer, default=0)
    active_recipes_count = db.Column(db.Integer, default=0)  # Used in last 30 days
    most_popular_recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'))
    avg_recipe_success_rate = db.Column(db.Float, default=0.0)

    # Production Stats
    total_batches_completed = db.Column(db.Integer, default=0)
    avg_batch_completion_time = db.Column(db.Float, default=0.0)  # hours
    avg_fill_efficiency = db.Column(db.Float, default=0.0)
    highest_fill_efficiency = db.Column(db.Float, default=0.0)

    # Team Stats
    active_users_count = db.Column(db.Integer, default=0)
    most_productive_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    avg_batches_per_user = db.Column(db.Float, default=0.0)
    most_testing_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    most_tests_created = db.Column(db.Integer, default=0)

    # Container Usage
    most_used_container_size = db.Column(db.Float, default=0.0)
    most_used_container_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'))

    # Cost Efficiency
    avg_cost_per_batch = db.Column(db.Float, default=0.0)
    lowest_cost_per_unit = db.Column(db.Float, default=0.0)
    highest_cost_per_unit = db.Column(db.Float, default=0.0)

    # Inventory Efficiency
    avg_spoilage_rate = db.Column(db.Float, default=0.0)
    inventory_turnover_rate = db.Column(db.Float, default=0.0)

    # Community Stats (for future features)
    recipes_shared_count = db.Column(db.Integer, default=0)
    recipes_sold_count = db.Column(db.Integer, default=0)
    community_rating = db.Column(db.Float, default=0.0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    last_updated = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Relationships
    organization = db.relationship('Organization')
    most_popular_recipe = db.relationship('Recipe', foreign_keys=[most_popular_recipe_id])
    most_productive_user = db.relationship('User', foreign_keys=[most_productive_user_id])
    most_testing_user = db.relationship('User', foreign_keys=[most_testing_user_id])
    most_used_container = db.relationship('InventoryItem', foreign_keys=[most_used_container_id])

    @classmethod
    def get_or_create(cls, organization_id):
        """Get existing stats or create new ones"""
        stats = cls.query.filter_by(organization_id=organization_id).first()
        if not stats:
            stats = cls(organization_id=organization_id)
            db.session.add(stats)
        return stats


class InventoryChangeLog(ScopedModelMixin, db.Model):
    """Log all inventory changes with detailed categorization"""
    __tablename__ = 'inventory_change_log'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # Change Details
    change_type = db.Column(db.String(50), nullable=False)  # purchase, use, spoilage, waste, damage, theft, etc.
    change_category = db.Column(db.String(50), nullable=False)  # additive, deductive, correction, transfer
    quantity_change = db.Column(db.Float, nullable=False)
    cost_impact = db.Column(db.Float, default=0.0)

    # Context
    related_batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'))
    related_lot_id = db.Column(db.Integer, db.ForeignKey('inventory_lot.id'))
    reason_code = db.Column(db.String(100))  # expired, damaged, customer_complaint, etc.
    notes = db.Column(db.Text)

    # Freshness Context (if applicable)
    item_age_days = db.Column(db.Integer)  # Age of item when changed
    expiration_date = db.Column(db.Date)
    freshness_score = db.Column(db.Float)  # 0-100

    # Timestamps
    change_date = db.Column(db.DateTime, default=TimezoneUtils.utc_now)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now)

    # Relationships
    inventory_item = db.relationship('InventoryItem')
    user = db.relationship('User')
    related_batch = db.relationship('Batch')
    related_lot = db.relationship('InventoryLot')

    @classmethod
    def log_change(cls, inventory_item_id, organization_id, change_type, quantity_change, **kwargs):
        """Log an inventory change with context"""
        log_entry = cls(
            inventory_item_id=inventory_item_id,
            organization_id=organization_id,
            change_type=change_type,
            quantity_change=quantity_change,
            **kwargs
        )
        db.session.add(log_entry)
        return log_entry
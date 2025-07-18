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

        # Batch statistics
        user_batches = Batch.query.filter_by(created_by=self.user_id, organization_id=self.organization_id)
        self.total_batches = user_batches.count()
        self.completed_batches = user_batches.filter_by(status='completed').count()
        self.failed_batches = user_batches.filter_by(status='failed').count()
        self.cancelled_batches = user_batches.filter_by(status='cancelled').count()

        # Recipe statistics
        user_recipes = Recipe.query.filter_by(created_by=self.user_id, organization_id=self.organization_id)
        self.total_recipes = user_recipes.count()
        self.recipes_created = user_recipes.count()

        # Inventory statistics
        user_inventory = InventoryItem.query.filter_by(created_by=self.user_id, organization_id=self.organization_id)
        self.inventory_items_created = user_inventory.count()

        user_adjustments = InventoryHistory.query.filter_by(created_by=self.user_id, organization_id=self.organization_id)
        self.inventory_adjustments = user_adjustments.count()

        # Product statistics
        user_products = Product.query.filter_by(created_by=self.user_id, organization_id=self.organization_id)
        self.products_created = user_products.count()

        self.last_updated = TimezoneUtils.utc_now()
        db.session.commit()

    def get_monthly_stats(self, year=None, month=None):
        """Get statistics for a specific month"""
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month

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
            from .models import Batch, User, InventoryItem, Product, Recipe
            
            # Batch statistics - scoped by organization
            batch_query = Batch.query.filter_by(organization_id=self.organization_id)
            self.total_batches = batch_query.count()
            self.completed_batches = batch_query.filter_by(status='completed').count()
            self.failed_batches = batch_query.filter_by(status='failed').count()
            self.cancelled_batches = batch_query.filter_by(status='cancelled').count()

            # User statistics - exclude developers from organization counts
            self.total_users = User.query.filter_by(organization_id=self.organization_id).filter(User.user_type != 'developer').count()
            self.active_users = User.query.filter_by(organization_id=self.organization_id, is_active=True).filter(User.user_type != 'developer').count()

            # Recipe statistics - scoped by organization
            self.total_recipes = Recipe.query.filter_by(organization_id=self.organization_id).count()

            # Inventory statistics - already scoped by organization
            self.total_inventory_items = InventoryItem.query.filter_by(organization_id=self.organization_id).count()
            total_value = db.session.query(func.sum(InventoryItem.quantity * InventoryItem.cost_per_unit))\
                .filter_by(organization_id=self.organization_id).scalar()
            self.total_inventory_value = total_value or 0.0

            # Product statistics - already scoped by organization
            self.total_products = Product.query.filter_by(organization_id=self.organization_id).count()
            # Note: ProductInventory calculation needs to be implemented when ProductInventory model is available

            self.last_updated = TimezoneUtils.utc_now()
            db.session.commit()
            
        except Exception as e:
            print(f"Error refreshing organization stats: {e}")
            # Set default values if refresh fails
            self.total_batches = 0
            self.completed_batches = 0
            self.failed_batches = 0
            self.cancelled_batches = 0

    def get_monthly_stats(self, year=None, month=None):
        """Get statistics for a specific month"""
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month

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
        query = db.session.query(
            OrganizationStats.organization_id,
            Organization.name,
            OrganizationStats.total_batches
        ).join(Organization, OrganizationStats.organization_id == Organization.id)

        return query.order_by(OrganizationStats.total_batches.desc()).limit(limit).all()

    @staticmethod
    def get_monthly_batch_leaders(year=None, month=None, limit=10):
        """Get monthly batch leaders across all organizations"""
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month

        from .models import Batch

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
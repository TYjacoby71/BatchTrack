
from app.models.statistics import UserStats, OrganizationStats
from app.extensions import db
from flask_login import current_user

class StatisticsService:
    """Service for updating statistics in real-time"""
    
    @staticmethod
    def increment_user_batch_count(user_id, organization_id, status='started'):
        """Increment batch count for user"""
        try:
            user_stats = UserStats.get_or_create(user_id, organization_id)
            org_stats = OrganizationStats.get_or_create(organization_id)
            
            # Update user stats
            user_stats.total_batches += 1
            
            # Update organization stats
            org_stats.total_batches += 1
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating batch statistics: {e}")
    
    @staticmethod
    def update_batch_status(user_id, organization_id, old_status, new_status):
        """Update batch status statistics"""
        try:
            user_stats = UserStats.get_or_create(user_id, organization_id)
            org_stats = OrganizationStats.get_or_create(organization_id)
            
            # Decrement old status count (if needed)
            if old_status == 'completed':
                user_stats.completed_batches = max(0, user_stats.completed_batches - 1)
                org_stats.completed_batches = max(0, org_stats.completed_batches - 1)
            elif old_status == 'failed':
                user_stats.failed_batches = max(0, user_stats.failed_batches - 1)
                org_stats.failed_batches = max(0, org_stats.failed_batches - 1)
            elif old_status == 'cancelled':
                user_stats.cancelled_batches = max(0, user_stats.cancelled_batches - 1)
                org_stats.cancelled_batches = max(0, org_stats.cancelled_batches - 1)
            
            # Increment new status count
            if new_status == 'completed':
                user_stats.completed_batches += 1
                org_stats.completed_batches += 1
            elif new_status == 'failed':
                user_stats.failed_batches += 1
                org_stats.failed_batches += 1
            elif new_status == 'cancelled':
                user_stats.cancelled_batches += 1
                org_stats.cancelled_batches += 1
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating batch status statistics: {e}")
    
    @staticmethod
    def increment_recipe_count(user_id, organization_id):
        """Increment recipe count for user and organization"""
        try:
            user_stats = UserStats.get_or_create(user_id, organization_id)
            org_stats = OrganizationStats.get_or_create(organization_id)
            
            user_stats.total_recipes += 1
            user_stats.recipes_created += 1
            org_stats.total_recipes += 1
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating recipe statistics: {e}")
    
    @staticmethod
    def increment_inventory_adjustment(user_id, organization_id):
        """Increment inventory adjustment count"""
        try:
            user_stats = UserStats.get_or_create(user_id, organization_id)
            user_stats.inventory_adjustments += 1
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating inventory adjustment statistics: {e}")
    
    @staticmethod
    def increment_inventory_item_count(user_id, organization_id):
        """Increment inventory item count"""
        try:
            user_stats = UserStats.get_or_create(user_id, organization_id)
            org_stats = OrganizationStats.get_or_create(organization_id)
            
            user_stats.inventory_items_created += 1
            org_stats.total_inventory_items += 1
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating inventory item statistics: {e}")
    
    @staticmethod
    def increment_product_count(user_id, organization_id):
        """Increment product count for user and organization"""
        try:
            user_stats = UserStats.get_or_create(user_id, organization_id)
            org_stats = OrganizationStats.get_or_create(organization_id)
            
            user_stats.products_created += 1
            org_stats.total_products += 1
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating product statistics: {e}")
    
    @staticmethod
    def refresh_all_organization_stats(organization_id):
        """Refresh all statistics for an organization"""
        try:
            org_stats = OrganizationStats.get_or_create(organization_id)
            org_stats.refresh_from_database()
            
            # Refresh all user stats for this organization
            from app.models import User
            users = User.query.filter_by(organization_id=organization_id).all()
            for user in users:
                user_stats = UserStats.get_or_create(user.id, organization_id)
                user_stats.refresh_from_database()
                
        except Exception as e:
            print(f"Error refreshing organization statistics: {e}")

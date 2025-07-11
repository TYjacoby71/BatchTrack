
from flask_login import current_user
from ..models import User, Role, Organization, db
from ..utils.permissions import has_permission

class UserTypeManager:
    """Manage user types and role assignments"""
    
    USER_TYPES = {
        'developer': 'developer',
        'organization_owner': 'organization_owner', 
        'team_member': 'manager'  # Default team members get manager role
    }
    
    @staticmethod
    def assign_role_by_user_type(user):
        """Assign appropriate role based on user type and organization subscription"""
        if user.user_type == 'developer':
            role = Role.query.filter_by(name='developer').first()
        elif user.user_type == 'organization_owner':
            role = Role.query.filter_by(name='organization_owner').first()
        else:  # team_member
            # Assign role based on organization subscription
            if user.organization.subscription_tier == 'solo':
                role = Role.query.filter_by(name='operator').first()  # Limited for solo
            else:
                role = Role.query.filter_by(name='manager').first()  # Full access for team/enterprise
        
        if role:
            user.role_id = role.id
            db.session.commit()
        
        return role
    
    @staticmethod
    def can_user_access_feature(feature_name):
        """Check if current user can access a feature based on subscription"""
        if not current_user.is_authenticated:
            return False
        
        # Developers can access everything
        if current_user.user_type == 'developer':
            return True
        
        org_features = current_user.organization.get_subscription_features()
        return feature_name in org_features or 'all_features' in org_features
    
    @staticmethod
    def get_user_type_display_name(user_type):
        """Get human-readable name for user type"""
        names = {
            'developer': 'System Developer',
            'organization_owner': 'Organization Owner',
            'team_member': 'Team Member'
        }
        return names.get(user_type, 'Team Member')
    
    @staticmethod
    def create_organization_with_owner(org_name, owner_username, owner_email, subscription_tier='solo'):
        """Create new organization with owner user"""
        # Create organization
        org = Organization(
            name=org_name,
            subscription_tier=subscription_tier
        )
        db.session.add(org)
        db.session.flush()  # Get org.id
        
        # Create owner user
        owner_role = Role.query.filter_by(name='organization_owner').first()
        owner = User(
            username=owner_username,
            email=owner_email,
            organization_id=org.id,
            is_owner=True,
            user_type='organization_owner',
            role_id=owner_role.id if owner_role else None
        )
        db.session.add(owner)
        db.session.commit()
        
        return org, owner

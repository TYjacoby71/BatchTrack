
from flask_login import current_user

class SubscriptionFeatures:
    """Centralized management of subscription-tier based features"""
    
    # Define all subscription features and their minimum required tier
    FEATURES = {
        # Organization Management
        'organization_dashboard': 'team',
        'user_management': 'team', 
        'custom_roles': 'team',
        'role_permissions': 'team',
        
        # Advanced Production
        'advanced_batch_tracking': 'team',
        'production_analytics': 'team',
        'batch_templates': 'team',
        
        # Integrations (Future)
        'ai_integration': 'enterprise',
        'shopify_integration': 'enterprise', 
        'api_access': 'enterprise',
        'custom_integrations': 'enterprise',
        
        # Premium Features (Future)
        'recipe_purchasing': 'enterprise',
        'marketplace_access': 'enterprise',
        'priority_support': 'team',
        'phone_support': 'enterprise',
        
        # Analytics & Reporting
        'advanced_reports': 'team',
        'export_data': 'team',
        'inventory_analytics': 'team',
        
        # System Features
        'backup_exports': 'team',
        'audit_logs': 'enterprise',
        'compliance_reports': 'enterprise',
    }
    
    # Tier hierarchy for comparison
    TIER_LEVELS = {
        'free': 0,
        'solo': 1, 
        'team': 2,
        'enterprise': 3,
        'exempt': 4  # Exempt gets everything
    }
    
    @classmethod
    def has_feature(cls, feature_name, organization=None):
        """Check if organization has access to a specific feature"""
        if not organization:
            if not current_user.is_authenticated:
                return False
            organization = current_user.organization
            
        if not organization:
            return False
            
        # Developers always have access
        if current_user.is_authenticated and current_user.user_type == 'developer':
            return True
            
        # Get required tier for feature
        required_tier = cls.FEATURES.get(feature_name)
        if not required_tier:
            return True  # Unknown features default to available
            
        # Get organization's effective tier
        current_tier = organization.effective_subscription_tier
        
        # Compare tier levels
        required_level = cls.TIER_LEVELS.get(required_tier, 0)
        current_level = cls.TIER_LEVELS.get(current_tier, 0)
        
        return current_level >= required_level
    
    @classmethod
    def get_available_features(cls, organization=None):
        """Get list of all features available to organization"""
        if not organization:
            if not current_user.is_authenticated:
                return []
            organization = current_user.organization
            
        if not organization:
            return []
            
        available = []
        for feature_name in cls.FEATURES.keys():
            if cls.has_feature(feature_name, organization):
                available.append(feature_name)
                
        return available
    
    @classmethod
    def get_missing_features(cls, organization=None):
        """Get list of features not available to organization"""
        if not organization:
            if not current_user.is_authenticated:
                return list(cls.FEATURES.keys())
            organization = current_user.organization
            
        if not organization:
            return list(cls.FEATURES.keys())
            
        missing = []
        for feature_name in cls.FEATURES.keys():
            if not cls.has_feature(feature_name, organization):
                missing.append(feature_name)
                
        return missing
    
    @classmethod
    def get_features_by_tier(cls, tier):
        """Get all features available at a specific tier"""
        tier_level = cls.TIER_LEVELS.get(tier, 0)
        features = []
        
        for feature_name, required_tier in cls.FEATURES.items():
            required_level = cls.TIER_LEVELS.get(required_tier, 0)
            if tier_level >= required_level:
                features.append(feature_name)
                
        return features
    
    @classmethod
    def get_upgrade_suggestions(cls, organization=None):
        """Get suggested features user would get by upgrading"""
        if not organization:
            if not current_user.is_authenticated:
                return {}
            organization = current_user.organization
            
        if not organization:
            return {}
            
        current_tier = organization.effective_subscription_tier
        current_level = cls.TIER_LEVELS.get(current_tier, 0)
        
        suggestions = {}
        
        # Check what they'd get with team
        if current_level < cls.TIER_LEVELS['team']:
            team_features = cls.get_features_by_tier('team')
            current_features = cls.get_available_features(organization)
            suggestions['team'] = [f for f in team_features if f not in current_features]
            
        # Check what they'd get with enterprise  
        if current_level < cls.TIER_LEVELS['enterprise']:
            enterprise_features = cls.get_features_by_tier('enterprise')
            current_features = cls.get_available_features(organization)
            suggestions['enterprise'] = [f for f in enterprise_features if f not in current_features]
            
        return suggestions

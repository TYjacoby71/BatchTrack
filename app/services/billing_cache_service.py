
"""
Billing Cache Service

High-performance caching layer for organization billing data to reduce
database load during high-concurrency scenarios.
"""

import logging
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from flask import current_app, g
from ..extensions import db
from ..models import Organization, SubscriptionTier

logger = logging.getLogger(__name__)

@dataclass
class BillingSnapshot:
    """Cached billing state for an organization."""
    id: int
    name: str
    tier_id: Optional[int]
    tier_name: Optional[str] 
    tier_max_products: Optional[int]
    tier_max_users: Optional[int]
    tier_features: Optional[Dict[str, Any]]
    is_active: bool
    created_at: str
    
    @classmethod
    def from_organization(cls, org: Organization) -> 'BillingSnapshot':
        """Create snapshot from live organization data."""
        tier_features = {}
        if org.tier:
            tier_features = {
                'batch_tracking': getattr(org.tier, 'batch_tracking', True),
                'recipe_management': getattr(org.tier, 'recipe_management', True),
                'advanced_reporting': getattr(org.tier, 'advanced_reporting', False),
                'api_access': getattr(org.tier, 'api_access', False),
            }
        
        return cls(
            id=org.id,
            name=org.name,
            tier_id=org.tier.id if org.tier else None,
            tier_name=org.tier.name if org.tier else 'Free',
            tier_max_products=org.tier.max_products if org.tier else 10,
            tier_max_users=org.tier.max_users if org.tier else 3,
            tier_features=tier_features,
            is_active=org.is_active,
            created_at=org.created_at.isoformat() if org.created_at else None
        )

class BillingCacheService:
    """Service for caching organization billing data."""
    
    @staticmethod
    def get_cache_key(org_id: int) -> str:
        """Generate cache key for organization billing data."""
        return f"billing:org:{org_id}"
    
    @staticmethod
    def get_cached_billing_data(org_id: int) -> Optional[BillingSnapshot]:
        """Retrieve cached billing data for organization."""
        if not current_app.config.get('BILLING_CACHE_ENABLED', True):
            return None
            
        try:
            from ..extensions import cache
            cache_key = BillingCacheService.get_cache_key(org_id)
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.debug(f"Billing cache hit for org {org_id}")
                g.billing_gate_cache_state = 'hit'
                return BillingSnapshot(**json.loads(cached_data))
            else:
                logger.debug(f"Billing cache miss for org {org_id}")
                g.billing_gate_cache_state = 'miss'
                return None
                
        except Exception as e:
            logger.warning(f"Billing cache retrieval failed for org {org_id}: {e}")
            g.billing_gate_cache_state = 'error'
            return None
    
    @staticmethod
    def cache_billing_data(org_id: int, snapshot: BillingSnapshot) -> bool:
        """Cache billing data for organization."""
        if not current_app.config.get('BILLING_CACHE_ENABLED', True):
            return False
            
        try:
            from ..extensions import cache
            cache_key = BillingCacheService.get_cache_key(org_id)
            ttl = current_app.config.get('BILLING_GATE_CACHE_TTL_SECONDS', 60)
            
            cache.set(cache_key, json.dumps(asdict(snapshot)), timeout=ttl)
            logger.debug(f"Cached billing data for org {org_id} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to cache billing data for org {org_id}: {e}")
            return False
    
    @staticmethod
    def invalidate_org_cache(org_id: int) -> bool:
        """Invalidate cached billing data for organization."""
        try:
            from ..extensions import cache
            cache_key = BillingCacheService.get_cache_key(org_id)
            cache.delete(cache_key)
            logger.debug(f"Invalidated billing cache for org {org_id}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to invalidate billing cache for org {org_id}: {e}")
            return False
    
    @staticmethod
    def refresh_org_cache(org_id: int) -> Optional[BillingSnapshot]:
        """Refresh cached billing data from database."""
        try:
            org = Organization.query.get(org_id)
            if not org:
                return None
                
            snapshot = BillingSnapshot.from_organization(org)
            BillingCacheService.cache_billing_data(org_id, snapshot)
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to refresh billing cache for org {org_id}: {e}")
            return None

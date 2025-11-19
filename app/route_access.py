"""
Centralized route access configuration.

This module defines all route access rules in one place, following the principle
of "configuration over hardcoding". This is the single source of truth for
which routes are public, require authentication, or have special access requirements.

Industry Standard Pattern:
- Declarative access rules
- Single source of truth
- Easy to audit and maintain
- Separated from enforcement logic (middleware)
"""


class RouteAccessConfig:
    """
    Master configuration for route access control.
    
    This class defines access rules for all routes in the application.
    The middleware references these rules for enforcement.
    """
    
    # ============================================================================
    # PUBLIC ACCESS - No authentication required
    # ============================================================================
    
    PUBLIC_ENDPOINTS = [
        # Core public pages
        'static',
        'homepage',
        'index',
        
        # Authentication
        'auth.login',
        'auth.signup',
        'auth.logout',
        
        # Legal pages
        'legal.privacy_policy',
        'legal.terms_of_service',
        
        # Billing webhooks (Stripe callbacks)
        'billing.stripe_webhook',
        
        # Public tools - category-specific calculators
        'tools_bp.tools_index',
        'tools_bp.tools_soap',
        'tools_bp.tools_candles',
        'tools_bp.tools_lotions',
        'tools_bp.tools_herbal',
        'tools_bp.tools_baker',
        'tools_bp.tools_draft',  # Save draft from public tools (unauthenticated)
        
        # Public exports - preview tools (HTML previews)
        'exports.soap_inci_tool',
        'exports.candle_label_tool',
        'exports.baker_sheet_tool',
        'exports.lotion_inci_tool',
        
        # Public API endpoints
        'public_api_bp.public_global_item_search',
        'global_library_bp.global_library',
        'global_library_bp.global_item_detail',
        'help_routes.help_overview',
        'help_routes.help_faq',
        
        # Waitlist signup (for unauthenticated users)
        'waitlist.join_waitlist',
    ]
    
    PUBLIC_PATH_PREFIXES = [
        '/homepage',
        '/legal/',
        '/static/',
        '/auth/login',
        '/auth/signup',
        '/auth/logout',
        '/tools',              # Public calculator tools
        '/tools/',             # Explicit trailing-slash variant for public tools
        '/exports/tool',       # Public export previews
        '/api/public',         # Public API namespace
        '/help',               # Public help center
    ]
    
    # ============================================================================
    # DEVELOPER-ONLY ACCESS - Requires user_type='developer'
    # ============================================================================
    
    DEVELOPER_ONLY_PATH_PREFIXES = [
        '/developer/',
    ]
    
    # Paths developers can access WITHOUT org selection
    DEVELOPER_NO_ORG_REQUIRED_PREFIXES = [
        '/developer/',
        '/auth/permissions',
        '/global-items',       # Read-only global library
    ]
    
    # ============================================================================
    # CUSTOMER ACCESS - Authenticated users (requires billing check)
    # ============================================================================
    
    # These are implicitly defined: any authenticated route not in PUBLIC or DEVELOPER
    # Examples:
    # - /dashboard
    # - /inventory/*
    # - /recipes/*
    # - /batches/*
    # - /products/*
    # - /billing/* (except webhooks)
    # - /organization/*
    # - /settings/*
    
    # ============================================================================
    # MONITORING & HEALTH CHECKS - Skip all middleware
    # ============================================================================
    
    MONITORING_PATHS = [
        '/api',
        '/api/',
        '/health',
        '/ping',
    ]
    
    # ============================================================================
    # LOGGING CONFIGURATION - Minimal logging for high-frequency endpoints
    # ============================================================================
    
    FREQUENT_ENDPOINTS = [
        'server_time.get_server_time',
        'api.get_dashboard_alerts',
    ]
    
    # ============================================================================
    # HELPER METHODS - Used by middleware for clean access checks
    # ============================================================================
    
    @classmethod
    def is_public_endpoint(cls, endpoint):
        """
        Check if an endpoint is public (no authentication required).
        
        Args:
            endpoint: Flask endpoint name (e.g., 'auth.login')
            
        Returns:
            bool: True if endpoint is public
        """
        return endpoint in cls.PUBLIC_ENDPOINTS
    
    @classmethod
    def is_public_path(cls, path):
        """
        Check if a path is public (no authentication required).
        
        Args:
            path: Request path (e.g., '/tools/soap')
            
        Returns:
            bool: True if path is public
        """
        return any(path.startswith(prefix) for prefix in cls.PUBLIC_PATH_PREFIXES)
    
    @classmethod
    def is_developer_only_path(cls, path):
        """
        Check if a path requires developer access.
        
        Args:
            path: Request path (e.g., '/developer/organizations')
            
        Returns:
            bool: True if path requires developer user_type
        """
        return any(path.startswith(prefix) for prefix in cls.DEVELOPER_ONLY_PATH_PREFIXES)
    
    @classmethod
    def is_developer_no_org_required(cls, path):
        """
        Check if a path can be accessed by developers without org selection.
        
        Args:
            path: Request path
            
        Returns:
            bool: True if developer can access without selecting an org
        """
        return any(path.startswith(prefix) for prefix in cls.DEVELOPER_NO_ORG_REQUIRED_PREFIXES)
    
    @classmethod
    def is_monitoring_request(cls, request):
        """
        Check if this is a monitoring/health check request.
        These requests skip ALL middleware processing.
        
        Args:
            request: Flask request object
            
        Returns:
            bool: True if this is a monitoring request
        """
        return (
            request.headers.get('User-Agent', '').lower() == 'node' and
            request.method == 'HEAD' and
            request.path in cls.MONITORING_PATHS
        )
    
    @classmethod
    def should_minimize_logging(cls, endpoint):
        """
        Check if this endpoint should have minimal logging.
        
        Args:
            endpoint: Flask endpoint name
            
        Returns:
            bool: True if logging should be minimized
        """
        return endpoint in cls.FREQUENT_ENDPOINTS
    
    @classmethod
    def get_access_summary(cls):
        """
        Generate a summary of all access rules for documentation/auditing.
        
        Returns:
            dict: Summary of all access rules
        """
        return {
            'public_endpoints': len(cls.PUBLIC_ENDPOINTS),
            'public_path_prefixes': len(cls.PUBLIC_PATH_PREFIXES),
            'developer_only_prefixes': len(cls.DEVELOPER_ONLY_PATH_PREFIXES),
            'developer_no_org_prefixes': len(cls.DEVELOPER_NO_ORG_REQUIRED_PREFIXES),
            'monitoring_paths': len(cls.MONITORING_PATHS),
            'frequent_endpoints': len(cls.FREQUENT_ENDPOINTS),
        }

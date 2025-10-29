"""
Centralized Error Messages

This module provides a single source of truth for all user-facing error messages
in the application. This ensures consistency, makes updates easier, and prepares
the codebase for future internationalization.

Usage:
    from app.utils.error_messages import ErrorMessages as EM
    
    # Simple message
    flash(EM.INVENTORY_NOT_FOUND, 'error')
    
    # Message with parameters
    flash(EM.INSUFFICIENT_STOCK.format(required=10, available=5), 'error')
    
    # In API responses
    return APIResponse.error(
        message=EM.BATCH_START_FAILED.format(reason=error_detail),
        errors={'batch_id': batch_id},
        status_code=400
    )
"""


class ErrorMessages:
    """User-facing error messages - never contain HTML or special characters"""
    
    # ==================== AUTHENTICATION & AUTHORIZATION ====================
    AUTH_REQUIRED = "Please log in to access this page."
    AUTH_INVALID_CREDENTIALS = "Invalid username or password."
    AUTH_PASSWORD_INCORRECT = "Incorrect password."
    PERMISSION_DENIED = "You don't have permission to access this feature. Required permission: {permission}"
    PERMISSION_INSUFFICIENT = "Insufficient permissions to perform this action."
    ACCESS_DENIED = "Access denied."
    DEVELOPER_ONLY = "Developer access required."
    
    # ==================== ORGANIZATION ====================
    ORG_NOT_FOUND = "Organization not found."
    ORG_SELECT_REQUIRED = "Please select an organization to view customer features."
    ORG_NO_LONGER_EXISTS = "Selected organization no longer exists. Masquerade cleared."
    ORG_SUBSCRIPTION_REQUIRED = "Organization dashboard is available with Team and Enterprise plans."
    ORG_SUSPENDED = "Your organization has been suspended. Please contact support."
    ORG_SUBSCRIPTION_INACTIVE = "Your organization does not have an active subscription. Please update billing."
    ORG_DATABASE_ERROR = "Database error accessing organization. Please try again."
    
    # ==================== INVENTORY ====================
    INVENTORY_NOT_FOUND = "Inventory item not found."
    INVENTORY_ACCESS_DENIED = "Inventory item not found or access denied."
    INVENTORY_ADJUST_FAILED = "Failed to adjust inventory: {reason}"
    INVENTORY_CREATE_FAILED = "Failed to create inventory item: {reason}"
    INVENTORY_UPDATE_FAILED = "Failed to update inventory item: {reason}"
    INVENTORY_DELETE_FAILED = "Error deleting inventory item: {reason}"
    INVENTORY_QUANTITY_REQUIRED = "Quantity is required."
    INVENTORY_QUANTITY_INVALID = "Invalid quantity provided."
    INVENTORY_QUANTITY_POSITIVE = "Quantity must be greater than 0."
    INVENTORY_QUANTITY_NEGATIVE = "Quantity cannot be negative."
    INVENTORY_CHANGE_TYPE_REQUIRED = "Adjustment type is required."
    INVENTORY_COST_INVALID = "Invalid cost provided."
    INVENTORY_COST_REQUIRES_QUANTITY = "Total cost requires a positive quantity."
    INVENTORY_INSUFFICIENT = "Insufficient inventory available. Required: {required} {unit}, Available: {available} {unit}"
    INVENTORY_SHORTAGE = "Short by {shortage} {unit}"
    
    # ==================== RECIPES ====================
    RECIPE_NOT_FOUND = "Recipe not found."
    RECIPE_LOCKED = "This recipe is locked and cannot be edited."
    RECIPE_CREATE_FAILED = "Error creating recipe: {reason}"
    RECIPE_UPDATE_FAILED = "Error updating recipe: {reason}"
    RECIPE_DELETE_FAILED = "Error deleting recipe: {reason}"
    RECIPE_VARIATION_FAILED = "Error creating variation: {reason}"
    RECIPE_CLONE_FAILED = "Error cloning recipe: {reason}"
    RECIPE_PARENT_NOT_FOUND = "Parent recipe not found."
    RECIPE_INGREDIENT_INVALID = "Invalid ingredient data provided."
    
    # ==================== BATCHES ====================
    BATCH_NOT_FOUND = "Batch not found."
    BATCH_START_FAILED = "Failed to start batch: {reason}"
    BATCH_FINISH_FAILED = "Failed to finish batch: {reason}"
    BATCH_CANCEL_FAILED = "Failed to cancel batch: {reason}"
    BATCH_RECIPE_REQUIRED = "Batch ID and Recipe ID are required."
    BATCH_SCALE_INVALID = "Scale must be greater than 0."
    BATCH_INVALID_STATUS = "Batch is not in a valid state for this operation."
    BATCH_INGREDIENT_SHORTAGE = "Cannot start batch: insufficient inventory for {ingredient}"
    BATCH_CONTAINER_SHORTAGE = "Cannot start batch: insufficient containers"
    
    # ==================== PRODUCTS & SKUs ====================
    PRODUCT_NOT_FOUND = "Product not found."
    SKU_NOT_FOUND = "SKU not found."
    SKU_INACTIVE = "SKU is not active."
    SKU_INVENTORY_ADJUST_FAILED = "Error adjusting product inventory: {reason}"
    PRODUCT_CREATE_FAILED = "Failed to create product: {reason}"
    PRODUCT_UPDATE_FAILED = "Failed to update product: {reason}"
    
    # ==================== RESERVATIONS ====================
    RESERVATION_NOT_FOUND = "Reservation not found."
    RESERVATION_NOT_ACTIVE = "Reservation is not active."
    RESERVATION_CREATE_FAILED = "Failed to create reservation: {reason}"
    RESERVATION_RELEASE_FAILED = "Failed to release reservation: {reason}"
    RESERVATION_CONVERT_FAILED = "Failed to convert reservation to sale: {reason}"
    RESERVATION_INSUFFICIENT_PERMISSIONS = "Insufficient permissions to create reservations."
    RESERVATION_FIELDS_REQUIRED = "Missing required fields: sku_code, quantity, order_id"
    
    # ==================== TIMERS ====================
    TIMER_NOT_FOUND = "Timer not found."
    TIMER_STOP_FAILED = "Cannot stop timer. Timer may already be stopped or in an invalid state."
    TIMER_PAUSE_FAILED = "Cannot pause timer. Timer can only be paused when active."
    TIMER_RESUME_FAILED = "Cannot resume timer. Timer can only be resumed when paused."
    TIMER_CREATE_FAILED = "Failed to create timer: {reason}"
    TIMER_FIELDS_REQUIRED = "Batch ID and duration are required."
    TIMER_INVALID_DATA = "Invalid batch ID or duration."
    
    # ==================== UNITS & CONVERSION ====================
    UNIT_NOT_FOUND = "Unit not found."
    UNIT_DELETE_SYSTEM = "Cannot delete system units."
    UNIT_DELETE_FAILED = "Error deleting unit: {reason}"
    UNIT_CREATE_FAILED = "Error creating unit: {reason}"
    UNIT_NAME_REQUIRED = "Unit name is required."
    UNIT_NAME_EXISTS = "A unit with this name already exists."
    UNIT_MAPPING_FAILED = "Failed to create unit mapping: {reason}"
    UNIT_MAPPING_EXISTS = "This custom unit already has a mapping."
    UNIT_MAPPING_DELETE_FAILED = "Error deleting mapping: {reason}"
    
    CONVERSION_FAILED = "Unit conversion failed: {reason}"
    CONVERSION_UNSUPPORTED = "Cannot convert {from_unit} to {to_unit} without a custom mapping."
    CONVERSION_DENSITY_REQUIRED = "Density required to convert {from_unit} to {to_unit}. Please set ingredient density first."
    CONVERSION_DENSITY_MISSING = "Missing density for conversion. Please add ingredient density or create a custom unit mapping."
    CONVERSION_INGREDIENT_CONTEXT_REQUIRED = "Volume to weight conversions require ingredient context."
    CONVERSION_NO_PATH = "No conversion path exists between {from_unit} and {to_unit}."
    
    # ==================== EXPIRATION ====================
    EXPIRATION_DISPOSE_FAILED = "Failed to dispose expired inventory: {reason}"
    EXPIRATION_NO_EXPIRED = "No expired inventory found."
    
    # ==================== STOCK CHECK ====================
    STOCK_CHECK_FAILED = "Error checking stock: {reason}"
    STOCK_CHECK_NO_RECIPES = "Please select at least one recipe."
    STOCK_CHECK_SCALE_INVALID = "Scale must be greater than 0."
    STOCK_CHECK_NO_RESULTS = "No stock check results available."
    STOCK_CHECK_NO_RESTOCK_NEEDED = "No items need restocking."
    
    # ==================== BILLING & SUBSCRIPTIONS ====================
    BILLING_WEBHOOK_FAILED = "Webhook processing failed: {reason}"
    BILLING_CUSTOMER_NOT_FOUND = "Customer not found for billing operation."
    BILLING_SUBSCRIPTION_FAILED = "Failed to process subscription change: {reason}"
    
    # ==================== SETTINGS & PREFERENCES ====================
    SETTINGS_UPDATE_FAILED = "Failed to update settings: {reason}"
    SETTINGS_INVALID_TIMEZONE = "Invalid timezone selected. Please choose from the available options."
    PREFERENCE_KEY_REQUIRED = "Preference key is required."
    PREFERENCE_KEY_INVALID = "Invalid preference key."
    PREFERENCE_SAVE_FAILED = "Error saving preference: {reason}"
    
    # ==================== VALIDATION ====================
    VALIDATION_REQUIRED_FIELDS = "Missing required fields: {fields}"
    VALIDATION_INVALID_FORMAT = "Invalid data format for field: {field}"
    VALIDATION_CSRF_INVALID = "Invalid CSRF token."
    VALIDATION_JSON_REQUIRED = "JSON data required."
    
    # ==================== SYSTEM ====================
    SYSTEM_ERROR = "An unexpected error occurred. Please try again."
    SYSTEM_DATABASE_ERROR = "Database error. Please try again."
    SYSTEM_TEMPORARILY_UNAVAILABLE = "This feature is temporarily unavailable. Please try refreshing the page."
    SYSTEM_PROCESSING_FAILED = "Processing failed. Please try again."
    
    # ==================== TOOLS ====================
    TOOLS_UNAVAILABLE = "{tool_name} tools are currently unavailable."


class SuccessMessages:
    """User-facing success messages"""
    
    # ==================== INVENTORY ====================
    INVENTORY_CREATED = "New inventory item created: {name}"
    INVENTORY_UPDATED = "Inventory item updated successfully."
    INVENTORY_ADJUSTED = "{change_type} completed: {details}"
    INVENTORY_ARCHIVED = "Inventory item archived successfully."
    INVENTORY_RESTORED = "Inventory item restored successfully."
    
    # ==================== RECIPES ====================
    RECIPE_CREATED = "Recipe created successfully with ingredients."
    RECIPE_UPDATED = "Recipe updated successfully."
    RECIPE_DELETED = "Recipe deleted successfully."
    RECIPE_LOCKED = "Recipe locked successfully."
    RECIPE_UNLOCKED = "Recipe unlocked successfully."
    RECIPE_VARIATION_CREATED = "Recipe variation created successfully."
    RECIPE_CLONED = "Recipe cloned successfully."
    
    # ==================== BATCHES ====================
    BATCH_STARTED = "Batch started successfully."
    BATCH_STARTED_WITH_DEDUCTIONS = "Batch started successfully. Deducted items: {items}"
    BATCH_FINISHED = "Batch finished successfully."
    BATCH_CANCELLED = "Batch cancelled successfully."
    
    # ==================== PRODUCTS & SKUs ====================
    PRODUCT_INVENTORY_ADJUSTED = "Product inventory adjusted successfully."
    PRODUCT_SALE_PROCESSED = "Sale processed successfully."
    PRODUCT_RETURN_PROCESSED = "Return processed successfully."
    
    # ==================== RESERVATIONS ====================
    RESERVATION_CREATED = "Reserved {quantity} {unit} for order {order_id}"
    RESERVATION_RELEASED = "Reservation released successfully."
    RESERVATION_CONVERTED = "Reservation converted to sale successfully."
    RESERVATION_EXPIRED = "Expired {count} reservations."
    
    # ==================== TIMERS ====================
    TIMER_CREATED = "Timer created successfully."
    TIMER_STOPPED = "Timer completed."
    TIMER_PAUSED = "Timer paused."
    TIMER_RESUMED = "Timer resumed."
    TIMER_DELETED = "Timer deleted."
    TIMER_CANCELLED = 'Timer "{name}" cancelled.'
    
    # ==================== UNITS & CONVERSION ====================
    UNIT_CREATED = "Unit created successfully."
    UNIT_DELETED = "Unit deleted successfully."
    UNIT_MAPPING_CREATED = "Custom mapping added successfully."
    UNIT_MAPPING_DELETED = "Mapping deleted successfully."
    
    # ==================== SETTINGS & PREFERENCES ====================
    SETTINGS_SAVED = "All preferences saved successfully."
    PROFILE_UPDATED = "Profile updated successfully."
    TIMEZONE_UPDATED = "Timezone updated successfully."
    PREFERENCE_SAVED = "Preference saved successfully."
    
    # ==================== SYSTEM ====================
    OPERATION_SUCCESSFUL = "Operation completed successfully."


class WarningMessages:
    """User-facing warning messages"""
    
    # ==================== ORGANIZATION ====================
    ORG_SELECTION_REQUIRED = "Developers must select an organization to view customer dashboard."
    
    # ==================== BATCHES ====================
    BATCH_STARTED_WITH_WARNINGS = "Batch started with warnings: {warnings}"
    
    # ==================== STOCK ====================
    STOCK_CHECK_ISSUES = "Bulk stock processing failed: {reason}"
    
    # ==================== TOOLS ====================
    TOOLS_UNAVAILABLE = "{tool_name} tools are currently unavailable."
    
    # ==================== FEATURES ====================
    FEATURE_COMING_SOON = "{feature} functionality coming soon."


class InfoMessages:
    """User-facing informational messages"""
    
    # ==================== INVENTORY ====================
    INVENTORY_ITEMS_ADDED = "Added {count} new inventory item(s) from this recipe: {names}"
    INVENTORY_ANALYTICS_DISABLED = "Inventory analytics is not enabled for this environment."
    
    # ==================== FEATURES ====================
    FEATURE_TIER_REQUIRED = "{feature} is available with {tier} plans."
    ADDON_ALREADY_INCLUDED = "This add-on is already included in your tier."


# ============================================================================
# MIGRATION PLACEHOLDERS - Organized by File
# ============================================================================
# Below are pre-created message constants organized by file.
# Each section shows the file it came from and line numbers where used.
# Simply copy these to the appropriate class above as you migrate each file.
# ============================================================================


class _TimersMessages:
    """
    Source: app/blueprints/timers/routes.py (3 violations)
    Lines: 106, 140, 154
    """
    # Already defined above - move these notes there:
    # TIMER_STOP_FAILED - Line 106
    # TIMER_PAUSE_FAILED - Line 140  
    # TIMER_RESUME_FAILED - Line 154


class _InventoryMessages:
    """
    Source: app/blueprints/inventory/routes.py (~12 violations)
    Lines: 236, 371, 376, 386, 392, 395, 409, 415, 465, 512
    """
    # Add these to ErrorMessages class:
    INVENTORY_ACCESS_DENIED_ALT = "Inventory item not found or access denied."  # Line 236
    # INVENTORY_NOT_FOUND already exists - Line 371
    # PERMISSION_DENIED already exists - Line 376
    # INVENTORY_CHANGE_TYPE_REQUIRED already exists - Line 386
    # INVENTORY_QUANTITY_POSITIVE already exists - Line 392
    # INVENTORY_QUANTITY_INVALID already exists - Line 395
    # INVENTORY_COST_REQUIRES_QUANTITY already exists - Line 409
    # INVENTORY_COST_INVALID already exists - Line 415
    # PERMISSION_DENIED already exists - Line 465
    INVENTORY_RECOUNT_QUANTITY_INVALID = "Invalid quantity provided for recount."  # Line 512


class _RecipesMessages:
    """
    Source: app/blueprints/recipes/routes.py (8 violations)
    Lines: 117, 176, 201, 259, 263, 359, 429, 455
    """
    # Add these to ErrorMessages class:
    RECIPE_UNEXPECTED_ERROR = "An unexpected error occurred"  # Lines 117, 359
    # RECIPE_NOT_FOUND already exists - Lines 176, 259
    # RECIPE_PARENT_NOT_FOUND already exists - Line 201
    # RECIPE_LOCKED already exists - Line 263
    RECIPE_DELETE_ERROR = "An error occurred while deleting the recipe."  # Line 429
    RECIPE_PASSWORD_INCORRECT = "Incorrect password."  # Line 455 (or use AUTH_PASSWORD_INCORRECT)


class _BulkStockMessages:
    """
    Source: app/routes/bulk_stock_routes.py (9 violations)
    Lines: 23, 29, 32, 79, 83, 92, 97, 111, 114
    """
    # Add these to ErrorMessages class:
    BULK_STOCK_SELECT_RECIPE = "Please select at least one recipe"  # Line 23
    BULK_STOCK_SCALE_POSITIVE = "Scale must be greater than 0"  # Line 29
    BULK_STOCK_SCALE_INVALID = "Invalid scale value"  # Line 32
    BULK_STOCK_CHECK_FAILED = "Bulk stock check failed"  # Line 79
    BULK_STOCK_ERROR = "Error checking stock: {reason}"  # Line 83
    BULK_STOCK_NO_RESULTS = "No stock check results available"  # Line 92
    BULK_STOCK_NO_RESTOCK_NEEDED = "No items need restocking"  # Line 97
    BULK_STOCK_PROCESSING_FAILED = "Bulk stock processing failed: {reason}"  # Line 111
    BULK_STOCK_CSV_ERROR = "Database error exporting CSV."  # Line 114


class _AppRoutesMessages:
    """
    Source: app/routes/app_routes.py (4 violations)
    Lines: 25, 37, 44, 123
    """
    # Add these to ErrorMessages/WarningMessages:
    # ORG_SELECTION_REQUIRED already exists - Line 25
    ORG_CLEARED_NO_LONGER_EXISTS = "Selected organization no longer exists. Masquerade cleared."  # Line 37
    # ORG_DATABASE_ERROR already exists - Line 44
    DASHBOARD_UNAVAILABLE = "Dashboard temporarily unavailable. Please try refreshing the page."  # Line 123


class _DeveloperRoutesMessages:
    """
    Source: app/blueprints/developer/routes.py (22 violations)
    Lines: 216, 220, 224, 228, 234, 380, 403, 537, 727, 1127, 1170, 1178, 1197, 1754, 1758, 1764, 1778, 1782, 1789, 1804, 1808
    """
    # Add these to ErrorMessages/SuccessMessages:
    DEV_ORG_NAME_REQUIRED = "Organization name is required"  # Line 216
    DEV_USERNAME_REQUIRED = "Username is required"  # Line 220
    DEV_EMAIL_REQUIRED = "Email is required"  # Line 224
    DEV_PASSWORD_REQUIRED = "Password is required"  # Line 228
    DEV_USERNAME_EXISTS = "Username already exists"  # Line 234
    DEV_ORG_UPDATED = "Organization updated successfully"  # Line 380 (SuccessMessages)
    DEV_TIER_INVALID = "Invalid subscription tier"  # Line 403
    DEV_CANNOT_MODIFY_DEVELOPER = "Cannot modify developer users"  # Line 537
    DEV_GLOBAL_ITEM_UPDATED = "Global item updated successfully"  # Line 727 (SuccessMessages)
    DEV_NAME_REQUIRED = "Name is required"  # Lines 1127, 1754, 1778
    DEV_DENSITY_INVALID = "Invalid density value"  # Line 1170
    DEV_CAPACITY_INVALID = "Invalid capacity value"  # Line 1178
    DEV_SHELF_LIFE_INVALID = "Invalid shelf life value"  # Line 1197
    DEV_CATEGORY_NAME_EXISTS = "Category name already exists"  # Lines 1758, 1782
    DEV_CATEGORY_CREATED = "Product category created"  # Line 1764 (SuccessMessages)
    DEV_CATEGORY_NAME_EXISTS_ALT = "Another category with that name exists"  # Line 1782
    DEV_CATEGORY_UPDATED = "Product category updated"  # Line 1789 (SuccessMessages)
    DEV_CATEGORY_IN_USE = "Cannot delete category that is used by products or recipes"  # Line 1804
    DEV_CATEGORY_DELETED = "Product category deleted"  # Line 1808 (SuccessMessages)


class _BillingRoutesMessages:
    """
    Source: app/blueprints/billing/routes.py (42 violations)
    Lines: 29, 38, 80, 91, 98, 111, 115, 128, 135, 140, 143, 148, 159, 162, 172, 189, 194, 203, 215, 220, 230, 238, 245, 254, 263, 270, 306, 410, 420, 427, 430, 435, 444, 455, 460, 469, 478, 482, 484, 488, 581, 586
    """
    # Add these to ErrorMessages/SuccessMessages/WarningMessages:
    # ORG_NOT_FOUND already exists - Lines 29, 172, 203, 469, 586
    BILLING_PRICING_UNAVAILABLE = "Pricing information temporarily unavailable. Please try again later."  # Line 38
    BILLING_NO_ORG_OR_TIER = "No organization or tier found"  # Line 80
    BILLING_STORAGE_UPGRADE_REQUIRED = "Storage add-on is not available for your tier. Please upgrade instead."  # Line 91
    BILLING_TEMPORARILY_UNAVAILABLE = "Billing temporarily unavailable"  # Lines 98, 148
    BILLING_STORAGE_CHECKOUT_FAILED = "Unable to start storage checkout"  # Line 111
    BILLING_CHECKOUT_FAILED = "Checkout failed. Please try again later."  # Lines 115, 162, 220
    BILLING_ADDON_NOT_AVAILABLE = "Add-on not available."  # Line 128
    BILLING_NO_TIER = "No subscription tier found for your organization."  # Line 135
    # BILLING_ADDON_ALREADY_INCLUDED already in InfoMessages - Line 140
    BILLING_ADDON_TIER_MISMATCH = "This add-on is not available for your current tier."  # Line 143
    BILLING_CHECKOUT_START_FAILED = "Unable to start checkout"  # Line 159
    BILLING_CHECKOUT_TIER_UNAVAILABLE = "Checkout not available for this tier"  # Line 189
    BILLING_CHECKOUT_FAILED_RETRY = "Checkout failed. Please try again."  # Line 194
    BILLING_WHOP_UNAVAILABLE = "Whop checkout not available"  # Line 215
    BILLING_SESSION_INVALID = "Invalid checkout session"  # Line 230
    BILLING_PAYMENT_ERROR = "Payment system error"  # Line 238
    BILLING_SESSION_NOT_FOUND = "Checkout session not found"  # Line 245
    BILLING_CUSTOMER_NOT_FOUND_ALT = "Customer information not found"  # Lines 254, 263
    BILLING_TIER_NOT_FOUND = "Subscription tier not found"  # Line 270
    BILLING_PLAN_INVALID = "Invalid subscription plan"  # Line 306
    BILLING_SETUP_FAILED = "Account setup failed. Please contact support."  # Line 410
    BILLING_LICENSE_MISSING = "No license key provided"  # Line 420
    BILLING_ACTIVATED = "Subscription activated successfully!"  # Line 427 (SuccessMessages)
    BILLING_ACTIVATION_FAILED = "Failed to activate subscription"  # Line 430
    BILLING_SIGNUP_FAILED = "Signup completion failed"  # Line 435
    BILLING_NO_ACCOUNT = "No billing account found"  # Line 444
    BILLING_PORTAL_ACCESS_FAILED = "Unable to access billing portal"  # Line 455
    BILLING_PORTAL_UNAVAILABLE = "Billing portal unavailable"  # Line 460
    BILLING_NO_SUBSCRIPTION = "No active subscription found"  # Line 478
    BILLING_CANCELLED = "Subscription cancelled successfully"  # Line 482 (SuccessMessages)
    BILLING_CANCEL_FAILED = "Failed to cancel subscription"  # Line 484
    BILLING_CANCELLATION_FAILED = "Cancellation failed"  # Line 488
    # ACCESS_DENIED already exists - Line 581


class _ToolsRoutesMessages:
    """
    Source: app/routes/tools_routes.py (5 violations)
    All use same pattern with different tool names
    """
    # Add to WarningMessages:
    TOOLS_SOAP_UNAVAILABLE = "Soap tools are currently unavailable."
    TOOLS_CANDLES_UNAVAILABLE = "Candle tools are currently unavailable."
    TOOLS_LOTIONS_UNAVAILABLE = "Lotion tools are currently unavailable."
    TOOLS_HERBAL_UNAVAILABLE = "Herbal tools are currently unavailable."
    TOOLS_BAKER_UNAVAILABLE = "Baker tools are currently unavailable."


class _ProductsMessages:
    """
    Source: Various product files - product_inventory_routes.py, product_variants.py, sku.py, products.py
    ~40+ violations across these files
    """
    # These are already defined in ErrorMessages for the most part
    # Add any missing ones as you encounter them during migration

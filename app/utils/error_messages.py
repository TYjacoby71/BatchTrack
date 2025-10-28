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
    
    # ==================== FEATURES ====================
    FEATURE_TIER_REQUIRED = "{feature} is available with {tier} plans."

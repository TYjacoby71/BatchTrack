## POST /batches/api/start-batch

Start a new batch from a client-provided PlanSnapshot.

Request JSON:
```
{
  "plan_snapshot": {
    "recipe_id": 12,
    "scale": 1.0,
    "batch_type": "product",
    "projected_yield": 10.0,
    "projected_yield_unit": "oz",
    "portioning": {
      "is_portioned": true,
      "portion_name": "bars",
      "portion_unit_id": 120,
      "portion_count": 20
    },
    "containers": [{ "id": 11, "quantity": 4 }],
    "ingredients_plan": [{ "inventory_item_id": 42, "quantity": 2.0, "unit": "count" }],
    "consumables_plan": [{ "inventory_item_id": 77, "quantity": 1.0, "unit": "count" }]
  }
}
```

Response JSON:
```
{ "success": true, "message": "Batch started successfully", "batch_id": 34 }
```

Errors:
- 400 if `plan_snapshot` is missing/invalid or deductions fail

# API Reference

## Production Planning

- POST `/production/stock/check` — Recipe stock check
  - Body: `{ recipe_id: number, scale_factor?: number }`
  - Returns: `{ success: boolean, shortages?: [...], drawer_payload?: {...} }`
  - Notes: May include `drawer_payload` for user-fixable issues (see `docs/WALL_OF_DRAWERS_PROTOCOL.md`).

## FIFO & Inventory

- GET `/api/fifo-details/:inventory_id` — FIFO entries for an inventory item
- GET `/api/batch-inventory-summary/:batch_id` — Batch usage summary

## Drawer Actions

- GET `/api/drawers/conversion/density-modal/:ingredient_id` — Density fix modal
- GET `/api/drawers/conversion/unit-mapping-modal` — Unit mapping modal

See controller: `app/blueprints/api/drawers/`.
# API Reference

This document provides a comprehensive reference for all API endpoints available in BatchTrack.

## Authentication

All API endpoints require user authentication via Flask-Login session cookies.

## Dashboard APIs

### Get Dashboard Alerts
```
GET /api/dashboard-alerts
```

Returns active alerts for the current user's organization using `DashboardAlertService.get_dashboard_alerts()`.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "priority": "HIGH|MEDIUM|LOW",
      "type": "low_stock|expiring_items|active_batches|incomplete_batches",
      "title": "Alert Title",
      "message": "Alert description",
      "action_url": "/path/to/action",
      "action_text": "Action Button Text",
      "dismissible": true
    }
  ]
}
```

### Dismiss Alert
```
POST /api/dismiss-alert
```

Dismisses a specific alert for the current session (session-based dismissal).

**Request Body:**
```json
{
  "alert_id": "alert_identifier"
}
```

## Unit Conversion APIs

### Get Available Units
```
GET /api/units
```

Returns all available units for the current user using `get_global_unit_list()`.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "gram",
      "symbol": "g",
      "unit_type": "weight",
      "base_unit": true
    }
  ]
}
```

### Convert Units
```
POST /api/convert-units
```

Converts a quantity from one unit to another using `ConversionEngine.convert_units()`.

**Request Body:**
```json
{
  "from_unit_id": 1,
  "to_unit_id": 2,
  "quantity": 100,
  "ingredient_id": 5
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "converted_quantity": 100.0,
    "from_unit": "g",
    "to_unit": "oz",
    "conversion_factor": 0.035274
  }
}
```

## Recipes

### Generate Label Prefix
```
GET /api/recipes/prefix?name=Milk%20and%20Honey
```

Returns a unique label prefix for the given recipe name, scoped to the active organization.

**Response:**
```json
{
  "prefix": "MAH"
}
```

## Organization Management

### Get Organization Dashboard Data
```http
GET /organization/dashboard
```

**Response:**
```json
{
    "success": true,
    "data": {
        "organization": {
            "id": 1,
            "name": "Example Soaps",
            "subscription_tier": "team",
            "active_users_count": 5
        },
        "users": [...],
        "roles": [...],
        "permissions": [...]
    }
}
```

### Invite User
```http
POST /organization/invite-user
```

**Request Body:**
```json
{
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe", 
    "phone": "555-123-4567",
    "role_id": 2
}
```

**Response:**
```json
{
    "success": true,
    "message": "User invited successfully",
    "data": {
        "username": "john.doe",
        "temporary_password": "temp123456"
    }
}
```

## Inventory Management

### Get Inventory Items
```http
GET /api/inventory
```

**Query Parameters:**
- `page` (int): Page number for pagination
- `per_page` (int): Items per page (max 100)
- `category_id` (int): Filter by ingredient category
- `low_stock` (bool): Show only low stock items

**Response:**
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 1,
                "ingredient_name": "Coconut Oil",
                "quantity": 250.5,
                "unit": "oz",
                "cost_per_unit": 0.15,
                "expiration_date": "2024-12-31",
                "low_stock": false
            }
        ],
        "pagination": {
            "page": 1,
            "pages": 5,
            "per_page": 20,
            "total": 98
        }
    }
}
```

### Adjust Inventory
```http
POST /api/inventory/adjust
```

**Request Body:**
```json
{
    "adjustments": [
        {
            "inventory_id": 1,
            "adjustment_type": "restock",
            "quantity": 100.0,
            "cost_per_unit": 0.16,
            "expiration_date": "2024-12-31",
            "reason": "New shipment received"
        }
    ],
    "notes": "Monthly restock order #12345"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Inventory adjusted successfully",
    "data": {
        "adjustments_processed": 1,
        "total_cost_change": 16.00
    }
}
```

## Batch Management

### Get Batches
```http
GET /api/batches
```

**Query Parameters:**
- `status` (string): Filter by status (planned, in_progress, finished)
- `recipe_id` (int): Filter by recipe
- `date_from` (date): Start date filter
- `date_to` (date): End date filter

### Start Batch
```http
POST /api/batches/start
```

**Request Body:**
```json
{
    "recipe_id": 1,
    "planned_quantity": 10,
    "notes": "Double batch for holiday orders"
}
```

### Finish Batch
```http
POST /api/batches/<batch_id>/finish
```

**Request Body:**
```json
{
    "products": [
        {
            "product_sku_id": 1,
            "quantity": 8,
            "notes": "2 bars broke during unmolding"
        }
    ],
    "batch_notes": "Successful batch, good trace"
}
```

## Product Management

### Get Product Variants
```http
GET /api/products/<product_id>/variants
```

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "sku": "SOAP-LAV-4OZ",
            "name": "Lavender Soap - 4oz",
            "price": 8.99,
            "current_stock": 15,
            "reserved_stock": 2
        }
    ]
}
```

### Reserve Product
```http
POST /api/reservations/create
```

**Request Body:**
```json
{
    "product_sku_id": 1,
    "quantity": 3,
    "customer_name": "Jane Smith",
    "notes": "Wedding favors order"
}
```

## Stock Management

### Check Stock Availability
```http
POST /api/check-stock
```

**Request Body:**
```json
{
    "items": [
        {
            "ingredient_id": 1,
            "quantity_needed": 50.0,
            "unit_id": 2
        }
    ]
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "overall_status": "sufficient",
        "items": [
            {
                "ingredient_id": 1,
                "status": "sufficient",
                "available_quantity": 75.5,
                "needed_quantity": 50.0,
                "shortage": 0
            }
        ]
    }
}
```

### Get FIFO Details
```http
GET /api/fifo-details/<inventory_id>
```

**Response:**
```json
{
    "success": true,
    "data": {
        "ingredient_name": "Coconut Oil",
        "total_available": 250.5,
        "lots": [
            {
                "id": 1,
                "quantity": 100.0,
                "cost_per_unit": 0.15,
                "expiration_date": "2024-10-15",
                "lot_number": "LOT001"
            }
        ]
    }
}
```

## Alert Management

### Get Dashboard Alerts
```http
GET /api/dashboard-alerts
```

**Response:**
```json
{
    "success": true,
    "data": {
        "alerts": [
            {
                "id": 1,
                "type": "low_stock",
                "severity": "warning",
                "title": "Low Stock Alert",
                "message": "Coconut Oil is running low (25.5 oz remaining)",
                "ingredient_id": 1,
                "created_at": "2024-01-15T10:30:00Z"
            }
        ],
        "count": 1
    }
}
```

### Dismiss Alert
```http
POST /api/dismiss-alert
```

**Request Body:**
```json
{
    "alert_id": 1
}
```

## Unit Conversion

### Get Available Units
```http
GET /api/units
```

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "name": "Ounces",
            "symbol": "oz",
            "unit_type": "weight",
            "base_unit": false
        }
    ]
}
```

### Convert Units
```http
POST /api/convert-units
```

**Request Body:**
```json
{
    "from_unit_id": 1,
    "to_unit_id": 2,
    "quantity": 16.0,
    "ingredient_id": 1
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "converted_quantity": 1.0,
        "from_unit": "oz",
        "to_unit": "lb",
        "conversion_factor": 0.0625
    }
}
```

## Developer Endpoints

### Get Organizations (Developer Only)
```http
GET /api/admin/organizations
```

**Requires**: Developer user type

### Switch Organization Context (Developer Only)
```http
POST /api/admin/switch-organization
```

**Request Body:**
```json
{
    "organization_id": 1
}
```

## Billing Management

### Upgrade Subscription
```http
POST /billing/upgrade
```

### Checkout
```http
POST /billing/checkout/<tier>/<billing_cycle>
POST /billing/checkout/<tier>
```

### Customer Portal
```http
GET /billing/customer-portal
```

### Cancel Subscription
```http
POST /billing/cancel-subscription
```

### Stripe Webhook
```http
POST /billing/webhooks/stripe
```

## Container Management

### Get Available Containers
```http
GET /api/available-containers/<int:recipe_id>
GET /api/containers/available
```

### Batch Container Management
```http
GET /api/batches/<int:batch_id>/containers
GET /api/batches/<int:batch_id>/containers/<int:container_id>
POST /api/batches/<int:batch_id>/containers/<int:container_id>/adjust
```

### Debug Containers
```http
GET /api/debug-containers
```

## Error Codes

### HTTP Status Codes
- `200`: Success
- `400`: Bad Request (validation errors)
- `401`: Unauthorized (not logged in)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found
- `500`: Internal Server Error

### Custom Error Types
- `validation_error`: Input validation failed
- `permission_denied`: User lacks required permission
- `organization_limit`: Subscription limit exceeded
- `stock_insufficient`: Not enough inventory available
- `batch_in_progress`: Cannot modify active batch

## Rate Limiting

### Current Limits
- General API: 100 requests per minute per user
- Batch operations: 10 requests per minute per user
- Inventory adjustments: 20 requests per minute per user

### Rate Limit Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Pagination

### Standard Pagination
```json
{
    "pagination": {
        "page": 1,
        "pages": 10,
        "per_page": 20,
        "total": 195,
        "has_next": true,
        "has_prev": false
    }
}
```

### Pagination Parameters
- `page` (int): Page number (1-based)
- `per_page` (int): Items per page (default: 20, max: 100)

## WebSocket Events (Future)

### Real-time Updates
```javascript
// Batch status updates
socket.on('batch_status_change', (data) => {
    // Update UI with new batch status
});

// Inventory alerts
socket.on('low_stock_alert', (data) => {
    // Show new alert notification
});
```

## SDK Examples

### JavaScript/TypeScript
```javascript
class BatchTrackAPI {
    constructor(baseURL, csrfToken) {
        this.baseURL = baseURL;
        this.csrfToken = csrfToken;
    }

    async checkStock(ingredients) {
        const response = await fetch(`${this.baseURL}/api/check-stock`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({ items: ingredients })
        });

        return response.json();
    }
}
```

### Python (for testing)
```python
import requests

class BatchTrackAPI:
    def __init__(self, base_url, session_cookies):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.cookies.update(session_cookies)

    def check_stock(self, ingredients):
        response = self.session.post(
            f"{self.base_url}/api/check-stock",
            json={"items": ingredients}
        )
        return response.json()
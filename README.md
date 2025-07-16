# BatchTrack

**BatchTrack** is a production and inventory management tool designed to help makers manage recipes, track batches, and generate labeled products.

## Features

- Start, cancel, and finish batches
- Assign label codes with recipe prefixes
- Upload product images and QR/barcode links
- Track units for ingredients vs. product output
- Admin panel to manage inventory and product units
- Ready for integration with Shopify or Etsy

## Getting Started

### Install dependencies:
```bash
pip install -r requirements.txt
```

### Run the app:
```bash
flask run
```

## Common Definitions & Architectural Guidelines

### FIFO Code Format
**All inventory event references must use the consistent `fifo_code` format across the system:**
- Expiration tables, inventory history tables, product SKU history tables, etc.
- Use `entry.fifo_code` when available, fallback to `entry.lot_number`, then `lot-{entry.id}`
- This ensures consistent display of inventory event codes throughout the application

### Core Data Identifiers
- **Inventory Item ID**: Primary identifier for all inventory items
- **Item Quantity**: Main quantity identifier - all other quantities (available, expired, reserved) are derivatives
- **Organization ID**: All data must be scoped to organizations for multi-tenant support
- **FIFO Entry ID**: Unique identifier for each inventory batch/lot

### Key Services
- **FIFO Service** (`app/blueprints/fifo/services.py`): Handles all FIFO inventory tracking and deduction logic
- **Stock Check Service** (`app/services/stock_check.py`): Centralized inventory availability checking
- **Unit Conversion Service** (`app/services/unit_conversion.py`): Handles all unit conversions with custom mappings
- **Inventory Adjustment Service** (`app/services/inventory_adjustment.py`): Manages all inventory changes and logging
- **Expiration Service** (`app/blueprints/expiration/services.py`): Tracks and alerts on expiring inventory
- **Reservation Service** (`app/services/reservation_service.py`): Manages inventory reservations for orders

### Service Boundaries & Authority
- **FIFO Service**: Authoritative for inventory deduction order and batch tracking
- **Stock Check Service**: Authoritative for real-time availability calculations
- **Unit Conversion**: Authoritative for all measurement conversions
- **Database Models**: Single source of truth for data structure and relationships
- **Permission System**: Authoritative for user access control and organization scoping

### Data Flow Principles
1. All inventory changes must go through the Inventory Adjustment Service
2. FIFO deductions must use the FIFO Service for proper batch ordering
3. Stock checks must use the centralized Stock Check Service
4. Unit conversions must use the Unit Conversion Service with proper error handling
5. All user actions must be validated through the Permission System

## Notes

- Make sure to initialize the database using Flask-Migrate or `flask db init && flask db migrate && flask db upgrade`
- Add users manually or build a registration page
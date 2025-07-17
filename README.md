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

## Inventory Change Types (InventoryHistory)
Based on the inventory routes and services:

**Restocking:**
- `restock` - Inventory restocked
- `manual_addition` - Manual inventory addition
- `finished_batch` - Inventory added from completed batch

**Deductions:**
- `spoil` - Inventory spoiled
- `trash` - Inventory trashed
- `damaged` - Inventory damaged
- `tester` - Used for testing
- `batch` - Used in batch production

**Adjustments:**
- `recount` - Inventory recount
- `cost_override` - Cost adjustment
- `unit_conversion` - Unit change conversion
- `refunded` - Inventory refunded (cancelled batches)

**Quality Control:**
- `quality_fail` - Quality control failure

## Product Change Types (ProductHistory)

**Restocking:**
- `produced` - Product created from batch

**Sales:**
- `sold` - Product sold
- `shipped` - Product shipped
- `returned` - Product returned
- `gift` - Product given as gift

**Loss/Waste:**
- `damaged` - Product damaged
- `spoil` - Product spoiled
- `trash` - Product trashed
- `expired` - Product expired

## FIFO Prefixes

**Action Prefixes:**
- `SLD` - sold
- `SHP` - shipped
- `SPL` - spoil
- `TRS` - trash
- `DMG` - damaged
- `BCH` - batch (consolidated from batch/batch_usage)
- `RCN` - recount
- `REF` - refunded
- `RTN` - returned
- `CST` - cost_override
- `ADD` - manual_addition
- `TST` - tester
- `GFT` - gift
- `QFL` - quality_fail
- `TXN` - default for unknown types

**Special Display:**
- `finished_batch` entries show the batch label code instead of FIFO prefix

## Notes

- Make sure to initialize the database using Flask-Migrate or `flask db init && flask db migrate && flask db upgrade`
- Add users manually or build a registration page
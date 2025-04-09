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

## Notes

- Make sure to initialize the database using Flask-Migrate or `flask db init && flask db migrate && flask db upgrade`
- Add users manually or build a registration page
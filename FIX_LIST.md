
# BatchTrack Fix List

## Quick Add Ingredient Modal
- **Issue**: Quick add ingredient save reloads entire recipe page, losing current edits
- **Fix Required**: 
  - Update quick_add/routes.py to return JSON only
  - Modify quick add ingredient modal JS to update dropdowns without page reload
  - Keep recipe form state intact after ingredient addition

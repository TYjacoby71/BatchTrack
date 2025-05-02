
# BatchTrack Fix List

## Quick Add Feature Issues
- **Quick Add Ingredient Save**: Currently reloads entire recipe page, losing edits
  - Should save ingredient and return to page while maintaining edit state
  - Route needs to return JSON response instead of redirect
  - Frontend JS needs updating to handle JSON response

## Unit Conversion Issues
- **Custom Unit Creation**: Base unit and multiplier confusion
  - Clarify relationship between Unit table and CustomUnitMapping
  - Ensure consistent conversion path through base units
  - Review unit creation process in conversion routes

## Container Management
- **Container Selection Logic**: Needs improvement
  - Validate container selection uniqueness
  - Update available containers display
  - Fix auto-fill container logic

## Edit Ingredient Form Issues
- **Unit Selection Reset**: After page reload on edit ingredient form
  - Unit selection gets reset to default
  - Need to persist selected unit through page reloads
  - Fix form state preservation in edit_ingredient.html

## Stock Check System
- **Universal Stock Check**: Core service implementation needed
  - Centralize stock checking logic
  - Implement unified API endpoint
  - Add proper unit conversion handling

## Interface Improvements
- **Plan Production Page**: Needs UX refinements
  - Add clear container availability display
  - Improve flex mode visibility
  - Fix stock check button behavior
  - Update container selection interface

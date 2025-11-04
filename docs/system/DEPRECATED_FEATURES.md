
# Deprecated & Scrapped Features Log

## Density Reference System
- Status: Removed
- Original Location: `/data/density_reference.json`
- Related Files:
  - `templates/components/modals/density_reference_modal.html`
  - `blueprints/api/routes.py` (density reference endpoint)
  - `static/js/main.js` (density reference functionality)
- Purpose: Provided density reference data for ingredient conversions
- Reason for Removal: Simplified to use category-based density system instead

## Batch Plan Legacy Component
- Status: Deprecated
- Original Location: `templates/components/batch/plan_batch.html`
- Note: Replaced by new `templates/plan_production.html`

## Quick Add Unit Modal (Original Version)
- Status: Modified
- Location: `templates/components/modals/quick_add_unit_modal.html`
- Changes: Integrated into unified quick add system

## Legacy Routes
- `/api/density-reference` - Removed in favor of category-based density system
- Container-specific density endpoints consolidated

## Potential Future Restoration Candidates
1. Density Reference System - Could be useful for precise scientific measurements
2. Legacy batch planning interface - Alternative simplified view
3. Container-specific density overrides - For special case ingredients

## Migration Notes
Keep this log updated when deprecating features for potential future restoration or reference.

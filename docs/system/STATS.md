# Statistics & Analytics Notes

## Recipe Library Metrics

`AnalyticsDataService.get_recipe_library_metrics()` now publishes recipe-specific data for dashboards and the public library UI:

| Field | Description |
| --- | --- |
| `total_public` | Count of recipes that are marked public, published, not blocked, and have `marketplace_status == 'listed'`. |
| `total_for_sale` | Number of public recipes that are currently for sale. |
| `blocked_listings` | Recipes hidden by moderation (`marketplace_blocked = true`). |
| `average_sale_price` | Mean of `Recipe.sale_price` for active, for-sale listings. |
| `average_yield_per_dollar` | Average `(predicted_yield / avg_cost_per_batch)` derived from `RecipeStats`. |
| `top_group_name` / `top_group_count` | Product group with the most live listings. |
| `sale_percentage` | Percentage of public recipes that are currently for sale. |
| `batchtrack_native_count` | Number of listings authored by BatchTrack (“native” recipes). |
| `total_downloads` / `total_purchases` | Rollups of the per-recipe counters tracking estimated downloads/purchases. |

These values appear in:

1. The developer **System Statistics** page (new row of cards for library metrics).
2. The hero cards on `library/recipe_library.html`.

## System Overview Payload

`AnalyticsDataService.get_system_overview()` embeds a subset of recipe metrics so any dashboard can display marketplace health:

```json
{
  "public_recipes": 42,
  "recipes_for_sale": 18,
  "blocked_recipes": 2,
  "average_recipe_price": 19.25,
  "average_yield_per_dollar": 2.4,
  "batchtrack_native_recipes": 6,
  "total_recipe_downloads": 880,
  "total_recipe_purchases": 210
}
```

## Usage Guidelines

- Always call the analytics service instead of writing ad-hoc aggregate queries in a route.
- The cache key `analytics:recipe_library` can be force-refreshed via `?refresh=1` on `/developer/system-statistics`.
- `RecipeStats` should be kept up to date (batch completion hooks already do this) to ensure `average_yield_per_dollar` remains accurate.

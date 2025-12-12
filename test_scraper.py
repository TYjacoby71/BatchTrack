
#!/usr/bin/env python3
"""
Test script for TGSC scraper with sample HTML data.
"""

from data_builder.scrapers import TGSCScraper

def test_scraper_with_sample_html():
    """Test the scraper with sample HTML content."""
    
    # Sample HTML that mimics TGSC formula structure
    sample_html = '''
    <html>
    <body>
    <table>
    <tr><td class="dmow1" colspan="3">Sample Lavender Formula</td></tr>
    <tr><td class="dmow3" colspan="3">Application: Perfume</td></tr>
    <tr><td class="dmow2" colspan="3">A beautiful lavender blend</td></tr>
    <tr><td class="dmow5">10.0</td><td colspan="2">Lavender Essential Oil</td></tr>
    <tr><td class="dmow5">5.0</td><td colspan="2">Linalool</td></tr>
    <tr><td class="dmow5">85.0</td><td colspan="2">Ethanol</td></tr>
    <tr><td class="dmow5">Total</td></tr>
    </table>
    </body>
    </html>
    '''
    
    # Create scraper instance
    scraper = TGSCScraper("", "", "test_sample")
    
    # Test parsing directly with sample HTML
    formulas, ingredients = scraper.parse_formulas(sample_html)
    
    print("=== Test Results ===")
    print(f"Found {len(formulas)} formulas")
    print(f"Found {len(ingredients)} ingredients")
    
    if formulas:
        print(f"Formula name: {formulas[0]['name']}")
        
    if ingredients:
        for ing in ingredients:
            print(f"- {ing['ingredients']}: {ing['percentage']}%")
    
    # Write test CSV files
    if formulas or ingredients:
        formula_headers = ["id", "name", "application", "description", "total"]
        ingredient_headers = ["id", "ingredients", "percentage", "100 pct", "website", "total"]
        
        scraper.write_csv("test_formulas.csv", formulas, formula_headers)
        scraper.write_csv("test_ingredients.csv", ingredients, ingredient_headers)
        
        print("\nGenerated test CSV files:")
        print("- test_formulas.csv")
        print("- test_ingredients.csv")
        
        # Copy to data sources if successful
        try:
            import shutil
            shutil.copy("test_ingredients.csv", "data_builder/ingredients/data_sources/tgsc_ingredients.csv")
            print("- Copied to data_builder/ingredients/data_sources/tgsc_ingredients.csv")
        except Exception as e:
            print(f"Could not copy to data sources: {e}")

if __name__ == "__main__":
    test_scraper_with_sample_html()

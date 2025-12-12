"""TGSC (The Good Scents Company) scraper for ingredient data and attributes."""
import csv
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
import urllib.parse

# Base URLs for different ingredient categories
TGSC_BASE_URL = "https://www.thegoodscentscompany.com"
TGSC_SEARCH_URL = f"{TGSC_BASE_URL}/search/fragrance.html"

# Category endpoints for ingredient discovery
TGSC_INGREDIENT_CATEGORIES = {
    "categories": f"{TGSC_BASE_URL}/categories.html"
}


class TGSCIngredientScraper:
    """Scraper for The Good Scents Company ingredient data and attributes."""

    def __init__(self, user_agent: str, delay_seconds: float = 1.0):
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.headers = {"User-Agent": user_agent}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def searchsingle(self, start: str, end: str, content: str) -> str:
        """Extract single match between start and end markers."""
        if end != "" and start != "":
            pattern = re.compile(f'{re.escape(start)}(.*?){re.escape(end)}', re.DOTALL | re.IGNORECASE)
        elif end == "":
            pattern = re.compile(re.escape(start) + r"\s*(.*)", re.IGNORECASE)
        elif start == "":
            pattern = re.compile(r"^(.*?)" + re.escape(end), re.IGNORECASE)

        match = re.search(pattern, content)
        return match.group(1).strip() if match else ""

    def searchmultiple(self, start: str, end: str, content: str) -> List[str]:
        """Extract multiple matches between start and end markers."""
        if end != "" and start != "":
            pattern = re.compile(f'{re.escape(start)}(.*?){re.escape(end)}', re.DOTALL | re.IGNORECASE)
        elif end == "":
            pattern = re.compile(re.escape(start) + r"\s*(.*)", re.IGNORECASE)
        elif start == "":
            pattern = re.compile(r"^(.*?)" + re.escape(end), re.IGNORECASE)

        matches = pattern.findall(content)
        return [match.strip() for match in matches]

    def fetch_html(self, url: str, save_filename: str = None) -> Optional[str]:
        """Fetch HTML content from URL with error handling and rate limiting."""
        try:
            print(f"Fetching: {url}")
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                html = response.text
                if save_filename:
                    with open(f"{save_filename}.html", "w", errors="ignore", encoding="utf-8") as fp:
                        fp.write(html)
                    print(f"HTML content saved to {save_filename}.html")

                time.sleep(self.delay_seconds)  # Rate limiting
                return html
            else:
                print(f"Failed to fetch {url}. Status code: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_ingredient_links(self, category_html: str) -> List[str]:
        """Extract ingredient detail page URLs from category listings."""
        ingredient_links = []

        # Look for ingredient links in various formats
        # Updated patterns to match current TGSC site structure
        link_patterns = [
            r'href="(/data/[^"]+\.html)"',  # Data pages (ingredient details)
            r'href="(/search/[^"]*\.html[^"]*)"',  # Search results
            r'<a[^>]+href="([^"]*(?:fragrance|ingredient|essential|oil)[^"]*\.html)"[^>]*>',
            r'href="([^"]*\.html)"'  # Any HTML page
        ]

        for pattern in link_patterns:
            matches = re.findall(pattern, category_html, re.IGNORECASE)
            for match in matches:
                if match.startswith('/'):
                    full_url = TGSC_BASE_URL + match
                elif match.startswith('http'):
                    full_url = match
                else:
                    full_url = TGSC_BASE_URL + '/' + match

                # Filter to only include likely ingredient pages
                if ('data/' in full_url or 
                    'fragrance' in full_url.lower() or 
                    'ingredient' in full_url.lower() or
                    'essential' in full_url.lower() or
                    'oil' in full_url.lower()) and full_url not in ingredient_links:
                    ingredient_links.append(full_url)

        return ingredient_links

    def parse_ingredient_data(self, html: str, url: str) -> Dict:
        """Parse ingredient page HTML to extract comprehensive data."""
        ingredient_data = {
            'url': url,
            'common_name': '',
            'botanical_name': '',
            'cas_number': '',
            'einecs_number': '',
            'fema_number': '',
            'category': '',
            'description': '',
            'odor_description': '',
            'flavor_description': '',
            'molecular_formula': '',
            'molecular_weight': '',
            'boiling_point': '',
            'melting_point': '',
            'density': '',
            'solubility': '',
            'synonyms': [],
            'uses': [],
            'safety_notes': '',
            'natural_occurrence': []
        }

        # Extract common name (usually in title or main heading)
        name_patterns = [
            r'<title>([^<]+?)(?:\s*-\s*The Good Scents Company)?</title>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'<h2[^>]*>([^<]+)</h2>'
        ]

        for pattern in name_patterns:
            name = self.searchsingle(pattern.split('(')[1].split(')')[0], '', html)
            if name and len(name) > 3:
                ingredient_data['common_name'] = re.sub(r'\s+', ' ', name).strip()
                break

        # CAS Number
        cas_patterns = [
            r'CAS[:\s]*(\d{1,7}-\d{2}-\d)',
            r'cas[:\s]*(\d{1,7}-\d{2}-\d)',
            r'(\d{1,7}-\d{2}-\d)'
        ]

        for pattern in cas_patterns:
            cas = re.search(pattern, html, re.IGNORECASE)
            if cas:
                ingredient_data['cas_number'] = cas.group(1)
                break

        # EINECS Number  
        einecs = self.searchsingle(r'EINECS[:\s]*(\d{3}-\d{3}-\d)', '', html)
        if einecs:
            ingredient_data['einecs_number'] = einecs

        # FEMA Number
        fema = self.searchsingle(r'FEMA[:\s]*(\d+)', '', html)
        if fema:
            ingredient_data['fema_number'] = fema

        # Botanical name
        botanical_patterns = [
            r'<i>([A-Z][a-z]+ [a-z]+)</i>',
            r'botanical[:\s]*([A-Z][a-z]+ [a-z]+)',
            r'species[:\s]*([A-Z][a-z]+ [a-z]+)'
        ]

        for pattern in botanical_patterns:
            botanical = re.search(pattern, html, re.IGNORECASE)
            if botanical:
                ingredient_data['botanical_name'] = botanical.group(1)
                break

        # Molecular formula and weight
        formula = self.searchsingle(r'molecular formula[:\s]*([A-Z0-9]+)', '', html)
        if formula:
            ingredient_data['molecular_formula'] = formula

        weight = self.searchsingle(r'molecular weight[:\s]*([0-9.]+)', '', html)
        if weight:
            ingredient_data['molecular_weight'] = weight

        # Physical properties
        bp = self.searchsingle(r'boiling point[:\s]*([0-9.-]+)', '', html)
        if bp:
            ingredient_data['boiling_point'] = bp

        mp = self.searchsingle(r'melting point[:\s]*([0-9.-]+)', '', html)
        if mp:
            ingredient_data['melting_point'] = mp

        density = self.searchsingle(r'density[:\s]*([0-9.]+)', '', html)
        if density:
            ingredient_data['density'] = density

        # Odor and flavor descriptions
        odor_desc = self.searchsingle(r'odor[:\s]*([^<\n]+)', '', html)
        if odor_desc:
            ingredient_data['odor_description'] = odor_desc[:500]  # Limit length

        flavor_desc = self.searchsingle(r'flavor[:\s]*([^<\n]+)', '', html)
        if flavor_desc:
            ingredient_data['flavor_description'] = flavor_desc[:500]

        # Extract synonyms (alternative names)
        synonym_section = self.searchsingle(r'synonyms?[:\s]*([^<]+)', '', html)
        if synonym_section:
            synonyms = [s.strip() for s in re.split(r'[,;]', synonym_section) if s.strip()]
            ingredient_data['synonyms'] = synonyms[:10]  # Limit to top 10

        # Natural occurrence
        occurrence_text = self.searchsingle(r'(?:found in|occurs in|natural occurrence)[:\s]*([^<]+)', '', html)
        if occurrence_text:
            occurrences = [o.strip() for o in re.split(r'[,;]', occurrence_text) if o.strip()]
            ingredient_data['natural_occurrence'] = occurrences[:15]

        return ingredient_data

    def scrape_category(self, category_name: str, category_url: str, max_ingredients: int = 50) -> List[Dict]:
        """Scrape all ingredients from a specific category."""
        print(f"\n{'='*60}")
        print(f"SCRAPING CATEGORY: {category_name.upper()}")
        print(f"URL: {category_url}")
        print(f"{'='*60}")

        # Fetch category page
        category_html = self.fetch_html(category_url, f"category_{category_name}")
        if not category_html:
            print(f"❌ Failed to fetch category page: {category_name}")
            return []

        # Extract ingredient links
        ingredient_links = self.extract_ingredient_links(category_html)
        print(f"📋 Found {len(ingredient_links)} ingredient links")

        if not ingredient_links:
            print("⚠️  No ingredient links found - checking page structure...")
            return []

        # Limit ingredients per category
        ingredient_links = ingredient_links[:max_ingredients]
        ingredients_data = []

        # Scrape each ingredient
        for i, link in enumerate(ingredient_links, 1):
            print(f"\n[{i}/{len(ingredient_links)}] Processing: {link}")

            html = self.fetch_html(link)
            if html:
                ingredient_data = self.parse_ingredient_data(html, link)
                if ingredient_data['common_name']:  # Only save if we got a name
                    ingredients_data.append(ingredient_data)
                    print(f"✅ Extracted: {ingredient_data['common_name']}")
                else:
                    print("⚠️  No name found - skipping")
            else:
                print("❌ Failed to fetch ingredient page")

        print(f"\n🎉 Category {category_name} complete: {len(ingredients_data)} ingredients extracted")
        return ingredients_data

    def save_ingredients_csv(self, ingredients: List[Dict], filename: str):
        """Save ingredients data to CSV file."""
        if not ingredients:
            print("No ingredients to save")
            return

        fieldnames = [
            'common_name', 'botanical_name', 'cas_number', 'einecs_number', 
            'fema_number', 'category', 'molecular_formula', 'molecular_weight',
            'boiling_point', 'melting_point', 'density', 'odor_description',
            'flavor_description', 'synonyms', 'natural_occurrence', 'url'
        ]

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for ingredient in ingredients:
                    # Convert lists to semicolon-separated strings
                    row = ingredient.copy()
                    for field in ['synonyms', 'natural_occurrence', 'uses']:
                        if field in row and isinstance(row[field], list):
                            row[field] = '; '.join(row[field])
                    writer.writerow(row)

            print(f"💾 Saved {len(ingredients)} ingredients to {filename}")

        except Exception as e:
            print(f"❌ Error saving CSV: {e}")


def main():
    """Main function to scrape TGSC ingredient database."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape TGSC ingredient database")
    parser.add_argument("--max-ingredients", type=int, default=30, 
                       help="Maximum number of ingredients to scrape in total (default: 30)")
    args = parser.parse_args()

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    scraper = TGSCIngredientScraper(user_agent, delay_seconds=2.0)
    all_ingredients = []

    print("🚀 TGSC Ingredient Database Scraper")
    print("=" * 50)
    print(f"📊 Max ingredients to scrape: {args.max_ingredients}")

    # Scrape each category
    total_scraped = 0
    max_total_ingredients = args.max_ingredients

    for category_name, category_url in TGSC_INGREDIENT_CATEGORIES.items():
        # Check if we have reached the maximum total ingredients limit
        if total_scraped >= max_total_ingredients:
            print(f"\nReached maximum total ingredients limit ({max_total_ingredients}). Stopping scrape.")
            break

        # Determine how many ingredients to scrape from this category
        ingredients_to_scrape = max_total_ingredients - total_scraped
        
        try:
            ingredients = scraper.scrape_category(category_name, category_url, max_ingredients=ingredients_to_scrape)

            if ingredients:
                # Save category-specific file
                category_filename = f"tgsc_{category_name}_ingredients.csv"
                scraper.save_ingredients_csv(ingredients, category_filename)

                # Add to master list
                for ingredient in ingredients:
                    ingredient['category'] = category_name
                all_ingredients.extend(ingredients)
                total_scraped += len(ingredients) # Update total scraped count

        except Exception as e:
            print(f"❌ Error scraping category {category_name}: {e}")
            continue

    # Save master file
    if all_ingredients:
        master_filename = "tgsc_all_ingredients.csv"
        scraper.save_ingredients_csv(all_ingredients, master_filename)

        # Copy to data sources directory
        import shutil
        target_dir = Path(__file__).parent.parent / "ingredients" / "data_sources"
        target_file = target_dir / "tgsc_ingredients.csv"

        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(master_filename, target_file)
        print(f"📋 Copied master file to {target_file}")
        print("Ready for ingredient compilation!")

    print(f"\n🎊 SCRAPING COMPLETE!")
    print(f"📊 Total ingredients extracted: {len(all_ingredients)}")
    print(f"📁 Files generated:")
    for category in TGSC_INGREDIENT_CATEGORIES.keys():
        # Only list generated files if they were potentially created
        # This logic might need refinement if we break early
        print(f"   - tgsc_{category}_ingredients.csv")
    print(f"   - tgsc_all_ingredients.csv")


if __name__ == "__main__":
    main()
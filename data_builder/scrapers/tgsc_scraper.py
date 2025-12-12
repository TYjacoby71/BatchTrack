"""TGSC (The Good Scents Company) scraper for ingredient data and attributes."""
import csv
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Base URLs for different ingredient categories
TGSC_BASE_URL = "https://www.thegoodscentscompany.com"
TGSC_SEARCH_URL = f"{TGSC_BASE_URL}/search/fragrance.html"

# Category endpoints for ingredient discovery
TGSC_INGREDIENT_CATEGORIES = {
    "essential_oils": f"{TGSC_BASE_URL}/essentlx-a.html",
    "absolutes": f"{TGSC_BASE_URL}/abs-az.html",
    "extracts": f"{TGSC_BASE_URL}/extractx-a.html",
    "aromatic_ingredients": f"{TGSC_BASE_URL}/rawmatex-a.html",
    "all_ingredients": f"{TGSC_BASE_URL}/allprod-a.html",
    "concretes": f"{TGSC_BASE_URL}/con-az.html",
    "cosmetic_ingredients": f"{TGSC_BASE_URL}/cosmetix-a.html",
    "botanical_species": f"{TGSC_BASE_URL}/botaspes-a.html"
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

        # Look for the main content table with ingredient links
        # TGSC uses JavaScript onclick handlers, so we need to extract from those
        onclick_pattern = r"onclick=\"openMainWindow\('([^']+)'\)"

        matches = re.findall(onclick_pattern, category_html)

        for match in matches:
            if match.startswith('/data/'):
                full_url = TGSC_BASE_URL + match
                ingredient_links.append(full_url)

        # Also try direct href links to /data/ pages
        href_pattern = r'href="(/data/[^"]+\.html)"'
        href_matches = re.findall(href_pattern, category_html, re.IGNORECASE)

        for match in href_matches:
            full_url = TGSC_BASE_URL + match
            if full_url not in ingredient_links:
                ingredient_links.append(full_url)

        return ingredient_links

    def clean_text(self, text: str) -> str:
        """Clean extracted text by removing HTML entities, tags, and normalizing whitespace."""
        if not text:
            return ""
        
        import html
        # Decode HTML entities
        text = html.unescape(text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove common scraping artifacts
        text = re.sub(r'""">Search', '', text)
        text = re.sub(r'=hp&amp;.*?"">Search', '', text)
        text = re.sub(r'scompany\.com/data/[^"]*\.html[^"]*', '', text)
        text = re.sub(r'&amp;.*?Search', '', text)
        text = re.sub(r'""">.*?</.*?>', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Filter out very short or meaningless text
        if len(text) < 3 or text.lower() in ['search', 'references', 'agents', 'ing', 'and']:
            return ""
            
        return text

    def extract_clean_content(self, html: str, patterns: List[str]) -> str:
        """Extract content using multiple patterns and clean the result."""
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
                cleaned = self.clean_text(content)
                if cleaned and len(cleaned) > 3:
                    return cleaned
        return ""

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

        # Extract common name from title
        title_match = re.search(r'<title>([^<]+?)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # Clean up title - remove "The Good Scents Company" and other generic text
            title = re.sub(r'\s*-\s*The Good Scents Company.*', '', title)
            title = re.sub(r'\s*Information.*', '', title)
            title = re.sub(r'\s*Catalog.*', '', title)

            # Extract CAS number from title if present and remove it from name
            cas_in_title = re.search(r'(\d{1,7}-\d{2}-\d)', title)
            if cas_in_title and not ingredient_data['cas_number']:
                ingredient_data['cas_number'] = cas_in_title.group(1)

            # Remove CAS numbers from the name
            title = re.sub(r'\s*\d{1,7}-\d{2}-\d\s*', ' ', title)
            # Remove extra whitespace
            title = re.sub(r'\s+', ' ', title)
            if title and len(title) > 2:
                ingredient_data['common_name'] = title.strip()

        # If no good title, try to extract from page content
        if not ingredient_data['common_name']:
            # Look for ingredient name in various places in the HTML
            name_patterns = [
                r'<td><a[^>]*>([^<]+)</a>',  # Link text in table cells
                r'<h1[^>]*>([^<]+)</h1>',
                r'<h2[^>]*>([^<]+)</h2>',
            ]

            for pattern in name_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()

                    # Extract CAS number from name if present
                    cas_in_name = re.search(r'(\d{1,7}-\d{2}-\d)', name)
                    if cas_in_name and not ingredient_data['cas_number']:
                        ingredient_data['cas_number'] = cas_in_name.group(1)

                    # Clean CAS numbers from extracted names
                    name = re.sub(r'\s*\d{1,7}-\d{2}-\d\s*', ' ', name)
                    name = re.sub(r'\s+', ' ', name).strip()
                    if name and len(name) > 2 and not name.lower().startswith('the good'):
                        ingredient_data['common_name'] = name
                        break

        # Extract CAS Number - multiple patterns
        cas_patterns = [
            r'CAS[:\s#-]*(\d{1,7}-\d{2}-\d)',
            r'(\d{1,7}-\d{2}-\d)',  # Standalone CAS number
            r'Registry Number[:\s]*(\d{1,7}-\d{2}-\d)',
            r'Chemical Abstracts[:\s]*(\d{1,7}-\d{2}-\d)'
        ]
        
        for pattern in cas_patterns:
            cas_match = re.search(pattern, html, re.IGNORECASE)
            if cas_match and not ingredient_data['cas_number']:
                ingredient_data['cas_number'] = cas_match.group(1)
                break

        # Extract EINECS Number - multiple patterns
        einecs_patterns = [
            r'EINECS[:\s#-]*(\d{3}-\d{3}-\d)',
            r'EC[:\s#-]*(\d{3}-\d{3}-\d)',
            r'ELINCS[:\s#-]*(\d{3}-\d{3}-\d)',
            r'European Inventory[:\s]*(\d{3}-\d{3}-\d)'
        ]
        
        for pattern in einecs_patterns:
            einecs_match = re.search(pattern, html, re.IGNORECASE)
            if einecs_match:
                ingredient_data['einecs_number'] = einecs_match.group(1)
                break

        # Extract FEMA Number - multiple patterns
        fema_patterns = [
            r'FEMA[:\s#-]*(\d+)',
            r'Flavor and Extract[:\s]*(\d+)',
            r'GRAS[:\s]*(\d+)'
        ]
        
        for pattern in fema_patterns:
            fema_match = re.search(pattern, html, re.IGNORECASE)
            if fema_match:
                ingredient_data['fema_number'] = fema_match.group(1)
                break

        # Extract uses/applications with better cleaning
        uses_patterns = [
            r'- ([^<>"]*?(?:agents?|ingredients?|conditioning|protecting)[^<>"]*?)(?:\.|"|/>)',
            r'Use\(?s?\)?[:\s]*([^<>"]{10,200})(?:\.|"|<|$)',
            r'Application[:\s]*([^<>"]{10,200})(?:\.|"|<|$)',
            r'Used\s+(?:in|for|as)[:\s]*([^<>"]{10,200})(?:\.|"|<|$)',
            r'Function[:\s]*([^<>"]{10,200})(?:\.|"|<|$)',
            r'Purpose[:\s]*([^<>"]{10,200})(?:\.|"|<|$)'
        ]
        
        uses_desc = self.extract_clean_content(html, uses_patterns)
        if uses_desc:
            ingredient_data['description'] = uses_desc[:300]
            # Split into individual uses
            uses_list = [use.strip() for use in re.split(r'[,;]', uses_desc) if use.strip() and len(use.strip()) > 2]
            ingredient_data['uses'] = uses_list[:5]

        # Botanical name - more comprehensive patterns
        botanical_patterns = [
            r'<i>([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)</i>',  # Italic scientific names
            r'botanical[:\s]*([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)',
            r'species[:\s]*([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)',
            r'Scientific name[:\s]*([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)',
            r'Latin name[:\s]*([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)',
            r'Genus[:\s]*([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)',
            r'\b([A-Z][a-z]+\s+[a-z]+)\s+(?:extract|oil|essence)',  # From product names
        ]

        for pattern in botanical_patterns:
            botanical = re.search(pattern, html, re.IGNORECASE)
            if botanical:
                botanical_name = botanical.group(1).strip()
                # Validate it looks like a proper binomial name
                if len(botanical_name.split()) >= 2 and botanical_name[0].isupper():
                    ingredient_data['botanical_name'] = botanical_name
                    break

        # Molecular formula and weight - enhanced patterns
        formula_patterns = [
            r'molecular formula[:\s]*([A-Z0-9]+)',
            r'formula[:\s]*([A-Z0-9]{3,})',
            r'chemical formula[:\s]*([A-Z0-9]+)'
        ]
        
        for pattern in formula_patterns:
            formula_match = re.search(pattern, html, re.IGNORECASE)
            if formula_match:
                ingredient_data['molecular_formula'] = formula_match.group(1)
                break

        weight_patterns = [
            r'molecular weight[:\s]*([0-9.,]+)',
            r'mol(?:ecular)?\s*wt[:\s]*([0-9.,]+)',
            r'MW[:\s]*([0-9.,]+)',
            r'weight[:\s]*([0-9.,]+)'
        ]
        
        for pattern in weight_patterns:
            weight_match = re.search(pattern, html, re.IGNORECASE)
            if weight_match:
                ingredient_data['molecular_weight'] = weight_match.group(1)
                break

        # Physical properties - enhanced patterns
        bp_patterns = [
            r'boiling point[:\s]*([0-9.,°C°F-]+)',
            r'b\.p\.?[:\s]*([0-9.,°C°F-]+)',
            r'BP[:\s]*([0-9.,°C°F-]+)',
            r'boils[:\s]*(?:at)?[:\s]*([0-9.,°C°F-]+)'
        ]
        
        for pattern in bp_patterns:
            bp_match = re.search(pattern, html, re.IGNORECASE)
            if bp_match:
                ingredient_data['boiling_point'] = bp_match.group(1)
                break

        mp_patterns = [
            r'melting point[:\s]*([0-9.,°C°F-]+)',
            r'm\.p\.?[:\s]*([0-9.,°C°F-]+)',
            r'MP[:\s]*([0-9.,°C°F-]+)',
            r'melts[:\s]*(?:at)?[:\s]*([0-9.,°C°F-]+)'
        ]
        
        for pattern in mp_patterns:
            mp_match = re.search(pattern, html, re.IGNORECASE)
            if mp_match:
                ingredient_data['melting_point'] = mp_match.group(1)
                break

        density_patterns = [
            r'density[:\s]*([0-9.,]+)',
            r'specific gravity[:\s]*([0-9.,]+)',
            r'd20[:\s]*([0-9.,]+)',
            r'ρ[:\s]*([0-9.,]+)'
        ]
        
        for pattern in density_patterns:
            density_match = re.search(pattern, html, re.IGNORECASE)
            if density_match:
                ingredient_data['density'] = density_match.group(1)
                break

        # Solubility extraction with better patterns
        solubility_patterns = [
            r'solubility[:\s]*([^<>"]{10,200})(?:\.|"|<|$)',
            r'soluble[:\s]*(?:in)?[:\s]*([^<>"]{10,200})(?:\.|"|<|$)',
            r'dissolves[:\s]*(?:in)?[:\s]*([^<>"]{10,200})(?:\.|"|<|$)',
            r'sol\.[:\s]*([^<>"]{10,200})(?:\.|"|<|$)'
        ]
        
        solubility_desc = self.extract_clean_content(html, solubility_patterns)
        if solubility_desc:
            ingredient_data['solubility'] = solubility_desc[:200]

        # Odor and flavor descriptions - improved extraction
        odor_patterns = [
            r'Has (?:an? )?([^<>"]+?) type odor',
            r'odor[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)',
            r'odour[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)',
            r'smell[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)',
            r'scent[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)',
            r'aroma[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)',
            r'fragrance[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)'
        ]
        
        odor_desc = self.extract_clean_content(html, odor_patterns)
        if odor_desc:
            ingredient_data['odor_description'] = odor_desc[:300]

        flavor_patterns = [
            r'Has (?:an? )?([^<>"]+?) type flavor',
            r'flavor[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)',
            r'flavour[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)',
            r'taste[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)',
            r'gustatory[:\s]*([^<>"]{5,200}?)(?:\s*\.|"|<|$)'
        ]
        
        flavor_desc = self.extract_clean_content(html, flavor_patterns)
        if flavor_desc:
            ingredient_data['flavor_description'] = flavor_desc[:300]

        # Extract synonyms with better cleaning
        synonym_patterns = [
            r'synonyms?[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'also known as[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'alternative names?[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'other names?[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'aliases?[:\s]*([^<>"]{10,300})(?:\.|"|<|$)'
        ]
        
        synonym_section = self.extract_clean_content(html, synonym_patterns)
        if synonym_section:
            synonyms = [s.strip() for s in re.split(r'[,;|]', synonym_section) if s.strip() and len(s.strip()) > 2]
            ingredient_data['synonyms'] = synonyms[:10]

        # Natural occurrence extraction with cleaning
        occurrence_patterns = [
            r'(?:found in|occurs in|natural occurrence)[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'(?:natural|naturally)\s+(?:found|occurs?)[:\s]*(?:in)?[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'source[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'derived from[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'obtained from[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'present in[:\s]*([^<>"]{10,300})(?:\.|"|<|$)'
        ]
        
        occurrence_text = self.extract_clean_content(html, occurrence_patterns)
        if occurrence_text:
            occurrences = [o.strip() for o in re.split(r'[,;|]', occurrence_text) if o.strip() and len(o.strip()) > 2]
            ingredient_data['natural_occurrence'] = occurrences[:10]

        # Safety notes extraction with cleaning
        safety_patterns = [
            r'safety[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'hazard[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'warning[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'caution[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'precaution[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'toxicity[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'health effects?[:\s]*([^<>"]{10,300})(?:\.|"|<|$)',
            r'side effects?[:\s]*([^<>"]{10,300})(?:\.|"|<|$)'
        ]
        
        safety_text = self.extract_clean_content(html, safety_patterns)
        if safety_text:
            ingredient_data['safety_notes'] = safety_text[:300]

        return ingredient_data

    def scrape_category(self, category_name: str, category_url: str, max_ingredients: int = 50, resume_from_url: Optional[str] = None) -> List[Dict]:
        """Scrape all ingredients from a specific category, with resume capability."""
        print(f"\n{'='*60}")
        print(f"SCRAPING CATEGORY: {category_name.upper()}")
        print(f"URL: {category_url}")
        if resume_from_url:
            print(f"Resuming from: {resume_from_url}")
        print(f"{'='*60}")

        # Fetch category page
        category_html = self.fetch_html(category_url)
        if not category_html:
            print(f"❌ Failed to fetch category page: {category_name}")
            return []

        # Extract ingredient links
        all_ingredient_links = self.extract_ingredient_links(category_html)
        print(f"📋 Found {len(all_ingredient_links)} ingredient links")

        if not all_ingredient_links:
            print("⚠️  No ingredient links found - checking page structure...")
            return []

        # Determine start index for resuming
        start_index = 0
        if resume_from_url:
            try:
                start_index = all_ingredient_links.index(resume_from_url) + 1
                print(f"Resuming scrape at index: {start_index}")
            except ValueError:
                print(f"Warning: Resume URL '{resume_from_url}' not found in category links. Starting from beginning.")
                start_index = 0
        
        # Limit ingredients per category
        ingredient_links_to_process = all_ingredient_links[start_index : start_index + max_ingredients]
        
        if not ingredient_links_to_process:
            print("No ingredients to scrape in this category for the current limit.")
            return []

        ingredients_data = []

        # Data quality tracking
        cas_count = 0
        einecs_count = 0
        description_count = 0

        # Scrape each ingredient
        for i, link in enumerate(ingredient_links_to_process, start=start_index + 1):
            print(f"\n[{i}/{len(all_ingredient_links)}] Processing: {link}")

            html = self.fetch_html(link)
            if html:
                ingredient_data = self.parse_ingredient_data(html, link)
                if ingredient_data['common_name']:  # Only save if we got a name
                    ingredients_data.append(ingredient_data)

                    # Track data quality
                    if ingredient_data.get('cas_number'):
                        cas_count += 1
                    if ingredient_data.get('einecs_number'):
                        einecs_count += 1
                    if ingredient_data.get('description'):
                        description_count += 1

                    print(f"✅ Extracted: {ingredient_data['common_name']}")
                    if ingredient_data.get('cas_number'):
                        print(f"   CAS: {ingredient_data['cas_number']}")
                else:
                    print("⚠️  No name found - skipping")
            else:
                print("❌ Failed to fetch ingredient page")

        # Data quality summary
        print(f"\n📊 Data Quality Summary for {category_name}:")
        print(f"   Total ingredients processed in this run: {len(ingredients_data)}")
        if len(ingredients_data) > 0:
            print(f"   CAS numbers found: {cas_count} ({cas_count/len(ingredients_data)*100:.1f}%)")
            print(f"   EINECS numbers found: {einecs_count} ({einecs_count/len(ingredients_data)*100:.1f}%)")
            print(f"   Descriptions found: {description_count} ({description_count/len(ingredients_data)*100:.1f}%)")

        print(f"\n🎉 Category {category_name} scrape complete: {len(ingredients_data)} ingredients extracted in this run")
        return ingredients_data
    
    def get_last_scraped_url(self, category_name: str, csv_filepath: str) -> Optional[str]:
        """Reads the CSV and returns the URL of the last scraped item for a given category."""
        if not Path(csv_filepath).exists():
            return None

        try:
            with open(csv_filepath, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                # Filter by category and get the last entry
                category_entries = [row for row in reader if row.get('category') == category_name]
                if category_entries:
                    return category_entries[-1].get('url')
        except Exception as e:
            print(f"⚠️ Error reading {csv_filepath} for resume: {e}")
        return None

    def save_ingredients_csv(self, ingredients: List[Dict], filename: str):
        """Save ingredients data to CSV file."""
        if not ingredients:
            print("No ingredients to save")
            return

        fieldnames = [
            'common_name', 'botanical_name', 'cas_number', 'einecs_number', 
            'fema_number', 'category', 'molecular_formula', 'molecular_weight',
            'boiling_point', 'melting_point', 'density', 'odor_description',
            'flavor_description', 'description', 'uses', 'safety_notes',
            'solubility', 'synonyms', 'natural_occurrence', 'url'
        ]

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for ingredient in ingredients:
                    # Convert lists to semicolon-separated strings and filter to fieldnames
                    row = {}
                    for field in fieldnames:
                        if field in ingredient:
                            value = ingredient[field]
                            if isinstance(value, list):
                                row[field] = '; '.join(str(v) for v in value)
                            else:
                                row[field] = str(value) if value is not None else ''
                        else:
                            row[field] = ''
                    writer.writerow(row)

            print(f"💾 Saved {len(ingredients)} ingredients to {filename}")

        except Exception as e:
            print(f"❌ Error saving CSV: {e}")

def scrape_category_with_resume(scraper, category_name, category_url, max_ingredients, target_file):
    """Scrape a single category with resume capability."""
    # Check for existing progress
    last_scraped_url = scraper.get_last_scraped_url(category_name, str(target_file))

    try:
        ingredients = scraper.scrape_category(
            category_name, 
            category_url, 
            max_ingredients=max_ingredients,
            resume_from_url=last_scraped_url
        )

        if ingredients:
            # Add category info
            for ingredient in ingredients:
                ingredient['category'] = category_name

        return category_name, ingredients

    except Exception as e:
        print(f"❌ Error scraping category {category_name}: {e}")
        return category_name, []

def main():
    """Main function to scrape TGSC ingredient database with parallel processing."""
    import argparse

    parser = argparse.ArgumentParser(description="Scrape TGSC ingredient database")
    parser.add_argument("--max-ingredients", type=int, default=30, 
                       help="Maximum number of ingredients to scrape per category (default: 30)")
    parser.add_argument("--max-workers", type=int, default=3,
                       help="Maximum number of parallel workers (default: 3)")
    parser.add_argument("--resume", action="store_true",
                       help="Resume from last scraped position in each category")
    args = parser.parse_args()

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    scraper = TGSCIngredientScraper(user_agent, delay_seconds=1.5)  # Slightly faster for parallel

    # Create target directory and file path
    target_dir = Path(__file__).parent.parent / "ingredients" / "data_sources"
    target_file = target_dir / "tgsc_ingredients.csv"
    target_dir.mkdir(parents=True, exist_ok=True)

    print("🚀 TGSC Ingredient Database Scraper (Parallel)")
    print("=" * 60)
    print(f"📊 Max ingredients per category: {args.max_ingredients}")
    print(f"⚡ Max parallel workers: {args.max_workers}")
    print(f"🔄 Resume mode: {'Enabled' if args.resume else 'Disabled'}")

    all_ingredients = []

    # Load existing data if resuming
    if args.resume and target_file.exists():
        try:
            with open(target_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                existing_ingredients = list(reader)
                all_ingredients.extend(existing_ingredients)
                print(f"📋 Loaded {len(existing_ingredients)} existing ingredients")
        except Exception as e:
            print(f"⚠️  Error loading existing data: {e}")

    # Process categories in parallel
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        # Submit all category tasks
        futures = {
            executor.submit(
                scrape_category_with_resume, 
                scraper, 
                category_name, 
                category_url, 
                args.max_ingredients,
                target_file
            ): category_name 
            for category_name, category_url in TGSC_INGREDIENT_CATEGORIES.items()
        }

        # Process completed tasks
        for future in as_completed(futures):
            category_name = futures[future]
            try:
                category_name_result, ingredients = future.result()
                if ingredients:
                    # Remove existing ingredients from this category if resuming
                    if args.resume:
                        all_ingredients = [ing for ing in all_ingredients if ing.get('category') != category_name]

                    all_ingredients.extend(ingredients)
                    print(f"🎉 {category_name}: {len(ingredients)} ingredients completed")
                else:
                    print(f"⚠️  {category_name}: No new ingredients found")
            except Exception as e:
                print(f"❌ {category_name}: Failed with error: {e}")

    # Save consolidated results
    if all_ingredients:
        scraper.save_ingredients_csv(all_ingredients, str(target_file))
        print(f"📋 Saved {len(all_ingredients)} total ingredients to {target_file}")
        print("Ready for ingredient compilation!")
    else:
        print("⚠️  No ingredients were scraped")

    print(f"\n🎊 SCRAPING COMPLETE!")
    print(f"📊 Total ingredients: {len(all_ingredients)}")
    print(f"📁 File: {target_file}")


if __name__ == "__main__":
    main()
"""TGSC (The Good Scents Company) scraper for ingredient data and attributes."""
import csv
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup, NavigableString
import html

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
    "botanical_species": f"{TGSC_BASE_URL}/botaspes-a.html",
    "fixed_oils": f"{TGSC_BASE_URL}/fix-az.html",
    "resins_gums": f"{TGSC_BASE_URL}/resinx-a.html"
}


class TGSCIngredientScraper:
    """Scraper for The Good Scents Company ingredient data and attributes."""

    def __init__(self, user_agent: str, delay_seconds: float = 1.0):
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.headers = {"User-Agent": user_agent}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetch_html(self, url: str, save_filename: str = None) -> Optional[str]:
        """Fetch HTML content from URL with error handling and rate limiting."""
        try:
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                html_content = response.text
                time.sleep(self.delay_seconds)  # Rate limiting
                return html_content
            else:
                print(f"Failed to fetch page. Status code: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error fetching page: {e}")
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

    def clean_extracted_text(self, text: str) -> str:
        """Clean and normalize extracted text content."""
        if not text:
            return ""

        # Decode HTML entities
        text = html.unescape(text)

        # Remove common scraping artifacts and noise
        text = re.sub(r'""">Search.*?""', '', text)
        text = re.sub(r'=hp&amp;.*?Search', '', text)
        text = re.sub(r'&amp;.*?Search', '', text)
        text = re.sub(r'scompany\.com/data/[^"]*\.html[^"]*', '', text)
        text = re.sub(r'""">.*?</.*?>', '', text)
        text = re.sub(r'<[^>]+>', '', text)  # Remove any remaining HTML tags

        # Remove search-related noise
        text = re.sub(r'\bSearch\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\breferences?\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bagents?\b(?!\s+(?:for|of|in))', '', text, flags=re.IGNORECASE)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # Filter out very short or meaningless text
        if len(text) < 3 or text.lower() in ['search', 'references', 'agents', 'ing', 'and', 'the', 'of', 'a', 'an']:
            return ""

        return text

    def extract_text_from_soup(self, soup: BeautifulSoup, patterns: List[str], context_keywords: List[str] = None) -> str:
        """Extract text using BeautifulSoup with contextual awareness."""
        if context_keywords is None:
            context_keywords = []

        # First try to find content by context keywords
        if context_keywords:
            for keyword in context_keywords:
                # Look for text containing the keyword
                elements = soup.find_all(string=re.compile(keyword, re.IGNORECASE))
                for element in elements:
                    if isinstance(element, NavigableString):
                        parent = element.parent
                        if parent:
                            # Get the text content from the parent element
                            text = parent.get_text(strip=True)
                            # Try to extract the relevant part after the keyword
                            for pattern in patterns:
                                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                                if match and match.groups():
                                    content = match.group(1)
                                    cleaned = self.clean_extracted_text(content)
                                    if cleaned and len(cleaned) > 3:
                                        return cleaned

        # Fall back to regex patterns on full text
        full_text = soup.get_text()
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
            if match and match.groups():
                content = match.group(1)
                cleaned = self.clean_extracted_text(content)
                if cleaned and len(cleaned) > 3:
                    return cleaned

        return ""

    def parse_ingredient_data(self, html_content: str, url: str) -> Dict:
        """Parse ingredient page HTML to extract comprehensive data using BeautifulSoup."""
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

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract common name from title
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
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
            # Look for ingredient name in various places
            for tag in soup.find_all(['h1', 'h2', 'h3']):
                name = self.clean_extracted_text(tag.get_text())
                if name and len(name) > 2 and not name.lower().startswith('the good'):
                    # Extract CAS number from name if present
                    cas_in_name = re.search(r'(\d{1,7}-\d{2}-\d)', name)
                    if cas_in_name and not ingredient_data['cas_number']:
                        ingredient_data['cas_number'] = cas_in_name.group(1)

                    # Clean CAS numbers from extracted names
                    name = re.sub(r'\s*\d{1,7}-\d{2}-\d\s*', ' ', name)
                    name = re.sub(r'\s+', ' ', name).strip()
                    if name:
                        ingredient_data['common_name'] = name
                        break

        # Extract CAS Number
        cas_patterns = [
            r'CAS[:\s#-]*(\d{1,7}-\d{2}-\d)',
            r'Registry Number[:\s]*(\d{1,7}-\d{2}-\d)',
            r'Chemical Abstracts[:\s]*(\d{1,7}-\d{2}-\d)',
            r'(\d{1,7}-\d{2}-\d)'  # Standalone CAS number
        ]

        if not ingredient_data['cas_number']:
            cas_text = self.extract_text_from_soup(soup, cas_patterns, ['CAS', 'Registry', 'Chemical'])
            if cas_text:
                cas_match = re.search(r'(\d{1,7}-\d{2}-\d)', cas_text)
                if cas_match:
                    ingredient_data['cas_number'] = cas_match.group(1)

        # Extract EINECS Number
        einecs_patterns = [
            r'EINECS[:\s#-]*(\d{3}-\d{3}-\d)',
            r'EC[:\s#-]*(\d{3}-\d{3}-\d)',
            r'ELINCS[:\s#-]*(\d{3}-\d{3}-\d)',
            r'European Inventory[:\s]*(\d{3}-\d{3}-\d)'
        ]

        einecs_text = self.extract_text_from_soup(soup, einecs_patterns, ['EINECS', 'EC', 'ELINCS', 'European'])
        if einecs_text:
            einecs_match = re.search(r'(\d{3}-\d{3}-\d)', einecs_text)
            if einecs_match:
                ingredient_data['einecs_number'] = einecs_match.group(1)

        # Extract FEMA Number
        fema_patterns = [
            r'FEMA[:\s#-]*(\d+)',
            r'Flavor and Extract[:\s]*(\d+)',
            r'GRAS[:\s]*(\d+)'
        ]

        fema_text = self.extract_text_from_soup(soup, fema_patterns, ['FEMA', 'Flavor', 'GRAS'])
        if fema_text:
            fema_match = re.search(r'(\d+)', fema_text)
            if fema_match:
                ingredient_data['fema_number'] = fema_match.group(1)

        # Extract botanical name - look for italic text first
        italic_elements = soup.find_all('i')
        for italic in italic_elements:
            text = self.clean_extracted_text(italic.get_text())
            # Check if it looks like a botanical name (Genus species format)
            botanical_match = re.match(r'^([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)$', text)
            if botanical_match and len(text.split()) >= 2:
                ingredient_data['botanical_name'] = text
                break

        # If no botanical name from italics, try other patterns
        if not ingredient_data['botanical_name']:
            botanical_patterns = [
                r'botanical[:\s]*([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)',
                r'species[:\s]*([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)',
                r'Scientific name[:\s]*([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)',
                r'Latin name[:\s]*([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)'
            ]

            botanical_text = self.extract_text_from_soup(soup, botanical_patterns, ['botanical', 'species', 'Scientific', 'Latin'])
            if botanical_text:
                botanical_match = re.search(r'([A-Z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)', botanical_text)
                if botanical_match:
                    ingredient_data['botanical_name'] = botanical_match.group(1)

        # Extract molecular information
        formula_patterns = [
            r'molecular formula[:\s]*([A-Z0-9]+)',
            r'formula[:\s]*([A-Z0-9]{3,})',
            r'chemical formula[:\s]*([A-Z0-9]+)'
        ]

        formula_text = self.extract_text_from_soup(soup, formula_patterns, ['molecular', 'formula', 'chemical'])
        if formula_text:
            formula_match = re.search(r'([A-Z0-9]{3,})', formula_text)
            if formula_match:
                ingredient_data['molecular_formula'] = formula_match.group(1)

        weight_patterns = [
            r'molecular weight[:\s]*([0-9.,]+)',
            r'mol(?:ecular)?\s*wt[:\s]*([0-9.,]+)',
            r'MW[:\s]*([0-9.,]+)'
        ]

        weight_text = self.extract_text_from_soup(soup, weight_patterns, ['molecular weight', 'mol wt', 'MW'])
        if weight_text:
            weight_match = re.search(r'([0-9.,]+)', weight_text)
            if weight_match:
                ingredient_data['molecular_weight'] = weight_match.group(1)

        # Extract physical properties
        bp_patterns = [
            r'boiling point[:\s]*([0-9.,°C°F\s-]+)',
            r'b\.?p\.?[:\s]*([0-9.,°C°F\s-]+)',
            r'BP[:\s]*([0-9.,°C°F\s-]+)'
        ]

        bp_text = self.extract_text_from_soup(soup, bp_patterns, ['boiling point', 'b.p.', 'BP'])
        if bp_text:
            bp_match = re.search(r'([0-9.,°C°F\s-]+)', bp_text)
            if bp_match:
                ingredient_data['boiling_point'] = self.clean_extracted_text(bp_match.group(1))

        mp_patterns = [
            r'melting point[:\s]*([0-9.,°C°F\s-]+)',
            r'm\.?p\.?[:\s]*([0-9.,°C°F\s-]+)',
            r'MP[:\s]*([0-9.,°C°F\s-]+)'
        ]

        mp_text = self.extract_text_from_soup(soup, mp_patterns, ['melting point', 'm.p.', 'MP'])
        if mp_text:
            mp_match = re.search(r'([0-9.,°C°F\s-]+)', mp_text)
            if mp_match:
                ingredient_data['melting_point'] = self.clean_extracted_text(mp_match.group(1))

        density_patterns = [
            r'density[:\s]*([0-9.,\s]+)',
            r'specific gravity[:\s]*([0-9.,\s]+)',
            r'd20[:\s]*([0-9.,\s]+)',
            r'ρ[:\s]*([0-9.,\s]+)'
        ]

        density_text = self.extract_text_from_soup(soup, density_patterns, ['density', 'specific gravity', 'd20'])
        if density_text:
            density_match = re.search(r'([0-9.,]+)', density_text)
            if density_match:
                ingredient_data['density'] = density_match.group(1)

        # Extract descriptive information
        solubility_patterns = [
            r'solubility[:\s]*([^.]{10,200}?)(?:\.|$)',
            r'soluble[:\s]*(?:in)?[:\s]*([^.]{10,200}?)(?:\.|$)',
            r'dissolves[:\s]*(?:in)?[:\s]*([^.]{10,200}?)(?:\.|$)'
        ]

        solubility_text = self.extract_text_from_soup(soup, solubility_patterns, ['solubility', 'soluble', 'dissolves'])
        if solubility_text:
            ingredient_data['solubility'] = solubility_text[:200]

        # Extract odor descriptions
        odor_patterns = [
            r'Has (?:an? )?([^.]{5,200}?) type odor',
            r'odor[:\s]*([^.]{5,200}?)(?:\.|$)',
            r'odour[:\s]*([^.]{5,200}?)(?:\.|$)',
            r'scent[:\s]*([^.]{5,200}?)(?:\.|$)',
            r'aroma[:\s]*([^.]{5,200}?)(?:\.|$)'
        ]

        odor_text = self.extract_text_from_soup(soup, odor_patterns, ['odor', 'odour', 'scent', 'aroma'])
        if odor_text:
            ingredient_data['odor_description'] = odor_text[:300]

        # Extract flavor descriptions
        flavor_patterns = [
            r'Has (?:an? )?([^.]{5,200}?) type flavor',
            r'flavor[:\s]*([^.]{5,200}?)(?:\.|$)',
            r'flavour[:\s]*([^.]{5,200}?)(?:\.|$)',
            r'taste[:\s]*([^.]{5,200}?)(?:\.|$)'
        ]

        flavor_text = self.extract_text_from_soup(soup, flavor_patterns, ['flavor', 'flavour', 'taste'])
        if flavor_text:
            ingredient_data['flavor_description'] = flavor_text[:300]

        # Extract uses and applications
        uses_patterns = [
            r'Use\(?s?\)?[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'Application[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'Used\s+(?:in|for|as)[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'Function[:\s]*([^.]{10,300}?)(?:\.|$)'
        ]

        uses_text = self.extract_text_from_soup(soup, uses_patterns, ['Use', 'Application', 'Used', 'Function'])
        if uses_text:
            ingredient_data['description'] = uses_text[:300]
            # Split into individual uses
            uses_list = [use.strip() for use in re.split(r'[,;]', uses_text) if use.strip() and len(use.strip()) > 2]
            ingredient_data['uses'] = uses_list[:5]

        # Extract synonyms
        synonym_patterns = [
            r'synonyms?[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'also known as[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'alternative names?[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'other names?[:\s]*([^.]{10,300}?)(?:\.|$)'
        ]

        synonym_text = self.extract_text_from_soup(soup, synonym_patterns, ['synonym', 'also known', 'alternative', 'other names'])
        if synonym_text:
            synonyms = [s.strip() for s in re.split(r'[,;|]', synonym_text) if s.strip() and len(s.strip()) > 2]
            ingredient_data['synonyms'] = synonyms[:10]

        # Extract natural occurrence
        occurrence_patterns = [
            r'(?:found in|occurs in|natural occurrence)[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'(?:natural|naturally)\s+(?:found|occurs?)[:\s]*(?:in)?[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'source[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'derived from[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'obtained from[:\s]*([^.]{10,300}?)(?:\.|$)'
        ]

        occurrence_text = self.extract_text_from_soup(soup, occurrence_patterns, ['found in', 'occurs', 'natural', 'source', 'derived', 'obtained'])
        if occurrence_text:
            occurrences = [o.strip() for o in re.split(r'[,;|]', occurrence_text) if o.strip() and len(o.strip()) > 2]
            ingredient_data['natural_occurrence'] = occurrences[:10]

        # Extract safety notes
        safety_patterns = [
            r'safety[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'hazard[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'warning[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'caution[:\s]*([^.]{10,300}?)(?:\.|$)',
            r'toxicity[:\s]*([^.]{10,300}?)(?:\.|$)'
        ]

        safety_text = self.extract_text_from_soup(soup, safety_patterns, ['safety', 'hazard', 'warning', 'caution', 'toxicity'])
        if safety_text:
            ingredient_data['safety_notes'] = safety_text[:300]

        return ingredient_data

    def scrape_category(self, category_name: str, category_url: str, max_ingredients: int = 50, resume_from_url: Optional[str] = None) -> Tuple[List[Dict], Dict]:
        """Scrape all ingredients from a specific category, with resume capability."""
        # Fetch category page
        category_html = self.fetch_html(category_url)
        if not category_html:
            print(f"❌ Failed to fetch category page: {category_name}")
            return [], {}

        # Extract ingredient links
        all_ingredient_links = self.extract_ingredient_links(category_html)

        if not all_ingredient_links:
            print(f"⚠️  No ingredient links found for {category_name}")
            return [], {}

        # Determine start index for resuming
        start_index = 0
        if resume_from_url:
            try:
                start_index = all_ingredient_links.index(resume_from_url) + 1
            except ValueError:
                start_index = 0

        # Limit ingredients per category
        ingredient_links_to_process = all_ingredient_links[start_index : start_index + max_ingredients]

        if not ingredient_links_to_process:
            return [], {}

        ingredients_data = []

        # Data quality tracking
        quality_stats = {
            'cas_count': 0,
            'einecs_count': 0,
            'description_count': 0,
            'botanical_count': 0,
            'odor_count': 0
        }

        # Category name normalization mapping
        category_mapping = {
            'resins_gums': 'resins_natural'
        }

        # Scrape each ingredient
        for i, link in enumerate(ingredient_links_to_process, start=start_index + 1):
            html_content = self.fetch_html(link, save_filename=None)
            if html_content:
                ingredient_data = self.parse_ingredient_data(html_content, link)
                if ingredient_data['common_name']:  # Only save if we got a name
                    # Add category info with mapping
                    mapped_category = category_mapping.get(category_name, category_name)
                    ingredient_data['category'] = mapped_category
                    ingredients_data.append(ingredient_data)

                    # Track data quality
                    if ingredient_data.get('cas_number'):
                        quality_stats['cas_count'] += 1
                    if ingredient_data.get('einecs_number'):
                        quality_stats['einecs_count'] += 1
                    if ingredient_data.get('description'):
                        quality_stats['description_count'] += 1
                    if ingredient_data.get('botanical_name'):
                        quality_stats['botanical_count'] += 1
                    if ingredient_data.get('odor_description'):
                        quality_stats['odor_count'] += 1

                    # Simple progress checkmark
                    print(f"✅ {i}/{len(ingredient_links_to_process) + start_index}: {ingredient_data['common_name']} [{category_name}]", flush=True)
            else:
                print(f"❌ [{category_name}] {i}/{len(ingredient_links_to_process) + start_index}: Failed to fetch HTML", flush=True)

        return ingredients_data, quality_stats

    def get_last_scraped_url(self, category_name: str, csv_filepath: str) -> Optional[str]:
        """Reads the CSV and returns the URL of the last scraped item for a given category."""
        if not Path(csv_filepath).exists():
            return None

        try:
            category_entries = []
            with open(csv_filepath, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                # Collect all entries for this specific category
                for row in reader:
                    if row.get('category') == category_name and row.get('url'):
                        category_entries.append(row)

            if category_entries:
                last_url = category_entries[-1].get('url')
                return last_url
            else:
                return None

        except Exception as e:
            print(f"⚠️ Error reading {csv_filepath} for resume: {e}")
        return None

    def save_ingredients_csv(self, ingredients: List[Dict], filename: str):
        """Save ingredients data to CSV file additively (no duplicate checking - handled by caller)."""
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

        # Check if file exists to determine if we need to write header
        file_exists = Path(filename).exists()

        try:
            # Open in append mode, or write mode if file doesn't exist
            mode = 'a' if file_exists else 'w'
            with open(filename, mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # Only write header if file is new
                if not file_exists:
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

        except Exception as e:
            print(f"❌ Error saving CSV: {e}")

def scrape_category_with_resume(scraper, category_name, category_url, max_ingredients, target_file):
    """Scrape a single category with resume capability."""
    # Check for existing progress - get the last scraped URL for this specific category
    last_scraped_url = scraper.get_last_scraped_url(category_name, str(target_file))

    try:
        ingredients, quality_stats = scraper.scrape_category(
            category_name,
            category_url,
            max_ingredients=max_ingredients,
            resume_from_url=last_scraped_url
        )

        if ingredients:
            # Add category info to all scraped ingredients
            for ingredient in ingredients:
                ingredient['category'] = category_name

        return category_name, ingredients, quality_stats

    except Exception as e:
        print(f"❌ Error scraping category {category_name}: {e}")
        return category_name, [], {}

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
    try:  # pragma: no cover
        from data_builder import paths as builder_paths  # type: ignore
        builder_paths.ensure_layout()
        target_dir = builder_paths.DATA_SOURCES_DIR
    except Exception:  # pragma: no cover - direct script execution fallback
        target_dir = Path(__file__).resolve().parents[2] / "data_sources"
        target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "tgsc_ingredients.csv"

    print("🚀 TGSC Ingredient Database Scraper (Enhanced)")
    print("=" * 60)
    print(f"📊 Max ingredients per category: {args.max_ingredients}")
    print(f"⚡ Max parallel workers: {args.max_workers}")
    print(f"🔄 Resume mode: {'Enabled' if args.resume else 'Disabled'}")

    # Track category results for final summary
    category_results = {}
    quality_summary = {}
    total_new_ingredients = 0

    # Get initial counts for each category if file exists
    initial_counts = {}
    if target_file.exists():
        try:
            with open(target_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                existing_ingredients = list(reader)

                # Count existing ingredients per category
                for ingredient in existing_ingredients:
                    category = ingredient.get('category', 'unknown')
                    initial_counts[category] = initial_counts.get(category, 0) + 1

        except Exception as e:
            print(f"⚠️  Error loading existing data: {e}")

    # Process categories in parallel
    all_new_ingredients = []

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

        # Process completed tasks and collect all ingredients
        for future in as_completed(futures):
            category_name = futures[future]
            try:
                category_name_result, ingredients, quality_stats = future.result()
                new_count = len(ingredients) if ingredients else 0
                initial_count = initial_counts.get(category_name, 0)
                current_total = initial_count + new_count

                category_results[category_name] = {
                    'new': new_count,
                    'total': current_total
                }
                quality_summary[category_name] = quality_stats
                total_new_ingredients += new_count

                if ingredients:
                    all_new_ingredients.extend(ingredients)
                    print(f"📋 Collected {new_count} ingredients from {category_name}")

            except Exception as e:
                print(f"❌ {category_name}: Failed with error: {e}")
                category_results[category_name] = {'new': 0, 'total': initial_counts.get(category_name, 0)}
                quality_summary[category_name] = {}

    # After the loop — write ONCE to prevent race conditions
    if all_new_ingredients:
        print(f"💾 Final save: Writing {len(all_new_ingredients)} new ingredients across all categories")

        # Re-load existing data one last time before final write to catch any recent writes
        existing_urls = set()
        existing_combinations = set()
        if target_file.exists():
            try:
                with open(target_file, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        if row.get('url'):
                            existing_urls.add(row['url'])
                        name_category_key = f"{row.get('common_name', '').lower().strip()}_{row.get('category', '').lower().strip()}"
                        existing_combinations.add(name_category_key)
            except Exception as e:
                print(f"⚠️  Error reading existing data: {e}")

        # Filter final ingredients with fresh duplicate check
        final_ingredients = []
        for ingredient in all_new_ingredients:
            ingredient_url = ingredient.get('url', '')
            ingredient_name = ingredient.get('common_name', '').lower().strip()
            ingredient_category = ingredient.get('category', '').lower().strip()
            name_category_key = f"{ingredient_name}_{ingredient_category}"

            if (ingredient_url not in existing_urls and
                name_category_key not in existing_combinations and
                ingredient_name):
                final_ingredients.append(ingredient)
                existing_combinations.add(name_category_key)  # Track within this final batch
            else:
                if name_category_key in existing_combinations:
                    print(f"⏭️  Skipping duplicate name+category: {ingredient.get('common_name', 'Unknown')}")

        if final_ingredients:
            scraper.save_ingredients_csv(final_ingredients, str(target_file))
            print(f"✅ Successfully saved {len(final_ingredients)} unique ingredients")
        else:
            print("No new unique ingredients to save")
    else:
        print("No new ingredients to save")

    # Enhanced final summary
    print(f"\n🎊 SCRAPING COMPLETE!")
    print(f"📁 File: {target_file}")
    print(f"\n📊 Total ingredients added: {total_new_ingredients}")

    if category_results:
        print("\nCategory breakdown:")
        for category_name in TGSC_INGREDIENT_CATEGORIES.keys():
            if category_name in category_results:
                result = category_results[category_name]
                print(f"   {category_name}: {result['new']}, {result['total']}")

        # Aggregate data quality summary
        total_cas = sum(stats.get('cas_count', 0) for stats in quality_summary.values())
        total_einecs = sum(stats.get('einecs_count', 0) for stats in quality_summary.values())
        total_descriptions = sum(stats.get('description_count', 0) for stats in quality_summary.values())
        total_botanical = sum(stats.get('botanical_count', 0) for stats in quality_summary.values())
        total_odor = sum(stats.get('odor_count', 0) for stats in quality_summary.values())

        if total_new_ingredients > 0:
            print(f"\n📊 Data Quality Summary:")
            print(f"   CAS numbers: {total_cas} ({total_cas/total_new_ingredients*100:.1f}%)")
            print(f"   EINECS numbers: {total_einecs} ({total_einecs/total_new_ingredients*100:.1f}%)")
            print(f"   Descriptions: {total_descriptions} ({total_descriptions/total_new_ingredients*100:.1f}%)")
            print(f"   Botanical names: {total_botanical} ({total_botanical/total_new_ingredients*100:.1f}%)")
            print(f"   Odor descriptions: {total_odor} ({total_odor/total_new_ingredients*100:.1f}%)")

        print(f"\nTotal new ingredients added: {total_new_ingredients}")


if __name__ == "__main__":
    main()
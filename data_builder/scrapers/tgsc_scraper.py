
"""TGSC (The Good Scents Company) scraper for fragrance demo formulas."""
import csv
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class TGSCScraper:
    """Scraper for The Good Scents Company fragrance demo formulas."""
    
    def __init__(self, url: str, user_agent: str, title: str):
        self.url = url
        self.user_agent = user_agent
        self.title = title
        self.headers = {"User-Agent": user_agent}

    def searchsingle(self, start: str, end: str, content: str) -> str:
        """Extract single match between start and end markers."""
        if end != "" and start != "":
            pattern = re.compile(f'{re.escape(start)}(.*?){re.escape(end)}', re.DOTALL)
        elif end == "":
            pattern = re.compile(f'{re.escape(start) + r"\s*(.*)"}')
        elif start == "":
            pattern = re.compile(f'{r"^(.*?)" + re.escape(end)}')
        
        match = re.search(pattern, content)
        return match.group(1) if match else ""

    def searchmultiple(self, start: str, end: str, content: str) -> List[str]:
        """Extract multiple matches between start and end markers."""
        if end != "" and start != "":
            pattern = re.compile(f'{re.escape(start)}(.*?){re.escape(end)}', re.DOTALL)
        elif end == "":
            pattern = re.compile(f'{re.escape(start) + r"\s*(.*)"}')
        elif start == "":
            pattern = re.compile(f'{r"^(.*?)" + re.escape(end)}')
        
        matches = pattern.findall(content)
        return matches

    def fetch_html(self, url: str, title: str) -> Optional[str]:
        """Fetch HTML content from URL and save to file."""
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                html = response.text
                # Write HTML content to file
                with open(f"{title}.txt", "w", errors="ignore", encoding="utf-8") as fp:
                    fp.write(html)
                print(f"HTML content from {url} written to {title}.txt")
                return html
            else:
                print(f"Failed to fetch HTML from {url}. Status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"An error occurred while fetching HTML from {url}: {e}")
            return None

    def read_html(self, filename: str) -> str:
        """Read and return the content of an HTML file."""
        try:
            with open(filename, "r", encoding="utf-8") as fp:
                content = fp.read()
            return content
        except Exception as e:
            print(f"Error reading file {filename}: {e}")
            return ""

    def write_csv(self, filename: str, data: List[Dict], fieldnames: List[str]):
        """Write data to CSV file."""
        try:
            with open(filename, "w", encoding="utf-8", newline="") as fp:
                writer = csv.DictWriter(fp, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
        except Exception as e:
            print(f"Error writing CSV file {filename}: {e}")

    def parse_formulas(self, html: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse HTML content to extract formula information and ingredients."""
        all_information = []
        all_ingredients = []
        
        # Extract formula blocks
        formula_blocks = self.searchmultiple("<tr><td", "Total</td></tr>", html)

        for i, block in enumerate(formula_blocks):
            # Parse formula information
            formula_info = {}
            name = self.searchsingle('class="dmow1" colspan="3">', '</td></tr>', block)
            
            try:
                application = self.searchsingle(
                    '<tr><td class="dmow3" colspan="3">Application: ', '</td></tr>', block
                )
            except:
                application = ""
            
            try:
                description = self.searchsingle('<tr><td class="dmow2" colspan="3">', '</td></tr>', block)
                if "href" in description:
                    description = self.searchsingle('">', "</a>", description)
            except:
                description = ""
            
            # Extract total percentage
            lines = self.searchmultiple("<tr>", "", block)
            total = ""
            for line in lines:
                if "</tr>" not in line:
                    total = self.searchsingle('<td class="dmow5">', '</td>', line)
            
            formula_info.update({
                "id": i,
                "name": name,
                "application": application,
                "description": description,
                "total": total
            })
            all_information.append(formula_info)

            # Parse ingredients for this formula
            ingredient_rows = self.searchmultiple('<tr><td class="dmow5">', '</td></tr>', block)
            
            for ingredient_row in ingredient_rows:
                ingredient_info = {}
                
                try:
                    website = self.searchsingle('<a href="', '">', ingredient_row)
                except:
                    website = ""
                
                percentage = self.searchsingle('', '</td>', ingredient_row)
                content = self.searchsingle('colspan="2">', '', ingredient_row)
                
                # Clean up ingredient name
                if "<sup>" in content:
                    content = content.replace("<sup>&reg;</sup>", "")
                if "href" in content:
                    content = self.searchsingle('.html">', "</a>", content)
                if "dmow9" in content:
                    content = self.searchsingle('"dmow9">', '</span>', content)
                
                ingredient_info.update({
                    "id": i,
                    "ingredients": content,
                    "percentage": percentage,
                    "website": website,
                    "total": total
                })
                
                # Calculate normalized percentage
                try:
                    ingredient_info["100 pct"] = round(
                        float(percentage) / float(total) * 100, 2
                    )
                except:
                    ingredient_info["100 pct"] = ""
                
                all_ingredients.append(ingredient_info)

        return all_information, all_ingredients

    def scrape(self) -> bool:
        """Main scraping method."""
        print(f"Starting TGSC scrape for: {self.title}")
        
        # Fetch HTML
        html = self.fetch_html(self.url, "sourcecode")
        if not html:
            print("Failed to fetch HTML content")
            return False
        
        # Parse the data
        formulas, ingredients = self.parse_formulas(html)
        
        if not formulas:
            print("No formula data found")
            return False
        
        # Define CSV headers
        formula_headers = ["id", "name", "application", "description", "total"]
        ingredient_headers = ["id", "ingredients", "percentage", "100 pct", "website", "total"]
        
        # Write CSV files
        formula_file = f"{self.title}Information.csv"
        ingredient_file = f"{self.title}Ingredients.csv"
        
        self.write_csv(formula_file, formulas, formula_headers)
        self.write_csv(ingredient_file, ingredients, ingredient_headers)
        
        print(f"Scraping completed:")
        print(f"  - {len(formulas)} formulas saved to {formula_file}")
        print(f"  - {len(ingredients)} ingredients saved to {ingredient_file}")
        
        return True

    @classmethod
    def scrape_formula_url(cls, url: str, user_agent: str, title: str) -> bool:
        """Convenience method to scrape a single formula URL."""
        scraper = cls(url, user_agent, title)
        return scraper.scrape()

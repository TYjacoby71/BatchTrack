
#!/usr/bin/env python3
"""
Example script to run the TGSC scraper and copy results to data sources.

Usage:
1. Run this script with a TGSC formula URL
2. The script will generate CSV files
3. Copy the *Ingredients.csv to data_builder/ingredients/data_sources/tgsc_ingredients.csv
"""

from data_builder.scrapers import TGSCScraper

def main():
    # Example URLs to scrape
    urls = [
        "https://www.thegoodscentscompany.com/search2.php?str=lavender&submit.x=0&submit.y=0",
        "https://www.thegoodscentscompany.com/search2.php?str=rose&submit.x=0&submit.y=0"
    ]
    
    # Your browser's User-Agent string (get from browser dev tools > Network tab)
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    for i, url in enumerate(urls):
        title = f"tgsc_batch_{i+1}"
        
        print(f"\n{'='*50}")
        print(f"Scraping batch {i+1}: {url}")
        print(f"{'='*50}")
        
        scraper = TGSCScraper(url, user_agent, title)
        success = scraper.scrape()
        
        if success:
            print(f"\n✅ Batch {i+1} completed successfully!")
            print(f"Generated files:")
            print(f"  - {title}Information.csv")
            print(f"  - {title}Ingredients.csv")
            print(f"\nNext step: Copy {title}Ingredients.csv to data_builder/ingredients/data_sources/tgsc_ingredients.csv")
        else:
            print(f"❌ Batch {i+1} failed")

if __name__ == "__main__":
    main()

"""
Compatibility shim.

The TGSC scraper implementation lives at:
  data_builder/scrapers/tgsc_scraper/scraper.py

This module preserves the historical CLI/import path:
  python3 data_builder/scrapers/tgsc_scraper.py ...
  from data_builder.scrapers.tgsc_scraper import TGSCIngredientScraper
"""

from data_builder.scrapers.tgsc_scraper.scraper import TGSCIngredientScraper, main

__all__ = ["TGSCIngredientScraper", "main"]


if __name__ == "__main__":
    main()


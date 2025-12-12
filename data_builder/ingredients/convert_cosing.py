
#!/usr/bin/env python3
"""Convert CosIng Excel file to CSV format for the ingredient compiler."""

import pandas as pd
from pathlib import Path

def convert_cosing_to_csv():
    """Convert the CosIng Excel file to CSV format."""
    
    # File paths
    base_dir = Path(__file__).parent / "data_sources"
    excel_file = base_dir / "COSING_Annex_III_v2.xls"
    csv_file = base_dir / "cosing.csv"
    
    if not excel_file.exists():
        print(f"Excel file not found: {excel_file}")
        return False
    
    try:
        # Read the Excel file
        print(f"Reading Excel file: {excel_file}")
        df = pd.read_excel(excel_file)
        
        # Display basic info about the data
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print("\nFirst few rows:")
        print(df.head())
        
        # Save as CSV
        df.to_csv(csv_file, index=False, encoding='utf-8')
        print(f"\nCSV file saved: {csv_file}")
        print(f"Total records: {len(df)}")
        
        return True
        
    except Exception as e:
        print(f"Error converting file: {e}")
        return False

if __name__ == "__main__":
    convert_cosing_to_csv()

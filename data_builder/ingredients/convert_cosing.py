
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
        # Try different engines to handle the Excel file
        engines = ['xlrd', 'openpyxl']
        df = None
        
        for engine in engines:
            try:
                print(f"Trying to read Excel file with {engine} engine...")
                df = pd.read_excel(excel_file, engine=engine)
                print(f"Successfully read with {engine} engine")
                break
            except Exception as engine_error:
                print(f"Failed with {engine}: {engine_error}")
                continue
        
        if df is None:
            print("All engines failed. Trying to read as CSV in case it's misnamed...")
            try:
                df = pd.read_csv(excel_file, encoding='utf-8', on_bad_lines='skip')
                print("Successfully read as CSV")
            except Exception as csv_error:
                print(f"CSV read also failed: {csv_error}")
                return False
        
        # Display basic info about the data
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print("\nFirst few rows:")
        print(df.head())
        
        # Check if we have the expected columns for CosIng
        expected_cols = ['INCI Name', 'Synonyms']
        missing_cols = [col for col in expected_cols if col not in df.columns]
        if missing_cols:
            print(f"Warning: Missing expected columns: {missing_cols}")
            print("Available columns:")
            for i, col in enumerate(df.columns):
                print(f"  {i}: {col}")
        
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

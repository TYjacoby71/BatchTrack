
import pandas as pd
import os
import sys
import re
import csv
import zipfile
from typing import List, Dict, Any

def convert_cosing_to_csv():
    """Convert CosIng data from ZIP file to clean CSV format."""
    
    # Define file paths
    zip_file = "data_builder/ingredients/data_sources/COSING_Ingredients-Fragrance Inventory_v2.csv.zip"
    csv_file = "data_builder/ingredients/data_sources/cosing.csv"
    
    if not os.path.exists(zip_file):
        print(f"❌ ZIP file not found: {zip_file}")
        return False
    
    try:
        print(f"📦 Found ZIP file: {zip_file}")
        
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            # List contents
            file_list = zip_ref.namelist()
            print(f"ZIP contents: {file_list}")
            
            # Look for CSV files in the ZIP
            csv_files = [f for f in file_list if f.endswith('.csv')]
            
            if not csv_files:
                print("❌ No CSV files found in ZIP")
                return False
            
            # Extract the first CSV file
            csv_name = csv_files[0]
            print(f"📄 Extracting {csv_name} from ZIP")
            
            with zip_ref.open(csv_name) as csv_in_zip:
                # Read the CSV content
                content = csv_in_zip.read().decode('utf-8', errors='ignore')
                
                # Write to our target CSV file
                with open(csv_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"✅ Successfully extracted CSV to {csv_file}")
        
        # Now clean and process the CSV
        return clean_and_validate_csv(csv_file)
        
    except Exception as e:
        print(f"❌ Error extracting ZIP file: {e}")
        return False

def clean_and_validate_csv(csv_file: str) -> bool:
    """Clean and validate the CosIng CSV file."""
    
    try:
        print(f"🧹 Cleaning CSV file: {csv_file}")
        
        # Read the file and detect encoding
        with open(csv_file, 'rb') as f:
            raw_content = f.read()
        
        # Try different encodings
        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        content = None
        used_encoding = None
        
        for encoding in encodings_to_try:
            try:
                content = raw_content.decode(encoding)
                used_encoding = encoding
                print(f"✅ Successfully decoded with {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            print("❌ Could not decode file with any encoding")
            return False
        
        # Split into lines and find the header
        lines = content.split('\n')
        header_line_idx = None
        header_line = None
        
        # Look for the header line containing expected CosIng columns
        for i, line in enumerate(lines):
            if any(col in line for col in ['COSING Ref No', 'INCI name', 'CAS No', 'Function']):
                header_line_idx = i
                header_line = line
                print(f"📍 Found header at line {i}: {line[:100]}...")
                break
        
        if header_line_idx is None:
            print("❌ Could not find header line with expected CosIng columns")
            return False
        
        # Extract data lines (skip metadata)
        clean_lines = []
        clean_lines.append(header_line)  # Add header
        
        # Add data rows (skip empty lines and metadata)
        for line in lines[header_line_idx + 1:]:
            line = line.strip()
            if line and not line.startswith('File creation') and not line.startswith('Ingredients/Fragrance'):
                # Basic validation - line should have multiple fields separated by commas
                if line.count(',') > 3:
                    clean_lines.append(line)
        
        print(f"📊 Found {len(clean_lines)} data lines (including header)")
        
        if len(clean_lines) < 2:
            print("❌ Not enough data lines found")
            return False
        
        # Write cleaned CSV
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(clean_lines))
        
        # Validate with pandas
        try:
            df = pd.read_csv(csv_file, encoding='utf-8', on_bad_lines='skip')
            
            # Clean up column names
            df.columns = df.columns.str.strip()
            
            print(f"📈 CSV Shape: {df.shape}")
            print(f"📋 Columns: {list(df.columns[:5])}...")  # Show first 5 columns
            
            # Check for expected columns
            expected_cols = ['INCI name', 'CAS No', 'Function']
            found_cols = []
            
            for col in df.columns:
                col_lower = col.lower()
                if 'inci' in col_lower and 'name' in col_lower:
                    found_cols.append('INCI name')
                elif 'cas' in col_lower:
                    found_cols.append('CAS No')
                elif 'function' in col_lower:
                    found_cols.append('Function')
            
            print(f"✅ Found expected columns: {found_cols}")
            
            # Save the final cleaned version
            df.to_csv(csv_file, index=False, encoding='utf-8')
            print(f"🎉 Successfully processed CosIng data: {len(df)} ingredients")
            
            return True
            
        except Exception as e:
            print(f"❌ Error validating CSV with pandas: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Error cleaning CSV file: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting CosIng conversion...")
    success = convert_cosing_to_csv()
    if success:
        print("✅ CosIng conversion completed successfully!")
        sys.exit(0)
    else:
        print("❌ CosIng conversion failed!")
        sys.exit(1)

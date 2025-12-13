import pandas as pd
import os
import sys
import re
import csv
import zipfile
from typing import List, Dict, Any

def convert_cosing_to_csv():
    """Convert CosIng data from the uploaded CSV file to clean CSV format."""

    # Use the uploaded CSV file directly - path relative to current working directory (data_builder/ingredients)
    input_file = "../../attached_assets/COSING_Ingredients-Fragrance_Inventory_v2_1765584408467.csv"
    output_file = "data_sources/cosing.csv"

    # Check if file exists and print debug info
    print(f"🔍 Looking for file: {input_file}")
    print(f"🔍 Current working directory: {os.getcwd()}")
    print(f"🔍 File exists check: {os.path.exists(input_file)}")

    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return False

    try:
        print(f"📄 Processing COSING file: {input_file}")

        # Read the file and find the actual header line
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        print(f"📊 Total lines in file: {len(lines)}")

        # Find the header line (contains COSING Ref No, INCI name, etc.)
        header_line_idx = None
        for i, line in enumerate(lines):
            line = line.strip()
            if 'COSING Ref No' in line and 'INCI name' in line:
                header_line_idx = i
                print(f"📍 Found header at line {i + 1}: {line[:100]}...")
                break

        if header_line_idx is None:
            print("❌ Could not find header line with 'COSING Ref No' and 'INCI name'")
            return False

        # Extract clean data starting from header line
        clean_lines = []
        data_line_count = 0

        for i in range(header_line_idx, len(lines)):
            line = lines[i].strip()
            if not line:
                continue

            # Count commas to validate it's a proper data line
            comma_count = line.count(',')
            if comma_count >= 8:  # Should have at least 9 fields (8+ commas)
                clean_lines.append(line)
                if i > header_line_idx:  # Don't count header as data
                    data_line_count += 1

        print(f"📈 Extracted {len(clean_lines)} lines ({data_line_count} data rows + header)")

        if len(clean_lines) < 2:
            print("❌ Not enough data lines found")
            return False

        # Write cleaned CSV
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(clean_lines))

        # Validate with pandas
        try:
            df = pd.read_csv(output_file, encoding='utf-8')
            print(f"✅ Successfully created CSV with {len(df)} rows and {len(df.columns)} columns")
            print(f"📋 Columns: {list(df.columns)}")

            # Show a sample of the data
            if len(df) > 0:
                print(f"📝 Sample INCI names: {df['INCI name'].head(3).tolist()}")

            return True

        except Exception as e:
            print(f"❌ Error validating CSV with pandas: {e}")
            return False

    except Exception as e:
        print(f"❌ Error processing COSING file: {e}")
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
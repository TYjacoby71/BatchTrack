
import pandas as pd
import os
import sys
import re
import csv
import zipfile
from typing import List, Dict, Any

def convert_cosing_to_csv():
    """Convert CosIng data from the uploaded CSV file to clean CSV format."""

    # Use the uploaded CSV file directly - path relative to workspace root
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
        
        # Read the file with multiple encoding attempts and better error handling
        encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        raw_lines = None
        
        for encoding in encodings_to_try:
            try:
                with open(input_file, 'r', encoding=encoding, errors='replace') as f:
                    raw_lines = f.readlines()
                print(f"✅ Successfully read file with encoding: {encoding}")
                break
            except UnicodeDecodeError:
                print(f"⚠️ Failed to read with encoding: {encoding}")
                continue
        
        if raw_lines is None:
            print("❌ Could not read file with any encoding")
            return False

        print(f"📊 Total lines in file: {len(raw_lines)}")
        
        # Find the actual header line - look for "COSING Ref No"
        header_line_idx = None
        for i, line in enumerate(raw_lines):
            line_clean = line.strip()
            if 'COSING Ref No' in line_clean and 'INCI name' in line_clean:
                header_line_idx = i
                print(f"📍 Found header at line {i + 1}: {line_clean[:100]}...")
                break

        if header_line_idx is None:
            print("❌ Could not find header line with 'COSING Ref No' and 'INCI name'")
            return False

        # Extract and clean the data
        clean_lines = []
        header_processed = False
        expected_field_count = None
        
        for i in range(header_line_idx, len(raw_lines)):
            line = raw_lines[i].strip()
            if not line:
                continue
            
            # Clean up problematic characters that might break CSV parsing
            line = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', line)  # Remove control characters
            line = line.replace('""', '"').replace(',"","', ',"",')  # Fix double quote issues
            
            # Skip lines that don't look like data (too few commas)
            comma_count = line.count(',')
            if comma_count < 5:  # Minimum expected fields
                continue
                
            if not header_processed:
                # This is our header line
                expected_field_count = comma_count
                clean_lines.append(line)
                header_processed = True
                print(f"📋 Header has {expected_field_count + 1} fields")
            else:
                # For data lines, try to normalize field count
                if comma_count != expected_field_count:
                    # If line has too many fields, it might have embedded commas in descriptions
                    # Try to fix by ensuring we have the right number of fields
                    fields = line.split(',')
                    if len(fields) > expected_field_count + 1:
                        # Merge excess fields into the description field (usually field 6)
                        if len(fields) > 7:  # If we have more than expected fields
                            # Merge fields 6 and beyond into field 6 (description field)
                            merged_description = ','.join(fields[6:expected_field_count + 1])
                            new_fields = fields[:6] + [merged_description] + fields[expected_field_count + 1:expected_field_count + 1]
                            line = ','.join(new_fields[:expected_field_count + 1])
                
                clean_lines.append(line)

        print(f"📈 Extracted {len(clean_lines)} lines")
        
        if len(clean_lines) < 2:
            print("❌ Not enough data lines found")
            return False

        # Create output directory if needed
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Write the cleaned data to a temporary file first
        temp_file = output_file + ".tmp"
        with open(temp_file, 'w', encoding='utf-8', newline='') as f:
            for line in clean_lines:
                f.write(line + '\n')

        # Try to read it back with pandas to validate
        try:
            df = pd.read_csv(temp_file, encoding='utf-8', on_bad_lines='skip')
            print(f"✅ Successfully created and validated CSV with {len(df)} rows and {len(df.columns)} columns")
            print(f"📋 Columns: {list(df.columns)}")
            
            # Show a sample of the data
            if len(df) > 0 and 'INCI name' in df.columns:
                sample_names = df['INCI name'].dropna().head(3).tolist()
                print(f"📝 Sample INCI names: {sample_names}")
            
            # Move temp file to final location
            os.rename(temp_file, output_file)
            return True
            
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            # Remove temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
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

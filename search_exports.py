
import json
import glob
from pathlib import Path

def search_exports(search_term):
    # Search through all json files in legacy_exports
    export_dir = Path('legacy_exports')
    
    for file_path in export_dir.glob('*.json'):
        print(f"\nSearching in {file_path.name}:")
        with open(file_path, 'r') as f:
            data = json.load(f)
            
            # Handle both list and dict formats
            if isinstance(data, list):
                matches = [item for item in data if any(str(search_term).lower() in str(v).lower() for v in item.values())]
            else:
                matches = []
                for key, value in data.items():
                    if str(search_term).lower() in str(value).lower():
                        matches.append({key: value})
            
            if matches:
                print(f"Found {len(matches)} matches:")
                for match in matches:
                    print(json.dumps(match, indent=2))
            else:
                print("No matches found")

if __name__ == '__main__':
    term = input("Enter search term: ")
    search_exports(term)

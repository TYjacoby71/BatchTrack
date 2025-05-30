
from .inventory_startup import load_startup_inventory
from .recipe_startup import load_startup_recipes
from .unit_startup import load_startup_units

def run_all_startup_services():
    """Run all startup data services in correct order"""
    print("🚀 Running startup data services...")
    
    # Order matters: units first, then inventory, then recipes
    print("\n1. Loading startup units...")
    load_startup_units()
    
    print("\n2. Loading startup inventory...")
    load_startup_inventory()
    
    print("\n3. Loading startup recipes...")
    load_startup_recipes()
    
    print("\n✅ All startup data services complete!")

if __name__ == '__main__':
    run_all_startup_services()
from .unit_startup import load_startup_units
from .inventory_startup import load_startup_inventory
from .recipe_startup import load_startup_recipes

def run_all_startup_services():
    """Run all startup data services in correct order"""
    print("🚀 Running startup data services...")
    
    # Order matters: units first, then inventory, then recipes
    print("\n1. Loading startup units...")
    load_startup_units()
    
    print("\n2. Loading startup inventory...")
    load_startup_inventory()
    
    print("\n3. Loading startup recipes...")
    load_startup_recipes()
    
    print("\n✅ All startup data services complete!")

if __name__ == '__main__':
    run_all_startup_services()

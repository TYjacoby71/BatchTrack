
#!/usr/bin/env python3
"""
BatchTrack Startup Service
Run this script to import legacy data using proper adjustment workflows
"""

from services.startup.main_startup import run_full_startup

if __name__ == '__main__':
    print("Starting BatchTrack Legacy Import Service...")
    success = run_full_startup()
    
    if success:
        print("\n✅ All systems ready! You can now:")
        print("   • View inventory at /inventory")
        print("   • View recipes at /recipes") 
        print("   • Start production batches")
        exit(0)
    else:
        print("\n❌ Startup failed. Check the output above for errors.")
        exit(1)

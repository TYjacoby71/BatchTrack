#!/usr/bin/env python3
"""
Load test runner that temporarily adjusts rate limiting
"""
import os
import sys
import subprocess
import time

def run_load_test():
    """Run load test with optimized settings"""

    # Set environment variables for load testing
    env = os.environ.copy()
    env['FLASK_ENV'] = 'development'
    env['RATELIMIT_STORAGE_URI'] = 'memory://'  # Use memory storage for faster rate limiting

    print("🚀 Starting optimized load test...")

    # Create test users first
    print("📝 Creating test users...")
    create_users_cmd = [
        'python', '-c', '''
import requests
import time

# Wait a moment for the server to be ready
time.sleep(2)

try:
    # Hit the dev-login endpoint to ensure dev user exists
    response = requests.get("http://0.0.0.0:5000/auth/dev-login", timeout=5)
    if response.status_code in [200, 302]:
        print("✅ Dev user ready for load testing")
    else:
        print(f"⚠️  Dev user creation returned status {response.status_code}")
except Exception as e:
    print(f"⚠️  Could not verify dev user setup: {e}")
    print("Load test will still proceed - users will attempt to create dev user during test")

print("Load test users ready!")
'''
    ]

    result = subprocess.run(create_users_cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ User creation failed: {result.stderr}")
        # In a real scenario, you might want to return False here if user creation is critical
        # but for load testing, we might proceed and let Locust handle failures.
        # return False
    
    print(result.stdout)

    # Run the load test
    print("🔥 Starting load test web interface...")
    print("💡 Access the dashboard at: http://0.0.0.0:8091")
    print("   In the webview, switch to port 3002 to see the dashboard")
    load_test_cmd = [
        'locust', 
        '-f', 'loadtests/locustfile.py',
        '--host=http://0.0.0.0:5000',
        '--web-host=0.0.0.0',
        '--web-port=8091'
    ]

    result = subprocess.run(load_test_cmd, env=env)
    return result.returncode == 0

if __name__ == '__main__':
    success = run_load_test()
    sys.exit(0 if success else 1)
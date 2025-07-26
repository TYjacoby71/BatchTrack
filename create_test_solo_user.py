
#!/usr/bin/env python3
"""
Script to create a test user for solo tier testing
Uses the proper signup service and session handling
"""

import requests
import random
import string
from datetime import datetime
import sys
import os
import json

# Configuration - Use Replit URL or discover local IP
REPL_URL = os.environ.get('REPL_URL', '')
BASE_URL = REPL_URL if REPL_URL else "http://127.0.0.1:5000"

def generate_random_string(length=8):
    """Generate random string for usernames/passwords"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_test_user_data(tier='solo'):
    """Generate realistic test user data"""
    timestamp = datetime.now().strftime("%m%d%H%M")

    return {
        'org_name': f'Test {tier.title()} Org {timestamp}',
        'username': f'{tier}{timestamp}',
        'email': f'{tier}{timestamp}@test.com',
        'first_name': 'Test',
        'last_name': f'{tier.title()}User',
        'password': 'test123',
        'confirm_password': 'test123',
        'phone': f'555-{random.randint(1000, 9999)}',
        'subscription_tier': tier
    }

def extract_csrf_token(html_content):
    """Extract CSRF token from HTML content"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for CSRF token in hidden input
        csrf_input = soup.find('input', {'name': 'csrf_token'})
        if csrf_input:
            return csrf_input.get('value')
        
        # Try meta tag
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        if csrf_meta:
            return csrf_meta.get('content')
            
        return None
    except ImportError:
        print("❌ BeautifulSoup not available. Installing...")
        import subprocess
        subprocess.run(['pip', 'install', 'beautifulsoup4'], check=True)
        print("✅ BeautifulSoup installed. Please run the script again.")
        return None

def submit_signup(base_url=BASE_URL, tier='solo'):
    """Submit signup form using the proper signup flow"""

    # Generate test data
    user_data = generate_test_user_data(tier)

    print(f"=== Creating Test {tier.title()} User ===")
    print(f"Organization: {user_data['org_name']}")
    print(f"Username: {user_data['username']}")
    print(f"Email: {user_data['email']}")
    print(f"Password: {user_data['password']}")
    print(f"Tier: {user_data['subscription_tier']}")
    print("=" * 35)

    # Create session to handle cookies/CSRF
    session = requests.Session()

    try:
        # Step 1: Get the signup page to extract CSRF token
        print("📄 Getting signup page...")
        signup_page = session.get(f'{base_url}/auth/signup', verify=False)

        if signup_page.status_code != 200:
            print(f"❌ Failed to load signup page. Status: {signup_page.status_code}")
            return False

        # Extract CSRF token
        csrf_token = extract_csrf_token(signup_page.content)
        if csrf_token:
            user_data['csrf_token'] = csrf_token
            print("✅ CSRF token extracted")
        else:
            print("⚠️  No CSRF token found, proceeding without it")

        # Step 2: Submit the signup form
        print("📤 Submitting signup form...")
        response = session.post(
            f'{base_url}/auth/signup',
            data=user_data,
            allow_redirects=False,
            verify=False
        )

        print(f"📊 Response Status: {response.status_code}")

        if response.status_code == 302:
            # Check redirect location
            redirect_url = response.headers.get('Location', '')
            print(f"🔄 Redirecting to: {redirect_url}")

            if 'billing/checkout' in redirect_url:
                print("💳 Redirected to billing checkout")
                
                # For non-Stripe ready tiers, this should complete the signup
                # Follow the redirect to see what happens
                checkout_response = session.get(base_url + redirect_url, verify=False)
                
                if checkout_response.status_code == 302:
                    final_redirect = checkout_response.headers.get('Location', '')
                    print(f"🔄 Final redirect to: {final_redirect}")
                    
                    if 'dashboard' in final_redirect:
                        print(f"\n🎉 SUCCESS: Test user created and logged in!")
                        print(f"\n📋 Login credentials:")
                        print(f"   Username: {user_data['username']}")
                        print(f"   Password: {user_data['password']}")
                        print(f"   Organization: {user_data['org_name']}")
                        return True
                
                # If we reach here, the signup is pending payment
                print(f"💳 Account created but payment required for {tier} tier")
                print(f"\n📋 Login credentials (for manual testing):")
                print(f"   Username: {user_data['username']}")
                print(f"   Password: {user_data['password']}")
                return True

            elif 'dashboard' in redirect_url:
                print("🎉 Redirected directly to dashboard - signup complete!")
                print(f"\n📋 Login credentials:")
                print(f"   Username: {user_data['username']}")
                print(f"   Password: {user_data['password']}")
                return True

            else:
                print(f"⚠️  Unexpected redirect: {redirect_url}")
                return False

        elif response.status_code == 200:
            # Form returned with errors
            print("❌ Signup form returned with errors")
            
            # Try to extract error message
            if 'already exists' in response.text.lower():
                print("   Error: Username or email already exists")
            elif 'error' in response.text.lower():
                print("   Check form validation errors")
            
            return False

        else:
            print(f"❌ Unexpected response status: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the application.")
        print(f"   Make sure the Flask app is running on {base_url}")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_app_running():
    """Check if the Flask app is running"""
    global BASE_URL

    # Get current Replit environment URLs
    replit_urls = []
    
    # Try REPL_URL from environment first
    if REPL_URL:
        replit_urls.append(REPL_URL)
    
    # Try discovering local IP from console output or common patterns
    import subprocess
    import socket
    try:
        # Get the hostname and try to resolve internal IP
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if local_ip and local_ip != '127.0.0.1':
            replit_urls.append(f"http://{local_ip}:5000")
    except:
        pass

    # Standard fallback URLs
    urls_to_try = replit_urls + [
        BASE_URL,
        "http://127.0.0.1:5000",
        "http://localhost:5000",
        "http://172.31.72.98:5000",  # From console output
        "http://0.0.0.0:5000"
    ]

    # Remove duplicates while preserving order
    seen = set()
    urls_to_try = [x for x in urls_to_try if not (x in seen or seen.add(x))]

    for url in urls_to_try:
        try:
            print(f"   Trying {url}...")
            # Try the root route
            response = requests.get(f"{url}/", timeout=3, verify=False, allow_redirects=True)
            if response.status_code in [200, 302]:
                BASE_URL = url
                print(f"   ✅ Connected to {url}")
                return True

            # Try specific routes that should always work
            for route in ['/homepage', '/auth/signup']:
                try:
                    response = requests.get(f"{url}{route}", timeout=3, verify=False)
                    if response.status_code == 200:
                        BASE_URL = url
                        print(f"   ✅ Connected to {url}{route}")
                        return True
                except:
                    continue

        except requests.exceptions.RequestException as e:
            print(f"   ❌ {url} failed: {str(e)[:100]}...")
            continue

    return False

def main():
    """Main function"""
    # Available tiers
    available_tiers = ['free', 'solo', 'team', 'enterprise']

    # Check command line arguments
    tier = 'solo'  # default
    if len(sys.argv) > 1:
        requested_tier = sys.argv[1].lower()
        if requested_tier in available_tiers:
            tier = requested_tier
        else:
            print(f"❌ Invalid tier '{requested_tier}'")
            print(f"Available tiers: {', '.join(available_tiers)}")
            return

    print(f"🚀 {tier.title()} Tier Test User Generator")
    print("=" * 40)

    # Check if app is running
    print("🔍 Checking if application is running...")
    if not check_app_running():
        print("❌ Application is not running.")
        print("   Please start your Flask app first with: python run.py")
        return

    print(f"✅ Application found at {BASE_URL}")

    # Create test user
    success = submit_signup(tier=tier)

    if success:
        print("\n🎯 Next steps:")
        print("1. The user account has been created")
        if tier in ['solo', 'team', 'enterprise']:
            print("2. If Stripe is not configured, the account should be activated in development mode")
            print("3. If Stripe is configured, you may need to complete payment")
        print("4. You can now test the application with this user account!")
        print(f"5. Login at: {BASE_URL}/auth/login")
    else:
        print("\n❌ Failed to create test user. Check the errors above.")
        print("💡 Try using a different tier or check if the username already exists")

if __name__ == "__main__":
    main()

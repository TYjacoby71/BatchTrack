
#!/usr/bin/env python3
"""
Script to create a test user for solo tier testing
Generates random user data and submits signup programmatically
"""

import requests
import random
import string
from datetime import datetime

def generate_random_string(length=8):
    """Generate random string for usernames/passwords"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_test_user_data():
    """Generate realistic test user data"""
    timestamp = datetime.now().strftime("%m%d%H%M")
    
    return {
        'org_name': f'Test Solo Org {timestamp}',
        'username': f'solo{timestamp}',
        'email': f'solo{timestamp}@test.com',
        'first_name': 'Solo',
        'last_name': f'Tester{timestamp}',
        'password': 'test123',
        'confirm_password': 'test123',
        'phone': f'555-{random.randint(1000, 9999)}',
        'subscription_tier': 'solo'
    }

def submit_signup(base_url='http://127.0.0.1:5000'):
    """Submit signup form programmatically"""
    
    # Generate test data
    user_data = generate_test_user_data()
    
    print("=== Creating Test Solo User ===")
    print(f"Organization: {user_data['org_name']}")
    print(f"Username: {user_data['username']}")
    print(f"Email: {user_data['email']}")
    print(f"Password: {user_data['password']}")
    print(f"Tier: {user_data['subscription_tier']}")
    print("=" * 35)
    
    # Create session to handle cookies/CSRF
    session = requests.Session()
    
    try:
        # First, get the signup page to extract CSRF token
        print("📄 Getting signup page...")
        signup_page = session.get(f'{base_url}/auth/signup')
        
        if signup_page.status_code != 200:
            print(f"❌ Failed to load signup page. Status: {signup_page.status_code}")
            return False
        
        # Extract CSRF token from the page
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(signup_page.content, 'html.parser')
        csrf_token = None
        
        # Look for CSRF token in hidden input or meta tag
        csrf_input = soup.find('input', {'name': 'csrf_token'})
        if csrf_input:
            csrf_token = csrf_input.get('value')
        else:
            # Try meta tag
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            if csrf_meta:
                csrf_token = csrf_meta.get('content')
        
        if csrf_token:
            user_data['csrf_token'] = csrf_token
            print("✅ CSRF token extracted")
        else:
            print("⚠️  No CSRF token found, proceeding without it")
        
        # Submit the signup form
        print("📤 Submitting signup form...")
        response = session.post(
            f'{base_url}/auth/signup',
            data=user_data,
            allow_redirects=False  # Don't follow redirects automatically
        )
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 302:
            # Redirect typically means success (going to billing)
            redirect_url = response.headers.get('Location', '')
            print(f"✅ Signup submitted successfully!")
            print(f"🔄 Redirecting to: {redirect_url}")
            
            if 'billing/checkout' in redirect_url:
                print("💳 Redirected to billing checkout (expected for solo tier)")
                print("\n🎉 SUCCESS: Test user created and ready for solo tier testing!")
                print(f"\n📋 Login credentials:")
                print(f"   Username: {user_data['username']}")
                print(f"   Password: {user_data['password']}")
                return True
            else:
                print(f"⚠️  Unexpected redirect: {redirect_url}")
                
        elif response.status_code == 200:
            # Form returned with errors
            print("❌ Signup form returned with errors")
            if 'error' in response.text.lower() or 'already exists' in response.text.lower():
                print("   Possible duplicate username/email")
            return False
            
        else:
            print(f"❌ Unexpected response status: {response.status_code}")
            return False
            
    except ImportError:
        print("❌ BeautifulSoup not available. Installing...")
        import subprocess
        subprocess.run(['pip', 'install', 'beautifulsoup4'], check=True)
        print("✅ BeautifulSoup installed. Please run the script again.")
        return False
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the application.")
        print("   Make sure the Flask app is running on http://127.0.0.1:5000")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main function"""
    print("🚀 Solo Tier Test User Generator")
    print("================================")
    
    # Check if app is running
    try:
        response = requests.get('http://127.0.0.1:5000', timeout=5)
        print("✅ Application is running")
    except:
        print("❌ Application is not running on http://127.0.0.1:5000")
        print("   Please start your Flask app first with: python run.py")
        return
    
    # Create test user
    success = submit_signup()
    
    if success:
        print("\n🎯 Next steps:")
        print("1. The user is now in the signup flow")
        print("2. Since no Stripe is configured, they should be able to bypass payment")
        print("3. The account should be created in dev mode")
        print("4. You can now test solo tier functionality!")
    else:
        print("\n❌ Failed to create test user. Check the errors above.")

if __name__ == "__main__":
    main()

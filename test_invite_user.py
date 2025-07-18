
#!/usr/bin/env python3
"""
Test script for invite user functionality in organization dashboard
"""

import requests
import json
import sys

def test_invite_user():
    """Test the invite user endpoint with sample data"""
    
    # Base URL for your Flask app
    base_url = "http://127.0.0.1:5000"
    
    # Test data for inviting a user
    test_data = {
        "email": "test.user@example.com",
        "first_name": "Test",
        "last_name": "User",
        "phone": "555-123-4567",
        "role_id": 2  # Assuming role ID 2 exists (manager or similar)
    }
    
    print("Testing invite user functionality...")
    print(f"Test data: {json.dumps(test_data, indent=2)}")
    print("-" * 50)
    
    try:
        # First, let's check if we can access the organization dashboard
        dashboard_response = requests.get(f"{base_url}/organization/dashboard")
        
        if dashboard_response.status_code == 302:
            print("❌ Not logged in - redirected to login page")
            print("You need to be logged in as an organization owner to test this")
            return False
        elif dashboard_response.status_code == 403:
            print("❌ Access forbidden - current user doesn't have organization owner permissions")
            return False
        elif dashboard_response.status_code != 200:
            print(f"❌ Dashboard access failed with status: {dashboard_response.status_code}")
            return False
        
        print("✅ Dashboard accessible")
        
        # Now test the invite user endpoint
        invite_response = requests.post(
            f"{base_url}/organization/invite-user",
            json=test_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Invite response status: {invite_response.status_code}")
        
        try:
            response_data = invite_response.json()
            print(f"Response data: {json.dumps(response_data, indent=2)}")
            
            if response_data.get('success'):
                print("✅ User invite would be successful!")
                if 'user_data' in response_data:
                    user_data = response_data['user_data']
                    print(f"Generated username: {user_data.get('username')}")
                    print(f"Temporary password: {user_data.get('temp_password')}")
            else:
                print(f"❌ User invite would fail: {response_data.get('error')}")
                
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON response: {invite_response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - make sure your Flask app is running on port 5000")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def test_different_scenarios():
    """Test various scenarios for invite user"""
    
    base_url = "http://127.0.0.1:5000"
    
    test_scenarios = [
        {
            "name": "Valid user with manager role",
            "data": {
                "email": "manager@test.com",
                "first_name": "Test",
                "last_name": "Manager",
                "role_id": 2
            }
        },
        {
            "name": "Valid user with operator role",
            "data": {
                "email": "operator@test.com",
                "first_name": "Test",
                "last_name": "Operator", 
                "role_id": 3
            }
        },
        {
            "name": "Invalid email format",
            "data": {
                "email": "invalid-email",
                "first_name": "Test",
                "last_name": "User",
                "role_id": 2
            }
        },
        {
            "name": "Missing required fields",
            "data": {
                "first_name": "Test",
                "last_name": "User"
                # Missing email and role_id
            }
        },
        {
            "name": "Try to assign developer role (should fail)",
            "data": {
                "email": "dev@test.com",
                "first_name": "Test",
                "last_name": "Dev",
                "role_id": 1  # Assuming role ID 1 is developer
            }
        }
    ]
    
    print("\n" + "="*60)
    print("TESTING DIFFERENT SCENARIOS")
    print("="*60)
    
    for scenario in test_scenarios:
        print(f"\nTesting: {scenario['name']}")
        print(f"Data: {json.dumps(scenario['data'], indent=2)}")
        
        try:
            response = requests.post(
                f"{base_url}/organization/invite-user",
                json=scenario['data'],
                headers={'Content-Type': 'application/json'}
            )
            
            result = response.json()
            status = "✅ SUCCESS" if result.get('success') else "❌ FAILED"
            print(f"Result: {status}")
            print(f"Message: {result.get('message') or result.get('error')}")
            
        except Exception as e:
            print(f"❌ Request failed: {str(e)}")
        
        print("-" * 40)

if __name__ == "__main__":
    print("🧪 Organization User Invite Tester")
    print("="*60)
    
    # Test basic functionality
    test_invite_user()
    
    # Test different scenarios
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        test_different_scenarios()
    else:
        print("\nRun with --full flag to test additional scenarios:")
        print("python test_invite_user.py --full")

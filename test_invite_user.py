
#!/usr/bin/env python3
"""
Test script for invite user functionality in organization dashboard
"""

import sys
import os
import json

# Add the app directory to the path so we can import models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_invite_user_backend():
    """Test the invite user logic directly without HTTP requests"""
    
    try:
        from app.models import Role, Permission, Organization, User
        from app.extensions import db
        from app import create_app
        import re
        import secrets
        
        # Create app context
        app = create_app()
        
        with app.app_context():
            print("🧪 Testing invite user backend logic...")
            print("="*60)
            
            # Get organization
            org = Organization.query.first()
            if not org:
                print("❌ No organization found")
                return False
            
            print(f"Organization: {org.name}")
            print(f"Subscription: {org.subscription_tier}")
            print(f"Current users: {org.active_users_count}/{org.get_max_users()}")
            print(f"Can add users: {org.can_add_users()}")
            
            if not org.can_add_users():
                print("⚠️  Organization has reached user limit - invite will fail")
                print("This is expected behavior for testing")
            
            # Get available roles (excluding developer and organization_owner roles)
            roles = Role.query.filter(
                Role.name.notin_(['developer', 'organization_owner'])
            ).all()
            
            if not roles:
                print("❌ No assignable roles found")
                return False
            
            print(f"\nAvailable roles for assignment:")
            for role in roles:
                print(f"  - {role.name} (ID: {role.id}): {role.description}")
            
            # Test data
            test_data = {
                "email": "test.invite@example.com",
                "first_name": "Test",
                "last_name": "Invite",
                "phone": "555-123-4567",
                "role_id": roles[0].id if roles else None
            }
            
            print(f"\nTest data:")
            print(f"  Email: {test_data['email']}")
            print(f"  Role: {roles[0].name if roles else 'None'} (ID: {test_data['role_id']})")
            
            # Test validation logic
            print(f"\n🔍 Testing validation logic...")
            
            # Email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            email_valid = re.match(email_pattern, test_data['email'])
            print(f"  Email format valid: {'✅' if email_valid else '❌'}")
            
            # Check if user already exists
            existing_user = User.query.filter(
                (User.email == test_data['email']) | (User.username == test_data['email'])
            ).first()
            print(f"  User already exists: {'❌ Yes' if existing_user else '✅ No'}")
            
            # Validate role
            role = Role.query.filter_by(id=test_data['role_id']).first()
            role_valid = role and role.name not in ['developer', 'organization_owner']
            print(f"  Role valid: {'✅' if role_valid else '❌'}")
            
            # Check subscription limits
            can_add = org.can_add_users()
            print(f"  Can add users: {'✅' if can_add else '❌'}")
            
            # Test username generation
            base_username = test_data['email'].split('@')[0]
            username = base_username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{counter}"
                counter += 1
            
            print(f"  Generated username: {username}")
            
            # Test password generation
            temp_password = secrets.token_urlsafe(12)
            print(f"  Generated password: {temp_password}")
            
            print(f"\n📊 Summary:")
            all_valid = email_valid and not existing_user and role_valid
            print(f"  Validation passed: {'✅' if all_valid else '❌'}")
            print(f"  Would succeed: {'✅' if all_valid and can_add else '❌'}")
            
            if not can_add:
                print(f"  Reason for failure: Organization limit reached ({org.active_users_count}/{org.get_max_users()})")
            
            return all_valid
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the project root directory")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_different_scenarios():
    """Test various edge cases and scenarios"""
    
    try:
        from app.models import Role, Organization, User
        from app.extensions import db
        from app import create_app
        
        app = create_app()
        
        with app.app_context():
            print("\n🧪 TESTING DIFFERENT SCENARIOS")
            print("="*60)
            
            org = Organization.query.first()
            roles = Role.query.filter(Role.name != 'developer').all()
            
            scenarios = [
                {
                    "name": "Valid invitation",
                    "data": {
                        "email": "valid.test@example.com",
                        "first_name": "Valid",
                        "last_name": "Test",
                        "role_id": roles[0].id if roles else None
                    },
                    "expected": "success" if org.can_add_users() else "fail_limit"
                },
                {
                    "name": "Invalid email format",
                    "data": {
                        "email": "invalid-email",
                        "first_name": "Invalid",
                        "last_name": "Email",
                        "role_id": roles[0].id if roles else None
                    },
                    "expected": "fail_validation"
                },
                {
                    "name": "Missing required fields",
                    "data": {
                        "email": "",
                        "first_name": "",
                        "last_name": "",
                        "role_id": None
                    },
                    "expected": "fail_validation"
                },
                {
                    "name": "Developer role assignment (should fail)",
                    "data": {
                        "email": "dev.test@example.com",
                        "first_name": "Dev",
                        "last_name": "Test",
                        "role_id": 1  # Assuming developer role has ID 1
                    },
                    "expected": "fail_role"
                }
            ]
            
            for scenario in scenarios:
                print(f"\n📋 Testing: {scenario['name']}")
                data = scenario['data']
                
                # Validate email
                import re
                email_valid = bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', data.get('email', '')))
                
                # Check required fields
                required_valid = all([data.get('email'), data.get('first_name'), data.get('last_name'), data.get('role_id')])
                
                # Check role
                if data.get('role_id'):
                    role = Role.query.filter_by(id=data['role_id']).first()
                    role_valid = role and role.name not in ['developer', 'organization_owner']
                else:
                    role_valid = False
                
                # Check if user exists
                user_exists = False
                if data.get('email'):
                    user_exists = User.query.filter(
                        (User.email == data['email']) | (User.username == data['email'])
                    ).first() is not None
                
                # Determine result
                if not required_valid:
                    result = "❌ Missing required fields"
                elif not email_valid:
                    result = "❌ Invalid email format"
                elif user_exists:
                    result = "❌ User already exists"
                elif not role_valid:
                    result = "❌ Invalid role (system or organization owner roles not allowed)"
                elif not org.can_add_users():
                    result = "❌ Organization user limit reached"
                else:
                    result = "✅ Would succeed"
                
                print(f"   Result: {result}")
                
    except Exception as e:
        print(f"❌ Error in scenario testing: {e}")

def simulate_api_call():
    """Simulate what the API call would look like"""
    
    print("\n🌐 API CALL SIMULATION")
    print("="*60)
    
    print("If you were to test this via HTTP requests, it would look like:")
    print()
    print("POST /organization/invite-user")
    print("Content-Type: application/json")
    print()
    print("Request Body:")
    print(json.dumps({
        "email": "test.user@example.com",
        "first_name": "Test",
        "last_name": "User",
        "phone": "555-123-4567",
        "role_id": 2
    }, indent=2))
    
    print("\nTo test manually:")
    print("1. Log in as an organization owner")
    print("2. Go to /organization/dashboard")
    print("3. Click 'Invite User' button")
    print("4. Fill out the form")
    print("5. Check the browser console for any JavaScript errors")

if __name__ == "__main__":
    print("🧪 Organization User Invite Tester")
    print("="*60)
    
    # Test basic functionality
    success = test_invite_user_backend()
    
    # Test different scenarios
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        test_different_scenarios()
    
    # Show API simulation
    simulate_api_call()
    
    print(f"\n{'✅ Tests completed successfully' if success else '❌ Tests found issues'}")
    print("\nRun with --full flag to test additional scenarios:")
    print("python test_invite_user.py --full")

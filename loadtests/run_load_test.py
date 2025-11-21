
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
from app import create_app
from app.extensions import db
from app.models import User, Organization
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    # Create test organization
    test_org = Organization.query.filter_by(name='Test Organization').first()
    if not test_org:
        test_org = Organization(name='Test Organization')
        db.session.add(test_org)
        db.session.flush()
    
    # Create test user
    test_user = User.query.filter_by(username='test@example.com').first()
    if not test_user:
        test_user = User(
            username='test@example.com',
            email='test@example.com',
            first_name='Test',
            last_name='User',
            password_hash=generate_password_hash('testpassword123'),
            is_active=True,
            user_type='customer',
            organization_id=test_org.id
        )
        db.session.add(test_user)
    
    db.session.commit()
    print('Test users ready')
'''
    ]
    
    result = subprocess.run(create_users_cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ User creation failed: {result.stderr}")
        return False
    
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

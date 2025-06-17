
from flask import Blueprint, request, jsonify, flash
import json
import os
from datetime import datetime

email_signup_bp = Blueprint('email_signup', __name__)

@email_signup_bp.route('/signup-email', methods=['POST'])
def signup_email():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or not data.get('email'):
            return jsonify({'status': 'error', 'message': 'Email is required'}), 400
        
        # Create signup record
        signup_data = {
            'firstName': data.get('firstName', ''),
            'lastName': data.get('lastName', ''),
            'email': data.get('email'),
            'company': data.get('company', ''),
            'businessType': data.get('businessType', ''),
            'newsletter': data.get('newsletter', False),
            'signupDate': datetime.now().isoformat()
        }
        
        # Save to JSON file (you can replace this with database storage later)
        signup_file = 'email_signups.json'
        signups = []
        
        if os.path.exists(signup_file):
            with open(signup_file, 'r') as f:
                signups = json.load(f)
        
        signups.append(signup_data)
        
        with open(signup_file, 'w') as f:
            json.dump(signups, f, indent=2)
        
        return jsonify({
            'status': 'success', 
            'message': 'Thank you! We\'ll notify you as soon as BatchTrack is ready for launch.'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Something went wrong. Please try again.'}), 500

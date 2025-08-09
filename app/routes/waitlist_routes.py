
from flask import Blueprint, request, jsonify
from flask_wtf.csrf import exempt
import json
import os
from datetime import datetime
from ..services.email_service import EmailService

waitlist_bp = Blueprint('waitlist', __name__)

@waitlist_bp.route('/api/waitlist', methods=['POST'])
@exempt
def join_waitlist():
    """Handle waitlist form submissions"""
    try:
        data = request.get_json()
        
        if not data or not data.get('email'):
            return jsonify({'error': 'Email is required'}), 400
        
        # Create waitlist entry
        waitlist_entry = {
            'email': data.get('email'),
            'name': data.get('name', ''),
            'business_type': data.get('business_type', ''),
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'homepage'
        }
        
        # Save to JSON file (you can later migrate this to database)
        waitlist_file = 'waitlist.json'
        waitlist = []
        
        # Load existing waitlist
        if os.path.exists(waitlist_file):
            try:
                with open(waitlist_file, 'r') as f:
                    waitlist = json.load(f)
            except (json.JSONDecodeError, IOError):
                waitlist = []
        
        # Check if email already exists
        if any(entry.get('email') == waitlist_entry['email'] for entry in waitlist):
            return jsonify({'message': 'Email already on waitlist'}), 200
        
        # Add new entry
        waitlist.append(waitlist_entry)
        
        # Save updated waitlist
        with open(waitlist_file, 'w') as f:
            json.dump(waitlist, f, indent=2)
        
        # Send confirmation email
        EmailService.send_waitlist_confirmation(
            email=waitlist_entry['email'],
            name=waitlist_entry['name']
        )
        
        return jsonify({'message': 'Successfully joined waitlist'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

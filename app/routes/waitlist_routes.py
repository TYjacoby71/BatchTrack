from flask import Blueprint, request, jsonify
import json
import os
from datetime import datetime
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

waitlist_bp = Blueprint('waitlist', __name__)

@waitlist_bp.route('/api/waitlist', methods=['POST'])
def join_waitlist():
    """Handle waitlist form submissions - save to JSON only"""
    try:
        # Get JSON data from request
        data = request.get_json()

        if not data or not data.get('email'):
            logger.warning("Waitlist join attempt with missing email.")
            return jsonify({'error': 'Email is required'}), 400

        # Create waitlist entry
        waitlist_entry = {
            'email': data.get('email'),
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
            'business_type': data.get('business_type', ''),
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'homepage'
        }

        # Save to JSON file (persistent storage)
        waitlist_file = 'data/waitlist.json'

        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)

        waitlist = []

        # Load existing waitlist
        if os.path.exists(waitlist_file):
            try:
                with open(waitlist_file, 'r') as f:
                    # Handle empty file case
                    content = f.read()
                    if not content:
                        waitlist = []
                    else:
                        waitlist = json.loads(content)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error reading waitlist file {waitlist_file}: {e}")
                waitlist = []

        # Check if email already exists
        if any(entry.get('email') == waitlist_entry['email'] for entry in waitlist):
            logger.info(f"Email {waitlist_entry['email']} already on waitlist.")
            return jsonify({'message': 'Email already on waitlist'}), 200

        # Add new entry
        waitlist.append(waitlist_entry)

        # Save updated waitlist
        try:
            with open(waitlist_file, 'w') as f:
                json.dump(waitlist, f, indent=2)
            logger.info(f"Successfully added {waitlist_entry['email']} to waitlist.")
            return jsonify({'message': 'Successfully joined waitlist'}), 200
        except IOError as e:
            logger.error(f"Error writing to waitlist file {waitlist_file}: {e}")
            return jsonify({'error': 'Internal server error: could not save to waitlist'}), 500

    except Exception as e:
        logger.error(f"Waitlist join error: {e}")
        return jsonify({'error': 'Error joining waitlist'}), 500
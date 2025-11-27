
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from app.utils.json_store import read_json_file, write_json_file

waitlist_bp = Blueprint('waitlist', __name__)

# Define valid waitlist sources and their corresponding files
WAITLIST_SOURCES = {
    'homepage': 'data/waitlist.json',
    'tools_soap': 'data/waitlist_soap.json',
    'tools_candles': 'data/waitlist_candles.json', 
    'tools_lotions': 'data/waitlist_lotions.json',
    'tools_herbal': 'data/waitlist_herbal.json',
    'tools_baker': 'data/waitlist_baker.json',
    'tools_general': 'data/waitlist_tools.json'
}

@waitlist_bp.route('/api/waitlist', methods=['POST'])
def join_waitlist():
    """Handle waitlist form submissions - save to JSON based on source"""
    print("=== WAITLIST ROUTE ACCESSED ===")
    print(f"Request method: {request.method}")
    print(f"Request content type: {request.content_type}")
    print(f"Request data: {request.get_data()}")
    try:
        # Get JSON data from request
        data = request.get_json()

        if not data or not data.get('email'):
            return jsonify({'error': 'Email is required'}), 400

        # Determine source and corresponding file
        source = data.get('source', 'homepage')
        if source not in WAITLIST_SOURCES:
            source = 'homepage'  # Default fallback
        
        waitlist_file = WAITLIST_SOURCES[source]

        # Create waitlist entry
        waitlist_entry = {
            'email': data.get('email'),
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
            'business_type': data.get('business_type', ''),
            'tool_interest': data.get('tool_interest', ''),  # New field for tool-specific interests
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': source
        }

        # Load existing waitlist for this source
        waitlist = read_json_file(waitlist_file, default=[]) or []

        # Check if email already exists in this specific waitlist
        if any(entry.get('email') == waitlist_entry['email'] for entry in waitlist):
            return jsonify({'message': f'Email already on {source} waitlist'}), 200

        # Add new entry
        waitlist.append(waitlist_entry)

        # Save updated waitlist
        write_json_file(waitlist_file, waitlist)

        return jsonify({'message': 'Successfully joined waitlist'}), 200

    except Exception as e:
        import traceback
        print(f"Waitlist error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e) if hasattr(e, '__str__') else 'Unknown error'
        }), 500

@waitlist_bp.route('/api/waitlist/sources', methods=['GET'])
def get_waitlist_sources():
    """Return available waitlist sources for analytics"""
    return jsonify({
        'sources': list(WAITLIST_SOURCES.keys()),
        'files': WAITLIST_SOURCES
    })

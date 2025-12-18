from flask import Blueprint, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import login_required, current_user

from .system_roles import system_roles_bp
from .subscription_tiers import subscription_tiers_bp
from .addons import addons_bp
from app.utils.permissions import permission_required
from app.utils.json_store import read_json_file, write_json_file
import os
import datetime

# Initialize Limiter
limiter = Limiter(key_func=get_remote_address, default_limits="200 per day, 50 per hour")

developer_bp = Blueprint("developer", __name__, url_prefix="/developer")

developer_bp.register_blueprint(system_roles_bp)
developer_bp.register_blueprint(subscription_tiers_bp)

developer_bp.register_blueprint(addons_bp)

# Import view modules for their side effects so routes register with the blueprint.
from . import views  # noqa: F401,E402


@developer_bp.route('/vendor-signups')
@limiter.limit("100 per minute")
@permission_required('developer.access')
def vendor_signups():
    """View vendor signups"""
    from app.utils.json_store import read_json_file
    import os

    vendor_file = os.path.join('data', 'vendor_signups.json')
    signups = read_json_file(vendor_file, default=[])

    # Sort by timestamp, most recent first
    signups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    return render_template('developer/vendor_signups.html', signups=signups)


@developer_bp.route('/waitlist-statistics')
@limiter.limit("100 per minute")
@permission_required('developer.access')
def waitlist_statistics():
    """
    This is a placeholder for the waitlist statistics view.
    This route should be implemented to display waitlist statistics.
    """
    # In a real application, you would read from a database or JSON file
    # and render a template.
    return "Waitlist Statistics - Not Implemented Yet"


# --- Vendor Signup Functionality ---

@developer_bp.route('/api/vendor/signup', methods=['POST'])
@limiter.limit("10 per minute")
def api_vendor_signup():
    """API endpoint to handle vendor signup submissions."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    required_fields = ['vendor_name', 'vendor_url', 'contact_email']
    if not all(field in data and data[field] for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    vendor_signup_data = {
        'vendor_name': data.get('vendor_name'),
        'vendor_url': data.get('vendor_url'),
        'contact_email': data.get('contact_email'),
        'message': data.get('message', ''),
        'timestamp': datetime.datetime.utcnow().isoformat()
    }

    vendor_file = os.path.join('data', 'vendor_signups.json')
    try:
        write_json_file(vendor_file, vendor_signup_data, append=True)
    except Exception as e:
        return jsonify({"error": f"Failed to save signup: {str(e)}"}), 500

    return jsonify({"message": "Vendor signup received successfully!"}), 201


# --- Item View Page Integration (Conceptual) ---
# The following code snippets are conceptual and would need to be integrated
# into your item detail templates and routes.

# Example of how you might add a button to an item detail template (e.g., item_detail.html):
#
# <div class="vendor-signup-section">
#   <h3>Interested in becoming a featured vendor?</h3>
#   <button class="btn btn-primary" data-toggle="modal" data-target="#vendorSignupModal">
#     Vendor Name URL Stub
#   </button>
# </div>
#
# Example of how you might add a modal to the same template:
#
# <div class="modal fade" id="vendorSignupModal" tabindex="-1" role="dialog" aria-labelledby="vendorSignupModalLabel" aria-hidden="true">
#   <div class="modal-dialog" role="document">
#     <div class="modal-content">
#       <div class="modal-header">
#         <h5 class="modal-title" id="vendorSignupModalLabel">Vendor Signup</h5>
#         <button type="button" class="close" data-dismiss="modal" aria-label="Close">
#           <span aria-hidden="true">&times;</span>
#         </button>
#       </div>
#       <div class="modal-body">
#         <form id="vendorSignupForm">
#           <div class="form-group">
#             <label for="vendorName">Vendor Name</label>
#             <input type="text" class="form-control" id="vendorName" name="vendor_name" required>
#           </div>
#           <div class="form-group">
#             <label for="vendorUrl">Vendor URL</label>
#             <input type="url" class="form-control" id="vendorUrl" name="vendor_url" required>
#           </div>
#           <div class="form-group">
#             <label for="contactEmail">Contact Email</label>
#             <input type="email" class="form-control" id="contactEmail" name="contact_email" required>
#           </div>
#           <div class="form-group">
#             <label for="message">Message (Optional)</label>
#             <textarea class="form-control" id="message" name="message" rows="3"></textarea>
#           </div>
#           <button type="submit" class="btn btn-primary">Submit Signup</button>
#         </form>
#         <div id="signupMessage" class="mt-3"></div>
#       </div>
#     </div>
#   </div>
# </div>
#
# Example of JavaScript to handle the form submission (add this to your template's JS section or a separate JS file):
#
# <script>
# $(document).ready(function() {
#   $('#vendorSignupForm').on('submit', function(event) {
#     event.preventDefault();
#     const formData = {
#       vendor_name: $('#vendorName').val(),
#       vendor_url: $('#vendorUrl').val(),
#       contact_email: $('#contactEmail').val(),
#       message: $('#message').val()
#     };
#
#     $.ajax({
#       url: '{{ url_for("developer.api_vendor_signup") }}',
#       method: 'POST',
#       contentType: 'application/json',
#       data: JSON.stringify(formData),
#       success: function(response) {
#         $('#signupMessage').html('<div class="alert alert-success">' + response.message + '</div>');
#         $('#vendorSignupForm')[0].reset();
#       },
#       error: function(xhr) {
#         const errorMsg = xhr.responseJSON && xhr.responseJSON.error ? xhr.responseJSON.error : 'An unexpected error occurred.';
#         $('#signupMessage').html('<div class="alert alert-danger">' + errorMsg + '</div>');
#       }
#     });
#   });
# });
# </script>
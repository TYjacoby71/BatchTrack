from flask import request

def wants_json():
    """Check if the request wants JSON response"""
    accept = request.headers.get('Accept', '')
    # Parse the Accept header properly
    from werkzeug.datastructures import MIMEAccept
    if hasattr(request, 'accept_mimetypes'):
        return ('application/json' in request.accept_mimetypes and 
                not request.accept_mimetypes.accept_html)
    else:
        # Fallback to simple string check
        return ("application/json" in accept) and ("text/html" not in accept)
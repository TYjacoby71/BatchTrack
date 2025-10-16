
from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # Only enable debug mode in development
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true' and os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)

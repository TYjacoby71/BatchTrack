from flask import Flask, render_template, request, jsonify
import logging

# Assuming create_app function is defined elsewhere and returns a Flask app instance.
def create_app():
    app = Flask(__name__)
    # Add any necessary configurations here. For example:
    app.config['SECRET_KEY'] = 'your_secret_key' # Replace with a strong secret key
    return app

app = create_app()
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.errorhandler(404)
def not_found_error(error):
    logger.error('Page not found: %s', request.url)
    return render_template('errors/404.html', error=error), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error('Server Error: %s', error, exc_info=True) # Include traceback for debugging
    return render_template('errors/500.html', error=error), 500

@app.route('/')
def index():
    return 'Hello, world!'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
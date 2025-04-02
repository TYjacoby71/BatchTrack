
from app import create_app
from werkzeug.serving import run_simple

app = create_app()
app.config['TEMPLATES_AUTO_RELOAD'] = True

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

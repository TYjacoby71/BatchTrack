from app import create_app
from app.routes.stock import stock_bp

app = create_app()
app.register_blueprint(stock_bp, url_prefix='/stock')
app.config['TEMPLATES_AUTO_RELOAD'] = True

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
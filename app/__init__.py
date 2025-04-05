from flask import Flask, render_template
from app.routes.ingredients import ingredients_bp
from app.routes.recipes import recipes_bp
from app.routes.batches import batches_bp
import os
from app.routes.utils import load_data

def create_app():
    app = Flask(__name__, template_folder='../templates')
    app.secret_key = 'supersecretkey'  # Replace with a secure key in production

    app.register_blueprint(batches_bp)
    app.register_blueprint(ingredients_bp)
    from app.routes.start_flow import start_flow_bp
    app.register_blueprint(recipes_bp)
    app.register_blueprint(start_flow_bp)
    from app.routes.auth import auth_bp
    from app.routes.export_missings import export_bp
    from app.routes.inventory_adjust import adjust_bp
    from app.routes.update_stock import update_stock_bp
    from app.routes.products import products_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(products_bp)
    from app.routes.api import api_bp
    app.register_blueprint(api_bp)
    from app.routes.stock import stock_bp
    app.register_blueprint(stock_bp, url_prefix='/stock')

    from app.routes.units import unit_bp
    app.register_blueprint(unit_bp)

    from app.routes.settings import settings_bp
    app.register_blueprint(settings_bp)

    from app.error_tools import register_error_handlers
    register_error_handlers(app)

    @app.context_processor
    def inject_globals():
        import json
        from app.routes.utils import load_categories
        with open('units.json') as f:
            units = json.load(f)
        return dict(units=units, category_options=load_categories())

    @app.route('/')
    def dashboard():
        from datetime import datetime
        data = load_data()
        ingredients = data.get('ingredients', [])
        
        low_stock = []
        for ing in ingredients:
            try:
                qty = float(ing.get("quantity", 0))
                if qty < 10:
                    low_stock.append(ing)
            except:
                pass

        recent_batches = sorted(
            data.get("batches", []),
            key=lambda b: b.get("timestamp", ""),
            reverse=True
        )[:5]

        has_unfinished_batches = False
        for batch in data.get("batches", []):
            if not batch.get("completed", False):
                has_unfinished_batches = True
                break

        for batch in recent_batches:
            if batch.get('timestamp'):
                dt = datetime.fromisoformat(batch['timestamp'])
                batch['formatted_time'] = dt.strftime('%B %d, %Y at %I:%M %p')

        return render_template("dashboard.html", 
                            low_stock=low_stock, 
                            recent_batches=recent_batches,
                            has_unfinished_batches=has_unfinished_batches)

    return app
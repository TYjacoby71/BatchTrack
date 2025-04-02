
import traceback
from flask import flash

def safe_route(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print("⚠️ ROUTE ERROR:", str(e))
            print(traceback.format_exc())
            flash("An unexpected error occurred. Please try again.")
            return "Something went wrong. Check logs.", 500
    wrapper.__name__ = func.__name__
    return wrapper
from flask import render_template

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(500) 
    def server_error(error):
        return render_template('errors/500.html'), 500

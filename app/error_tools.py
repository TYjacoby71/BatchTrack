
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


from flask import Blueprint, request, render_template, redirect, session

auth_bp = Blueprint('auth', __name__)

# Dummy user setup
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "prod": {"password": "prod123", "role": "production"},
    "viewer": {"password": "view123", "role": "viewer"}
}

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        user = USERS.get(username)

        if user and user["password"] == password:
            session["user"] = username
            session["role"] = user["role"]
            return redirect("/")
        else:
            return render_template("login.html", error="Invalid login")

    return render_template("login.html")

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect("/login")

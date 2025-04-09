
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(32), default='user')
    
    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

recipe_ingredients = db.Table('recipe_ingredients',
    db.Column('recipe_id', db.Integer, db.ForeignKey('recipe.id')),
    db.Column('ingredient_id', db.Integer, db.ForeignKey('ingredient.id')),
    db.Column('amount', db.Float),
    db.Column('unit', db.String(32))
)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    instructions = db.Column(db.Text)
    label_prefix = db.Column(db.String(8))
    qr_image = db.Column(db.String(128))
    ingredients = db.relationship('Ingredient', secondary=recipe_ingredients,
                                backref=db.backref('recipes', lazy='dynamic'))

class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer)
    recipe_name = db.Column(db.String(128))
    label_code = db.Column(db.String(32))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    scale = db.Column(db.Float)
    notes = db.Column(db.Text)
    tags = db.Column(db.Text)
    total_cost = db.Column(db.Float)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer)
    name = db.Column(db.String(128))
    label_code = db.Column(db.String(32))
    image = db.Column(db.String(128))
    expiration_date = db.Column(db.Date)
    quantity = db.Column(db.Integer)
    unit = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    quantity = db.Column(db.Float)
    unit = db.Column(db.String(32))

class InventoryUnit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)
    type = db.Column(db.String(16))
    aliases = db.Column(db.Text)
    base_equivalent = db.Column(db.Float)
    density_required = db.Column(db.Boolean, default=False)

class ProductUnit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

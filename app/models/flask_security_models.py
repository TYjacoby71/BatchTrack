
from flask_security import UserMixin, RoleMixin
from ..extensions import db
from datetime import datetime

# Flask-Security-Too required models
roles_users = db.Table('roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('flask_role.id'))
)

class FlaskRole(db.Model, RoleMixin):
    __tablename__ = 'flask_role'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))
    
    def __str__(self):
        return self.name

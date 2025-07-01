
from app.extensions import db
from datetime import datetime

class BatchContainer(db.Model):
    __tablename__ = 'batch_containers'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    container_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)  # Null for one-time containers
    container_name = db.Column(db.String(200), nullable=False)
    container_size = db.Column(db.Float, nullable=False, default=0)
    quantity_used = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(50), nullable=False)  # primary_packaging, overflow, broke_container, test_sample, other
    one_time_use = db.Column(db.Boolean, default=False)  # For emergency containers when inventory is zero
    exclude_from_product = db.Column(db.Boolean, default=False)  # For broken containers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    batch = db.relationship('Batch', backref='container_usage')
    container_item = db.relationship('InventoryItem', backref='batch_usage')
    created_by_user = db.relationship('User', backref='container_additions')
    
    @property
    def total_capacity(self):
        """Calculate total capacity of this container usage"""
        return self.container_size * self.quantity_used
    
    @property
    def is_valid_for_product(self):
        """Check if this container should count toward final product"""
        return not self.exclude_from_product
    
    def __repr__(self):
        return f'<BatchContainer {self.container_name} x{self.quantity_used} for Batch {self.batch_id}>'

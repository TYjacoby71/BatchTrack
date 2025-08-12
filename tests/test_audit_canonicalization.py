
import pytest
from unittest.mock import patch, MagicMock


def test_api_reservation_routes_uses_canonical_audit(app):
    """Test that API reservation routes use canonical audit helper"""
    with app.app_context():
        with patch('app.services.inventory_adjustment.record_audit_entry') as mock_audit:
            
            # Mock the route function that writes audit entries
            from app.blueprints.api.reservation_routes import _write_unreserved_audit
            
            _write_unreserved_audit(
                item_id=123,
                unit="kg", 
                notes="Test unreserve"
            )
            
            # Assert canonical helper was called
            mock_audit.assert_called_once_with(
                item_id=123,
                change_type="unreserved_audit",
                notes="Unreserved via API: Test unreserve"
            )


def test_products_routes_uses_canonical_audit(app):
    """Test that product creation uses canonical audit helper"""
    with app.app_context():
        with patch('app.services.inventory_adjustment.record_audit_entry') as mock_audit:
            
            # Mock the route function that writes audit entries  
            from app.blueprints.products.products import _write_product_created_audit
            
            mock_variant = MagicMock()
            mock_variant.id = 456
            mock_variant.name = "Test Product"
            
            _write_product_created_audit(mock_variant)
            
            # Assert canonical helper was called
            mock_audit.assert_called_once_with(
                item_id=456,
                change_type="product_created",
                notes="Product variant created: Test Product"
            )


import pytest
from unittest.mock import patch, MagicMock
from app.services.reservation_service import ReservationService


def test_credit_specific_lot_called_on_reservation_release(app):
    """Test that releasing a reservation calls the canonical credit_specific_lot helper"""
    with app.app_context():
        with patch('app.services.inventory_adjustment.credit_specific_lot') as mock_credit:
            mock_credit.return_value = True
            
            # Mock reservation object
            mock_reservation = MagicMock()
            mock_reservation.inventory_item_id = 123
            mock_reservation.source_fifo_id = 456
            mock_reservation.quantity = 5.0
            
            # Mock source entry
            mock_source_entry = MagicMock()
            mock_source_entry.unit = "kg"
            
            with patch('app.models.inventory.InventoryHistory.query') as mock_query:
                mock_query.get.return_value = mock_source_entry
                
                # This should trigger the credit_specific_lot call
                ReservationService._release_reservation_inventory(mock_reservation, mock_source_entry)
                
                # Assert it was called with correct parameters
                mock_credit.assert_called_once_with(
                    item_id=123,
                    fifo_entry_id=456,
                    qty=5.0,
                    unit="kg",
                    notes="Released reservation → credit back lot #456"
                )


def test_record_audit_entry_called_for_unreserved_audit(app):
    """Test that audit entries use the canonical record_audit_entry helper"""
    with app.app_context():
        with patch('app.services.inventory_adjustment.record_audit_entry') as mock_audit:
            
            # Mock reservation object
            mock_reservation = MagicMock()
            mock_reservation.inventory_item_id = 123
            mock_reservation.source_fifo_id = 456
            mock_reservation.id = 789
            
            # This should trigger the record_audit_entry call
            ReservationService._write_unreserved_audit_entry(mock_reservation)
            
            # Assert it was called with correct parameters
            mock_audit.assert_called_once_with(
                item_id=123,
                change_type="unreserved_audit",
                notes="Released reservation (ref lot #456)",
                fifo_reference_id=456,
                source="reservation_789"
            )

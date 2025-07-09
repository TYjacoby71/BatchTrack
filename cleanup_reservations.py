
#!/usr/bin/env python3
"""
Reservation Cleanup Script for BatchTrack

This script cleans up various types of problematic reservations:
- Expired reservations that haven't been properly released
- Orphaned reservations with missing product items
- Reservations with invalid FIFO references
- Old released/cancelled reservations (optional cleanup)
"""

import sys
import os
from datetime import datetime, timedelta

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, Reservation, InventoryItem
from app.models.product import ProductSKUHistory
from app.services.reservation_service import ReservationService
from sqlalchemy import and_, or_

def cleanup_expired_reservations(app, dry_run=True):
    """Clean up reservations that have expired but are still marked as active"""
    with app.app_context():
        print("🔍 Checking for expired reservations...")
        
        expired_reservations = Reservation.query.filter(
            and_(
                Reservation.status == 'active',
                Reservation.expires_at.isnot(None),
                Reservation.expires_at < datetime.utcnow()
            )
        ).all()
        
        print(f"Found {len(expired_reservations)} expired active reservations")
        
        if not dry_run and expired_reservations:
            released_count = 0
            for reservation in expired_reservations:
                try:
                    # Use the reservation service to properly release it
                    success, message = ReservationService.release_reservation(reservation.order_id)
                    if success:
                        released_count += 1
                        print(f"✅ Released expired reservation {reservation.id} for order {reservation.order_id}")
                    else:
                        print(f"❌ Failed to release reservation {reservation.id}: {message}")
                except Exception as e:
                    print(f"❌ Error releasing reservation {reservation.id}: {str(e)}")
            
            db.session.commit()
            print(f"✅ Successfully released {released_count} expired reservations")
        elif expired_reservations:
            for res in expired_reservations:
                print(f"  - Order: {res.order_id}, Expired: {res.expires_at}, Quantity: {res.quantity}")

def cleanup_orphaned_reservations(app, dry_run=True):
    """Clean up reservations with missing product items or reserved items"""
    with app.app_context():
        print("\n🔍 Checking for orphaned reservations...")
        
        # Find reservations where product_item or reserved_item no longer exists
        orphaned_reservations = db.session.query(Reservation).filter(
            or_(
                ~db.session.query(InventoryItem).filter(InventoryItem.id == Reservation.product_item_id).exists(),
                ~db.session.query(InventoryItem).filter(InventoryItem.id == Reservation.reserved_item_id).exists()
            )
        ).all()
        
        print(f"Found {len(orphaned_reservations)} orphaned reservations")
        
        if not dry_run and orphaned_reservations:
            for reservation in orphaned_reservations:
                try:
                    # Mark as cancelled since we can't properly release without the items
                    reservation.status = 'cancelled'
                    reservation.released_at = datetime.utcnow()
                    print(f"✅ Marked orphaned reservation {reservation.id} as cancelled")
                except Exception as e:
                    print(f"❌ Error handling orphaned reservation {reservation.id}: {str(e)}")
            
            db.session.commit()
            print(f"✅ Successfully cleaned up {len(orphaned_reservations)} orphaned reservations")
        elif orphaned_reservations:
            for res in orphaned_reservations:
                print(f"  - ID: {res.id}, Order: {res.order_id}, Status: {res.status}")

def cleanup_invalid_fifo_references(app, dry_run=True):
    """Clean up reservations with invalid FIFO references"""
    with app.app_context():
        print("\n🔍 Checking for reservations with invalid FIFO references...")
        
        invalid_fifo_reservations = []
        reservations_with_fifo = Reservation.query.filter(
            and_(
                Reservation.source_fifo_id.isnot(None),
                Reservation.status == 'active'
            )
        ).all()
        
        for reservation in reservations_with_fifo:
            # Check if the FIFO entry exists
            fifo_entry = ProductSKUHistory.query.get(reservation.source_fifo_id)
            if not fifo_entry:
                invalid_fifo_reservations.append(reservation)
        
        print(f"Found {len(invalid_fifo_reservations)} reservations with invalid FIFO references")
        
        if not dry_run and invalid_fifo_reservations:
            for reservation in invalid_fifo_reservations:
                try:
                    # Clear the invalid FIFO reference but keep the reservation
                    reservation.source_fifo_id = None
                    print(f"✅ Cleared invalid FIFO reference for reservation {reservation.id}")
                except Exception as e:
                    print(f"❌ Error clearing FIFO reference for reservation {reservation.id}: {str(e)}")
            
            db.session.commit()
            print(f"✅ Successfully cleared {len(invalid_fifo_reservations)} invalid FIFO references")
        elif invalid_fifo_reservations:
            for res in invalid_fifo_reservations:
                print(f"  - ID: {res.id}, Order: {res.order_id}, Invalid FIFO ID: {res.source_fifo_id}")

def cleanup_old_completed_reservations(app, days_old=30, dry_run=True):
    """Clean up old completed reservations (released, cancelled, fulfilled)"""
    with app.app_context():
        print(f"\n🔍 Checking for completed reservations older than {days_old} days...")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        old_completed_reservations = Reservation.query.filter(
            and_(
                Reservation.status.in_(['released', 'cancelled', 'fulfilled', 'expired']),
                or_(
                    Reservation.released_at < cutoff_date,
                    Reservation.converted_at < cutoff_date,
                    and_(
                        Reservation.released_at.is_(None),
                        Reservation.converted_at.is_(None),
                        Reservation.created_at < cutoff_date
                    )
                )
            )
        ).all()
        
        print(f"Found {len(old_completed_reservations)} old completed reservations")
        
        if not dry_run and old_completed_reservations:
            for reservation in old_completed_reservations:
                try:
                    db.session.delete(reservation)
                    print(f"✅ Deleted old completed reservation {reservation.id}")
                except Exception as e:
                    print(f"❌ Error deleting old reservation {reservation.id}: {str(e)}")
            
            db.session.commit()
            print(f"✅ Successfully deleted {len(old_completed_reservations)} old completed reservations")
        elif old_completed_reservations:
            for res in old_completed_reservations:
                print(f"  - ID: {res.id}, Order: {res.order_id}, Status: {res.status}, Created: {res.created_at}")

def fix_reserved_item_quantities(app, dry_run=True):
    """Fix reserved item quantities that might be out of sync"""
    with app.app_context():
        print("\n🔍 Checking reserved item quantities...")
        
        # Get all reserved items
        reserved_items = InventoryItem.query.filter(InventoryItem.type == 'product-reserved').all()
        
        fixes_needed = []
        for reserved_item in reserved_items:
            # Calculate what the quantity should be based on active reservations
            active_reservations_total = db.session.query(db.func.sum(Reservation.quantity)).filter(
                and_(
                    Reservation.reserved_item_id == reserved_item.id,
                    Reservation.status == 'active'
                )
            ).scalar() or 0
            
            if reserved_item.quantity != active_reservations_total:
                fixes_needed.append((reserved_item, active_reservations_total))
        
        print(f"Found {len(fixes_needed)} reserved items with incorrect quantities")
        
        if not dry_run and fixes_needed:
            for reserved_item, correct_quantity in fixes_needed:
                old_quantity = reserved_item.quantity
                reserved_item.quantity = correct_quantity
                print(f"✅ Fixed {reserved_item.name}: {old_quantity} → {correct_quantity}")
            
            db.session.commit()
            print(f"✅ Successfully fixed {len(fixes_needed)} reserved item quantities")
        elif fixes_needed:
            for reserved_item, correct_quantity in fixes_needed:
                print(f"  - {reserved_item.name}: Current={reserved_item.quantity}, Should be={correct_quantity}")

def print_reservation_summary(app):
    """Print a summary of all reservations"""
    with app.app_context():
        print("\n📊 Reservation Summary:")
        
        total = Reservation.query.count()
        active = Reservation.query.filter(Reservation.status == 'active').count()
        released = Reservation.query.filter(Reservation.status == 'released').count()
        cancelled = Reservation.query.filter(Reservation.status == 'cancelled').count()
        fulfilled = Reservation.query.filter(Reservation.status == 'fulfilled').count()
        expired = Reservation.query.filter(Reservation.status == 'expired').count()
        
        print(f"  Total reservations: {total}")
        print(f"  Active: {active}")
        print(f"  Released: {released}")
        print(f"  Cancelled: {cancelled}")
        print(f"  Fulfilled: {fulfilled}")
        print(f"  Expired: {expired}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up BatchTrack reservations')
    parser.add_argument('--dry-run', action='store_true', default=True,
                      help='Show what would be cleaned without making changes (default)')
    parser.add_argument('--execute', action='store_true',
                      help='Actually perform the cleanup operations')
    parser.add_argument('--old-days', type=int, default=30,
                      help='Days old for cleaning completed reservations (default: 30)')
    parser.add_argument('--skip-expired', action='store_true',
                      help='Skip cleaning expired reservations')
    parser.add_argument('--skip-orphaned', action='store_true',
                      help='Skip cleaning orphaned reservations')
    parser.add_argument('--skip-fifo', action='store_true',
                      help='Skip cleaning invalid FIFO references')
    parser.add_argument('--skip-old', action='store_true',
                      help='Skip cleaning old completed reservations')
    parser.add_argument('--skip-quantities', action='store_true',
                      help='Skip fixing reserved item quantities')
    
    args = parser.parse_args()
    
    # If --execute is specified, turn off dry_run
    dry_run = not args.execute
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("Use --execute to actually perform cleanup operations\n")
    else:
        print("⚠️  EXECUTING CLEANUP - Changes will be made to the database\n")
    
    app = create_app()
    
    print_reservation_summary(app)
    
    if not args.skip_expired:
        cleanup_expired_reservations(app, dry_run)
    
    if not args.skip_orphaned:
        cleanup_orphaned_reservations(app, dry_run)
    
    if not args.skip_fifo:
        cleanup_invalid_fifo_references(app, dry_run)
    
    if not args.skip_quantities:
        fix_reserved_item_quantities(app, dry_run)
    
    if not args.skip_old:
        cleanup_old_completed_reservations(app, args.old_days, dry_run)
    
    print_reservation_summary(app)
    
    if dry_run:
        print("\n✅ Dry run completed. Use --execute to perform actual cleanup.")
    else:
        print("\n✅ Cleanup completed!")

if __name__ == '__main__':
    main()

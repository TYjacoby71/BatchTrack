import click
from datetime import datetime

from app import create_app
from app.models import db, UnifiedInventoryHistory, Batch
from app.models.domain_event import DomainEvent


def backfill_inventory_events():
    count = 0
    # Map legacy change types roughly to our event change types
    for h in UnifiedInventoryHistory.query.yield_per(1000):
        try:
            # Skip if already backfilled (best-effort heuristic)
            exists = DomainEvent.query.filter_by(
                entity_type='inventory_item', entity_id=h.inventory_item_id, occurred_at=h.timestamp, event_name='inventory_adjusted'
            ).first()
            if exists:
                continue

            quantity_delta = float(h.quantity_change or 0)
            evt = DomainEvent(
                event_name='inventory_adjusted',
                occurred_at=h.timestamp or datetime.utcnow(),
                organization_id=h.organization_id,
                user_id=h.created_by,
                entity_type='inventory_item',
                entity_id=h.inventory_item_id,
                properties={
                    'change_type': h.change_type,
                    'quantity_delta': quantity_delta,
                    'unit': h.unit,
                    'notes': h.notes,
                    'batch_id': h.batch_id,
                    'fifo_code': h.fifo_code,
                }
            )
            db.session.add(evt)
            count += 1
            if count % 1000 == 0:
                db.session.commit()
        except Exception:
            db.session.rollback()
    db.session.commit()
    return count


def backfill_batch_events():
    count = 0
    for b in Batch.query.yield_per(1000):
        try:
            # Completed event
            if b.completed_at:
                exists = DomainEvent.query.filter_by(
                    entity_type='batch', entity_id=b.id, event_name='batch_completed'
                ).first()
                if not exists:
                    evt = DomainEvent(
                        event_name='batch_completed',
                        occurred_at=b.completed_at,
                        organization_id=b.organization_id,
                        user_id=b.created_by,
                        entity_type='batch',
                        entity_id=b.id,
                        properties={
                            'label_code': b.label_code,
                            'final_quantity': b.final_quantity,
                            'output_unit': b.output_unit,
                            'completed_at': (b.completed_at.isoformat() if b.completed_at else None),
                        }
                    )
                    db.session.add(evt)
                    count += 1

            # Started event
            if b.started_at:
                exists = DomainEvent.query.filter_by(
                    entity_type='batch', entity_id=b.id, event_name='batch_started'
                ).first()
                if not exists:
                    evt = DomainEvent(
                        event_name='batch_started',
                        occurred_at=b.started_at,
                        organization_id=b.organization_id,
                        user_id=b.created_by,
                        entity_type='batch',
                        entity_id=b.id,
                        properties={
                            'label_code': b.label_code,
                            'projected_yield': b.projected_yield,
                            'projected_yield_unit': b.projected_yield_unit,
                            'batch_type': b.batch_type,
                        }
                    )
                    db.session.add(evt)
                    count += 1

            # Cancelled event
            if b.cancelled_at:
                exists = DomainEvent.query.filter_by(
                    entity_type='batch', entity_id=b.id, event_name='batch_cancelled'
                ).first()
                if not exists:
                    evt = DomainEvent(
                        event_name='batch_cancelled',
                        occurred_at=b.cancelled_at,
                        organization_id=b.organization_id,
                        user_id=b.created_by,
                        entity_type='batch',
                        entity_id=b.id,
                        properties={'label_code': b.label_code}
                    )
                    db.session.add(evt)
                    count += 1

            if count and count % 1000 == 0:
                db.session.commit()
        except Exception:
            db.session.rollback()
    db.session.commit()
    return count


@click.group()
def cli():
    pass


@cli.command()
def inventory():
    app = create_app()
    with app.app_context():
        created = backfill_inventory_events()
        click.echo(f"Backfilled {created} inventory events")


@cli.command()
def batches():
    app = create_app()
    with app.app_context():
        created = backfill_batch_events()
        click.echo(f"Backfilled {created} batch events")


if __name__ == '__main__':
    cli()

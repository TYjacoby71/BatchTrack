"""Production-safe maintenance command set."""

import click
from flask.cli import with_appcontext

from ...extensions import db


@click.command("update-permissions")
@with_appcontext
def update_permissions_command():
    """Update permissions from consolidated JSON (production-safe)."""
    try:
        print("🔄 Updating permissions from consolidated_permissions.json...")

        from ...seeders.consolidated_permission_seeder import seed_consolidated_permissions

        seed_consolidated_permissions()

        print("✅ Permissions updated successfully!")
        print("   - New permissions added")
        print("   - Existing permissions updated")
        print("   - Old permissions deactivated")

    except Exception as e:
        print(f"❌ Permission update failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("update-addons")
@with_appcontext
def update_addons_command():
    """Update add-ons from addon_seeder (production-safe)."""
    try:
        print("🔄 Updating add-ons from addon_seeder...")

        from ...seeders.addon_seeder import backfill_addon_permissions, seed_addons

        seed_addons()
        backfill_addon_permissions()

        print("✅ Add-ons updated successfully!")
        print("   - New add-ons added")
        print("   - Existing add-ons updated")
        print("   - Tier add-on permissions backfilled")

    except Exception as e:
        print(f"❌ Add-on update failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("update-subscription-tiers")
@with_appcontext
def update_subscription_tiers_command():
    """Update subscription tiers (production-safe)."""
    try:
        print("🔄 Updating subscription tiers...")

        from ...seeders.subscription_seeder import seed_subscription_tiers

        seed_subscription_tiers()

        print("✅ Subscription tiers updated!")

    except Exception as e:
        print(f"❌ Subscription tier update failed: {str(e)}")
        db.session.rollback()
        raise


@click.command("dispatch-domain-events")
@click.option("--poll-interval", default=5.0, show_default=True, help="Seconds to wait between polls when idle.")
@click.option("--batch-size", default=100, show_default=True, type=int, help="Maximum events to process per batch.")
@click.option("--once", is_flag=True, help="Process a single batch instead of running continuously.")
@with_appcontext
def dispatch_domain_events_command(poll_interval: float, batch_size: int, once: bool):
    """Run the asynchronous dispatcher that delivers pending domain events."""
    from app.services.domain_event_dispatcher import DomainEventDispatcher

    dispatcher = DomainEventDispatcher(batch_size=batch_size)

    if once:
        metrics = dispatcher.dispatch_pending_events()
        click.echo(
            f"Processed {metrics['processed']} events ({metrics['succeeded']} succeeded, {metrics['failed']} failed)."
        )
    else:
        click.echo(
            f"Starting domain event dispatcher (batch_size={batch_size}, poll_interval={poll_interval}s)..."
        )
        dispatcher.run_forever(poll_interval=poll_interval)


MAINTENANCE_COMMANDS = [
    update_permissions_command,
    update_addons_command,
    update_subscription_tiers_command,
    dispatch_domain_events_command,
]


import click
from datetime import date, datetime

from app import create_app
from app.services.freshness_snapshot_service import FreshnessSnapshotService


@click.command()
@click.option('--date', 'date_str', required=False, help='YYYY-MM-DD (defaults to today)')
def main(date_str: str):
    app = create_app()
    with app.app_context():
        if date_str:
            snapshot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            snapshot_date = date.today()
        total = FreshnessSnapshotService.compute_for_all(snapshot_date)
        click.echo(f"Freshness snapshot completed for {snapshot_date.isoformat()}: {total} items")


if __name__ == '__main__':
    main()

import click
from app import create_app


@click.command()
def main():
    app = create_app()
    with app.app_context():
        from app.services.retention_service import RetentionService
        deleted = RetentionService.nightly_sweep_delete_due()
        click.echo(f"Retention sweep completed. Deleted: {deleted}")


if __name__ == '__main__':
    main()


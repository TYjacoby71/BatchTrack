import click

from app import create_app


@click.command()
@click.option("--commit/--dry-run", default=True, help="Persist changes (default) or just report.")
def main(commit):
    app = create_app()
    with app.app_context():
        from app.models import db
        from app.models.global_item import GlobalItem
        from app.services.global_item_metadata_service import GlobalItemMetadataService

        updated = 0
        total = 0
        for gi in GlobalItem.query.filter(GlobalItem.is_archived != True).all():
            total += 1
            new_meta = GlobalItemMetadataService.merge_metadata(gi)
            if new_meta != (gi.metadata_json or {}):
                updated += 1
                gi.metadata_json = new_meta
        if commit and updated:
            db.session.commit()
        elif not commit:
            db.session.rollback()
        click.echo(f"Processed {total} global items. Updated metadata for {updated}. {'Committed' if commit else 'Dry run'}")


if __name__ == "__main__":
    main()

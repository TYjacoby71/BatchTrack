import click

from app import create_app


@click.command()
@click.option('--batch-size', default=100, show_default=True, type=int, help='Candidates per batch.')
@click.option('--page-size', default=500, show_default=True, type=int, help='Inventory rows pulled per scan page.')
@click.option('--max-batches', default=None, type=int, help='Optional cap on batches per run.')
def main(batch_size: int, page_size: int, max_batches: int | None):
    """Standalone runner for the Community Scout discovery job."""
    app = create_app()
    with app.app_context():
        from app.services.community_scout_service import CommunityScoutService

        stats = CommunityScoutService.generate_batches(
            batch_size=batch_size,
            page_size=page_size,
            max_batches=max_batches,
        )
        click.echo(
            f"Community Scout complete — batches: {stats['batches_created']}, candidates: {stats['candidates_created']}, scanned: {stats['scanned']}, skipped_existing: {stats['skipped_existing']}"
        )


if __name__ == '__main__':
    main()

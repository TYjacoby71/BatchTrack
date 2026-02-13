"""CLI registration by section/purpose/process groups."""

from .assets import ASSET_COMMANDS
from .destructive import DESTRUCTIVE_COMMANDS
from .maintenance import MAINTENANCE_COMMANDS
from .schema import SCHEMA_COMMANDS
from .seeding import BOOTSTRAP_COMMANDS, INDIVIDUAL_SEED_COMMANDS, RECOVERY_COMMANDS


def register_commands(app):
    """Register all CLI commands in stable grouped order."""
    for command in SCHEMA_COMMANDS:
        app.cli.add_command(command)

    for command in BOOTSTRAP_COMMANDS:
        app.cli.add_command(command)

    for command in DESTRUCTIVE_COMMANDS:
        app.cli.add_command(command)

    for command in INDIVIDUAL_SEED_COMMANDS:
        app.cli.add_command(command)

    for command in MAINTENANCE_COMMANDS:
        app.cli.add_command(command)

    for command in RECOVERY_COMMANDS:
        app.cli.add_command(command)

    for command in ASSET_COMMANDS:
        app.cli.add_command(command)


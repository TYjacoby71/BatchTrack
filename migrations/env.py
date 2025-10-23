import logging
import os
import sys
from logging.config import fileConfig

from flask import current_app

from alembic import context
from sqlalchemy import text

# Production safety check removed - migrations now allowed in all environments


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def _normalize_db_url(url: str | None) -> str | None:
    if not url:
        return None
    # SQLAlchemy 2.x prefers postgresql:// over postgres://
    if url.startswith('postgres://'):
        return 'postgresql://' + url[len('postgres://'):]
    return url


def get_engine():
    """Always derive the engine from Flask's SQLAlchemy configuration.

    This ensures we use the same connection parameters as the app
    across environments (SQLite locally, Postgres on Render).
    """
    try:
        # Flask-SQLAlchemy < 3
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # Flask-SQLAlchemy >= 3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace('%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# Dynamically import all models so Alembic can see them
import os
import importlib
import pkgutil

def import_all_models():
    """Dynamically import all model files from app.models"""
    try:
        # First import the main models package
        from app import models

        # Get the models directory path
        models_dir = os.path.join(os.path.dirname(models.__file__))

        # Import all Python files in the models directory
        for finder, name, ispkg in pkgutil.iter_modules([models_dir]):
            if name != '__init__' and not name.startswith('_'):
                try:
                    importlib.import_module(f'app.models.{name}')
                    logger.info(f'Imported model module: app.models.{name}')
                except ImportError as e:
                    logger.warning(f'Could not import app.models.{name}: {e}')

    except Exception as e:
        logger.error(f'Error importing models: {e}')

# Import all models dynamically so Alembic can autogenerate accurately
import_all_models()

# Always use the Flask SQLAlchemy URI
config.set_main_option("sqlalchemy.url", current_app.config["SQLALCHEMY_DATABASE_URI"])
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    # Mirror online config defaults coming from Flask-Migrate init
    conf_args = getattr(current_app.extensions.get('migrate'), 'configure_args', {})
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        compare_type=conf_args.get("compare_type", False),
        compare_server_default=conf_args.get("compare_server_default", False),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    # Ensure each revision runs in its own transaction (Postgres-friendly)
    conf_args["transaction_per_migration"] = True
    # Avoid spurious diffs from server defaults while models use Python defaults
    conf_args["compare_server_default"] = False
    # Be conservative on type diffs to keep cross-db compatibility
    conf_args.setdefault("compare_type", False)
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        # Clean up any leftover temporary tables from failed SQLite migrations
        if 'sqlite' in str(connection.engine.url):
            try:
                # Get list of all temporary tables
                result = connection.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name LIKE '_alembic_tmp_%'
                """))
                temp_tables = [row[0] for row in result.fetchall()]
                
                if temp_tables:
                    logger.info(f"Cleaning up {len(temp_tables)} temporary tables from failed migrations")
                    for table_name in temp_tables:
                        try:
                            connection.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                            logger.info(f"   ✅ Cleaned up temporary table: {table_name}")
                        except Exception as e:
                            logger.warning(f"   ⚠️  Could not clean temporary table {table_name}: {e}")
                    connection.commit()
            except Exception as e:
                logger.warning(f"Could not clean temporary tables: {e}")
        
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""Database schema and model synchronization commands."""

import click
from flask.cli import with_appcontext
from sqlalchemy import inspect, text

from ...extensions import db


@click.command("create-app")
@with_appcontext
def create_app_command():
    """Initialize database and create all model tables."""
    try:
        print("🚀 Creating BatchTrack application database...")

        print("📦 Dynamically importing all models...")

        from ... import models

        import importlib
        import os
        import pkgutil

        models_imported = 0

        if hasattr(models, "__all__"):
            for model_name in models.__all__:
                if hasattr(models, model_name):
                    model_class = getattr(models, model_name)
                    if hasattr(model_class, "__tablename__"):
                        models_imported += 1
                        print(f"   ✓ {model_name}")

        models_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models")
        models_dir = os.path.normpath(models_dir)
        for _, name, _ in pkgutil.iter_modules([models_dir]):
            if name != "__init__" and not name.startswith("_"):
                try:
                    importlib.import_module(f".models.{name}", package="app")
                    print(f"   ✓ Loaded models from {name}.py")
                except ImportError as e:
                    print(f"   ⚠️  Could not import models.{name}: {e}")

        print(f"✅ {models_imported} models imported dynamically")

        print("🏗️  Creating database tables...")
        db.create_all()
        print("✅ Database tables created")

        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📊 Created {len(tables)} tables: {', '.join(sorted(tables))}")

        print("✅ BatchTrack application database created successfully!")
        print("🔄 Next steps:")
        print("   1. Run: flask init-production (to seed initial data)")
        print("   2. Or run individual seeders as needed")

    except Exception as e:
        print(f"❌ Database creation failed: {str(e)}")
        import traceback

        traceback.print_exc()
        raise


@click.command("sync-schema")
@with_appcontext
def sync_schema_command():
    """Safely sync database schema to match models (adds missing tables/columns only)."""
    try:
        print("🚀 Syncing database schema to match models (safe mode)...")
        print("📦 Dynamically importing all models...")

        from ... import models

        import importlib
        import os
        import pkgutil

        models_imported = 0

        if hasattr(models, "__all__"):
            for model_name in models.__all__:
                if hasattr(models, model_name):
                    model_class = getattr(models, model_name)
                    if hasattr(model_class, "__tablename__"):
                        models_imported += 1
                        print(f"   ✓ {model_name}")

        models_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models")
        models_dir = os.path.normpath(models_dir)
        for _, name, _ in pkgutil.iter_modules([models_dir]):
            if name != "__init__" and not name.startswith("_"):
                try:
                    importlib.import_module(f".models.{name}", package="app")
                    print(f"   ✓ Loaded models from {name}.py")
                except ImportError as e:
                    print(f"   ⚠️  Could not import models.{name}: {e}")

        print(f"✅ {models_imported} models imported dynamically")

        print("🏗️  Creating any missing tables...")
        existing_tables = set(inspect(db.engine).get_table_names())

        db.create_all()

        inspector = inspect(db.engine)
        tables_after = set(inspector.get_table_names())
        new_tables = tables_after - existing_tables

        if new_tables:
            print(f"✅ Added {len(new_tables)} new tables: {', '.join(sorted(new_tables))}")
        else:
            print("✅ No new tables needed")

        print("🔧 Checking for missing columns in existing tables...")
        columns_added = 0

        for table_name in existing_tables:
            existing_columns = {col["name"]: col for col in inspector.get_columns(table_name)}

            model_class = None
            for model_name in models.__all__:
                if hasattr(models, model_name):
                    model_cls = getattr(models, model_name)
                    if hasattr(model_cls, "__tablename__") and model_cls.__tablename__ == table_name:
                        model_class = model_cls
                        break

            if not model_class:
                print(f"   ⚠️  No model found for table: {table_name}")
                continue

            expected_columns = {}
            for column_name, column in model_class.__table__.columns.items():
                expected_columns[column_name] = column

            missing_columns = set(expected_columns.keys()) - set(existing_columns.keys())

            if missing_columns:
                print(f"   📋 Table '{table_name}' missing columns: {', '.join(missing_columns)}")

                for column_name in missing_columns:
                    column = expected_columns[column_name]

                    try:
                        column_type = column.type.compile(db.engine.dialect)
                        nullable = "NULL" if column.nullable else "NOT NULL"

                        default_clause = ""
                        if column.default is not None:
                            if hasattr(column.default, "arg"):
                                if callable(column.default.arg):
                                    nullable = "NULL"
                                else:
                                    default_value = column.default.arg
                                    if isinstance(default_value, str):
                                        default_clause = f" DEFAULT '{default_value}'"
                                    else:
                                        default_clause = f" DEFAULT {default_value}"
                            else:
                                default_value = column.default
                                if isinstance(default_value, str):
                                    default_clause = f" DEFAULT '{default_value}'"
                                else:
                                    default_clause = f" DEFAULT {default_value}"

                        nullable = "NULL"

                        sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type} {nullable}{default_clause}'
                        db.session.execute(text(sql))
                        db.session.commit()

                        columns_added += 1
                        print(f"      ✅ Added column: {column_name} ({column_type})")

                    except Exception as e:
                        print(f"      ❌ Failed to add column {column_name}: {e}")
                        db.session.rollback()
            else:
                print(f"   ✅ Table '{table_name}' schema is up to date")

        print(f"📊 Total tables: {len(tables_after)}")
        print(f"📊 Total columns added: {columns_added}")
        print("✅ Database schema safely synced to match models!")
        print("🔄 Note: This only adds missing tables/columns - existing data is preserved")
        print("⚠️  New columns are added as nullable for safety")

    except Exception as e:
        print(f"❌ Schema sync failed: {str(e)}")
        import traceback

        traceback.print_exc()
        db.session.rollback()
        raise


SCHEMA_COMMANDS = [create_app_command, sync_schema_command]


"""0005 cleanup guardrails and ingredient attribute expansion

Revision ID: 0005_cleanup_guardrails
Revises: 0004_seed_presets
Create Date: 2025-10-21 20:29:06.302261

"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker


# revision identifiers, used by Alembic.
revision = '0005_cleanup_guardrails'
down_revision = '0004_seed_presets'
branch_labels = None
depends_on = None


def upgrade():
    from migrations.postgres_helpers import is_postgresql, is_sqlite, safe_add_column

    bind = op.get_bind()

    # Drop legacy index before renaming JSON column (succeeds even if absent)
    try:
        op.execute("DROP INDEX IF EXISTS ix_global_item_aka_gin")
    except Exception:
        pass

    # Expand global item attributes  
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        columns = [col['name'] for col in inspector.get_columns('global_item')]
        if 'aka_names' in columns:
            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('aka_names', new_column_name='aliases')
        elif 'aliases' not in columns:
            # Neither column exists - this is unexpected 
            print("⚠️  Neither 'aka_names' nor 'aliases' column found in global_item table")
    except Exception as e:
        print(f"⚠️  Could not rename aka_names column: {e}")

    # Add new columns to global_item for enhanced ingredient data (safely)
    safe_add_column('global_item', sa.Column('fatty_acid_profile', sa.JSON()))
    safe_add_column('global_item', sa.Column('brewing_diastatic_power_lintner', sa.Float()))
    safe_add_column('global_item', sa.Column('brewing_potential_sg', sa.Float()))
    safe_add_column('global_item', sa.Column('brewing_color_srm', sa.Float()))
    safe_add_column('global_item', sa.Column('protein_content_pct', sa.Float()))
    safe_add_column('global_item', sa.Column('certifications', sa.JSON()))
    safe_add_column('global_item', sa.Column('inci_name', sa.String(256)))
    safe_add_column('global_item', sa.Column('recommended_fragrance_load_pct', sa.Float()))
    safe_add_column('global_item', sa.Column('recommended_usage_rate', sa.String(128)))
    safe_add_column('global_item', sa.Column('is_active_ingredient', sa.Boolean()))

    # Alter is_active_ingredient server_default after it's added and set column types
    with op.batch_alter_table('global_item') as batch_op:
        batch_op.alter_column('is_active_ingredient', server_default=None, nullable=False)
        batch_op.alter_column('recommended_usage_rate',
               existing_type=sa.VARCHAR(length=128),
               type_=sa.String(length=64),
               existing_nullable=True)
        batch_op.alter_column('recommended_fragrance_load_pct',
               existing_type=sa.Float(),
               type_=sa.String(length=64),
               existing_nullable=True)

    if is_postgresql():
        try:
            bind.execute(sa.text(
                "CREATE INDEX IF NOT EXISTS ix_global_item_aliases_gin "
                "ON global_item USING gin ((aliases::jsonb))"
            ))
        except Exception:
            pass

    # Mirror new attributes onto inventory items
    # Add same columns to inventory_item for backwards compatibility (safely)
    safe_add_column('inventory_item', sa.Column('certifications', sa.JSON()))
    safe_add_column('inventory_item', sa.Column('fatty_acid_profile', sa.JSON()))
    safe_add_column('inventory_item', sa.Column('brewing_diastatic_power_lintner', sa.Float()))
    safe_add_column('inventory_item', sa.Column('brewing_potential_sg', sa.Float()))
    safe_add_column('inventory_item', sa.Column('brewing_color_srm', sa.Float()))
    safe_add_column('inventory_item', sa.Column('protein_content_pct', sa.Float()))
    safe_add_column('inventory_item', sa.Column('inci_name', sa.String(256)))
    safe_add_column('inventory_item', sa.Column('recommended_fragrance_load_pct', sa.Float()))
    safe_add_column('inventory_item', sa.Column('recommended_usage_rate', sa.String(128)))

    # Now alter the column types for inventory_item
    with op.batch_alter_table('inventory_item') as batch_op:
        batch_op.alter_column('recommended_usage_rate',
               existing_type=sa.VARCHAR(length=128),
               type_=sa.String(length=64),
               existing_nullable=True)
        batch_op.alter_column('recommended_fragrance_load_pct',
               existing_type=sa.Float(),
               type_=sa.String(length=64),
               existing_nullable=True)

    # Remove category-level attribute toggles
    with op.batch_alter_table('ingredient_category') as batch_op:
        for col in [
            'show_saponification_value',
            'show_iodine_value',
            'show_melting_point',
            'show_flash_point',
            'show_ph_value',
            'show_moisture_content',
            'show_shelf_life_days',
            'show_comedogenic_rating',
        ]:
            batch_op.drop_column(col)

    # PostgreSQL-specific performance indexes
    if is_postgresql():
        try:
            bind.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_recipe_category_data_gin ON recipe USING gin ((category_data::jsonb))'))
        except Exception:
            pass

        try:
            bind.execute(sa.text("""
                CREATE INDEX IF NOT EXISTS ix_global_item_alias_tsv ON global_item_alias 
                USING gin(to_tsvector('simple', alias))
            """))
        except Exception:
            pass

        try:
            bind.execute(sa.text('CREATE UNIQUE INDEX IF NOT EXISTS ix_product_category_lower_name ON product_category (lower(name))'))
        except Exception:
            pass

    if os.environ.get("SEED_PRESETS") == "1":
        _seed_global_ingredient_library()
    else:
        print("   ℹ️ Skipping global ingredient seeding in 0005 (SEED_PRESETS env not set to 1).")


def downgrade():
    from migrations.postgres_helpers import is_postgresql, is_sqlite, safe_add_column, safe_drop_column

    bind = op.get_bind()

    # Note: ingredient_category show_* columns were permanently removed
    # and are not restored in downgrade as they no longer exist in models

    # Remove inventory item extensions (safe drop if exists)
    columns_to_drop = [
        'certifications',
        'fatty_acid_profile', 
        'brewing_diastatic_power_lintner',
        'brewing_potential_sg',
        'brewing_color_srm',
        'protein_content_pct',
        'inci_name',
        'recommended_fragrance_load_pct',
        'recommended_usage_rate'
    ]

    for column_name in columns_to_drop:
        safe_drop_column('inventory_item', column_name, verbose=False)

    # Drop new index prior to renaming column back
    try:
        op.execute("DROP INDEX IF EXISTS ix_global_item_aliases_gin")
    except Exception:
        pass

    # Revert column types before dropping (if columns still exist)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        columns = [col['name'] for col in inspector.get_columns('global_item')]

        # Revert global_item column types
        if 'recommended_usage_rate' in columns:
            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('recommended_usage_rate',
                       existing_type=sa.String(length=64),
                       type_=sa.VARCHAR(length=128),
                       existing_nullable=True)

        if 'recommended_fragrance_load_pct' in columns:
            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('recommended_fragrance_load_pct',
                       existing_type=sa.String(length=64),
                       type_=sa.Float(),
                       existing_nullable=True)

        if 'is_active_ingredient' in columns:
            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('is_active_ingredient',
                       existing_type=sa.BOOLEAN(),
                       nullable=True)

        # Revert inventory_item column types
        inv_columns = [col['name'] for col in inspector.get_columns('inventory_item')]

        if 'recommended_usage_rate' in inv_columns:
            with op.batch_alter_table('inventory_item') as batch_op:
                batch_op.alter_column('recommended_usage_rate',
                       existing_type=sa.String(length=64),
                       type_=sa.VARCHAR(length=128),
                       existing_nullable=True)

        if 'recommended_fragrance_load_pct' in inv_columns:
            with op.batch_alter_table('inventory_item') as batch_op:
                batch_op.alter_column('recommended_fragrance_load_pct',
                       existing_type=sa.String(length=64),
                       type_=sa.Float(),
                       existing_nullable=True)

    except Exception as e:
        print(f"⚠️  Could not revert column types: {e}")

    # Remove global_item extensions (safe drop if exists)
    global_item_columns_to_drop = [
        'brewing_diastatic_power_lintner',
        'brewing_potential_sg', 
        'brewing_color_srm',
        'protein_content_pct',
        'fatty_acid_profile',
        'certifications',
        'inci_name',
        'recommended_fragrance_load_pct',
        'recommended_usage_rate',
        'is_active_ingredient'
    ]

    for column_name in global_item_columns_to_drop:
        safe_drop_column('global_item', column_name, verbose=False)

    # Rename column only if aliases exists (safe check)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        columns = [col['name'] for col in inspector.get_columns('global_item')]
        if 'aliases' in columns:
            with op.batch_alter_table('global_item') as batch_op:
                batch_op.alter_column('aliases', new_column_name='aka_names')
        elif 'aka_names' not in columns:
            # Neither column exists - this is unexpected but safe to skip
            print("⚠️  Neither 'aliases' nor 'aka_names' column found in global_item table")
    except Exception as e:
        print(f"⚠️  Could not rename aliases column: {e}")

    # Drop PostgreSQL-specific indexes created in upgrade
    if is_postgresql():
        index_drops = [
            'ix_product_category_lower_name',
            'ix_global_item_alias_tsv',
            'ix_recipe_category_data_gin',
        ]

        for index_name in index_drops:
            try:
                bind.execute(sa.text(f'DROP INDEX IF EXISTS {index_name}'))
            except Exception:
                pass
    else:
        try:
            op.execute("DROP INDEX IF EXISTS ix_global_item_aliases_gin")
        except Exception:
            pass


# ----------------------------
# Seed helpers (internal use)
# ----------------------------

def _seed_global_ingredient_library():
    seed_dir = _ingredient_seed_dir()
    if not seed_dir.exists():
        print(f"   ℹ️ Ingredient seed directory {seed_dir} missing; skipping global ingredient seeds.")
        return

    bind = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(bind, only=['ingredient_category', 'global_item', 'global_item_alias'])

    category_table = metadata.tables['ingredient_category']
    global_item_table = metadata.tables['global_item']
    alias_table = metadata.tables['global_item_alias']

    alias_column_key = 'aliases' if 'aliases' in global_item_table.c else 'aka_names'

    Session = sessionmaker(bind=bind)
    session = Session()

    inserted_categories = 0
    updated_categories = 0
    inserted_items = 0
    updated_items = 0
    inserted_aliases = 0

    try:
        for json_path in sorted(seed_dir.glob("*.json")):
            payload = _load_seed_payload(json_path)
            if payload is None:
                continue

            category_name = (payload.get('category_name') or '').strip()
            if not category_name:
                print(f"   ⚠️ Skipping {json_path.name}: missing category_name")
                continue

            category_id, created = _get_or_create_category(session, category_table, category_name, payload)
            if created:
                inserted_categories += 1
            else:
                updated_categories += 1

            category_attributes = payload.get('attributes') or []

            for item in payload.get('items', []):
                result = _upsert_global_ingredient_item(
                    session=session,
                    global_item_table=global_item_table,
                    alias_table=alias_table,
                    alias_column_key=alias_column_key,
                    category_id=category_id,
                    category_name=category_name,
                    category_attributes=category_attributes,
                    item_payload=item,
                    source_name=json_path.name,
                )

                if result is None:
                    continue

                created_item, alias_count = result
                if created_item:
                    inserted_items += 1
                else:
                    updated_items += 1
                inserted_aliases += alias_count

        session.flush()

        print(
            "   ✅ Global ingredient seeding complete "
            f"(categories: +{inserted_categories}/~{inserted_categories + updated_categories}, "
            f"items: +{inserted_items}/~{inserted_items + updated_items}, "
            f"aliases added: {inserted_aliases})"
        )
    finally:
        session.close()


def _ingredient_seed_dir() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "app" / "seeders" / "globallist" / "ingredients" / "categories"


def _load_seed_payload(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        print(f"   ⚠️ Could not parse {path.name}: {exc}")
        return None


def _get_or_create_category(session, category_table, category_name: str, payload: dict):
    stmt = (
        select(category_table.c.id, category_table.c.description, category_table.c.default_density)
        .where(category_table.c.name == category_name)
        .where(category_table.c.organization_id.is_(None))
    )
    existing = session.execute(stmt).first()

    now = datetime.utcnow()

    default_density = _parse_float(payload.get('default_density'))
    description = payload.get('description')

    if existing:
        category_id, existing_description, existing_density = existing
        updates = {}
        if description is not None and description != existing_description:
            updates['description'] = description
        if default_density is not None and default_density != existing_density:
            updates['default_density'] = default_density
        if updates:
            updates['updated_at'] = now
            session.execute(
                category_table.update()
                .where(category_table.c.id == category_id)
                .values(**updates)
            )
        return category_id, False

    insert_values = {
        'name': category_name,
        'description': description,
        'color': None,
        'default_density': default_density,
        'is_active': True,
        'is_global_category': True,
        'organization_id': None,
        'created_by': None,
        'created_at': now,
        'updated_at': now,
    }

    session.execute(category_table.insert().values(**insert_values))

    category_id = session.execute(
        select(category_table.c.id)
        .where(category_table.c.name == category_name)
        .where(category_table.c.organization_id.is_(None))
    ).scalar_one()

    return category_id, True


def _upsert_global_ingredient_item(
    session,
    global_item_table,
    alias_table,
    alias_column_key: str,
    category_id: int,
    category_name: str,
    category_attributes,
    item_payload: dict,
    source_name: str,
):
    item_name = (item_payload.get('name') or '').strip()
    if not item_name:
        return None

    metadata_supported = 'metadata_json' in global_item_table.c

    select_columns = [global_item_table.c.id]
    if metadata_supported:
        select_columns.append(global_item_table.c.metadata_json)

    stmt = select(*select_columns).where(
        global_item_table.c.name == item_name,
        global_item_table.c.item_type == 'ingredient'
    )
    existing = session.execute(stmt).first()

    now = datetime.utcnow()

    aliases = _normalize_aliases(
        item_payload.get('aliases'),
        item_payload.get('aka_names'),
        item_payload.get('aka')
    )

    density = _parse_float(item_payload.get('density', item_payload.get('density_g_ml')))
    moisture = _parse_float(item_payload.get('moisture_content_percent'))
    shelf_life = _parse_int(
        item_payload.get('recommended_shelf_life_days', item_payload.get('shelf_life_days'))
    )

    ph_value_numeric, ph_metadata = _process_ph_value(item_payload.get('ph_value'))

    certifications = _clean_list(item_payload.get('certifications'))

    metadata_payload = {
        'seed_source': source_name,
        'seed_category': category_name,
    }
    if category_attributes:
        metadata_payload['category_attributes'] = category_attributes
    if ph_metadata:
        metadata_payload.update(ph_metadata)

    extra_keys = set(item_payload.keys()) - {
        'name',
        'aliases',
        'aka_names',
        'aka',
        'density',
        'density_g_ml',
        'default_unit',
        'recommended_shelf_life_days',
        'shelf_life_days',
        'recommended_usage_rate',
        'recommended_fragrance_load_pct',
        'is_active_ingredient',
        'is_active',
        'default_is_perishable',
        'perishable',
        'inci_name',
        'certifications',
        'saponification_value',
        'iodine_value',
        'melting_point_c',
        'flash_point_c',
        'ph_value',
        'moisture_content_percent',
        'comedogenic_rating',
        'fatty_acid_profile',
        'protein_content_pct',
        'brewing_color_srm',
        'brewing_potential_sg',
        'brewing_diastatic_power_lintner',
    }
    if extra_keys:
        metadata_payload['extra_item_fields'] = {k: item_payload[k] for k in extra_keys}

    base_values = {
        'name': item_name,
        'item_type': 'ingredient',
        alias_column_key: aliases if aliases else None,
        'density': density,
        'default_unit': item_payload.get('default_unit'),
        'ingredient_category_id': category_id,
        'default_is_perishable': _parse_bool(
            item_payload.get('default_is_perishable', item_payload.get('perishable'))
        ),
        'recommended_shelf_life_days': shelf_life,
        'recommended_usage_rate': item_payload.get('recommended_usage_rate'),
        'recommended_fragrance_load_pct': item_payload.get('recommended_fragrance_load_pct'),
        'is_active_ingredient': _parse_bool(
            item_payload.get('is_active_ingredient', item_payload.get('is_active'))
        ),
        'inci_name': item_payload.get('inci_name'),
        'certifications': certifications,
        'saponification_value': _parse_float(item_payload.get('saponification_value')),
        'iodine_value': _parse_float(item_payload.get('iodine_value')),
        'melting_point_c': _parse_float(item_payload.get('melting_point_c')),
        'flash_point_c': _parse_float(item_payload.get('flash_point_c')),
        'ph_value': ph_value_numeric,
        'moisture_content_percent': moisture,
        'comedogenic_rating': _parse_int(item_payload.get('comedogenic_rating')),
        'fatty_acid_profile': item_payload.get('fatty_acid_profile'),
        'protein_content_pct': _parse_float(item_payload.get('protein_content_pct')),
        'brewing_color_srm': _parse_float(item_payload.get('brewing_color_srm')),
        'brewing_potential_sg': _parse_float(item_payload.get('brewing_potential_sg')),
        'brewing_diastatic_power_lintner': _parse_float(item_payload.get('brewing_diastatic_power_lintner')),
        'is_archived': False,
        'updated_at': now,
    }

    if metadata_supported:
        base_values['metadata_json'] = metadata_payload

    base_values = _filter_values_for_table(global_item_table, base_values)

    if existing:
        if metadata_supported:
            item_id, metadata_existing = existing
        else:
            item_id = existing[0]
            metadata_existing = {}
        update_values = dict(base_values)
        if metadata_supported:
            merged_metadata = metadata_existing or {}
            if metadata_payload:
                merged_metadata.update(metadata_payload)
            update_values['metadata_json'] = merged_metadata

        session.execute(
            global_item_table.update()
            .where(global_item_table.c.id == item_id)
            .values(**update_values)
        )
        alias_insert_count = _ensure_alias_rows(session, alias_table, item_id, aliases)
        return False, alias_insert_count

    insert_values = dict(base_values)
    insert_values['created_at'] = now
    insert_values = _filter_values_for_table(global_item_table, insert_values)

    session.execute(global_item_table.insert().values(**insert_values))

    item_id = session.execute(
        select(global_item_table.c.id)
        .where(global_item_table.c.name == item_name)
        .where(global_item_table.c.item_type == 'ingredient')
    ).scalar_one()

    alias_insert_count = _ensure_alias_rows(session, alias_table, item_id, aliases)

    return True, alias_insert_count


def _ensure_alias_rows(session, alias_table, item_id: int, aliases):
    if not aliases:
        return 0

    inserted = 0
    for alias in aliases:
        if not alias:
            continue
        exists = session.execute(
            select(alias_table.c.id).where(
                alias_table.c.global_item_id == item_id,
                alias_table.c.alias == alias
            )
        ).first()
        if exists:
            continue
        session.execute(alias_table.insert().values(global_item_id=item_id, alias=alias))
        inserted += 1
    return inserted


def _normalize_aliases(*alias_sources):
    aliases = []
    for src in alias_sources:
        if not src:
            continue
        if isinstance(src, str):
            candidate = src.strip()
            if candidate:
                aliases.append(candidate)
        elif isinstance(src, (list, tuple, set)):
            for item in src:
                if not item:
                    continue
                candidate = str(item).strip()
                if candidate:
                    aliases.append(candidate)
    # Remove duplicates while preserving order
    seen = set()
    unique_aliases = []
    for alias in aliases:
        lower_alias = alias.lower()
        if lower_alias in seen:
            continue
        seen.add(lower_alias)
        unique_aliases.append(alias)
    return unique_aliases


def _filter_values_for_table(table, values: dict) -> dict:
    return {key: value for key, value in values.items() if key in table.c}


def _parse_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).strip()
        if not cleaned:
            return None
        # Remove trailing unit annotations, keep numeric part
        cleaned = cleaned.replace(',', '')
        match = re.search(r'-?\d+(?:\.\d+)?', cleaned)
        if match:
            return float(match.group(0))
    except (ValueError, TypeError):
        return None
    return None


def _parse_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        cleaned = str(value).strip()
        if not cleaned:
            return None
        match = re.search(r'-?\d+', cleaned)
        if match:
            return int(match.group(0))
    except (ValueError, TypeError):
        return None
    return None


def _parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return default


def _clean_list(value):
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    return []


PH_REGEX = re.compile(r'-?\d+(?:\.\d+)?')


def _process_ph_value(value):
    if value is None:
        return None, {}
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric, {
            'ph_display': str(value),
            'ph_min': numeric,
            'ph_max': numeric,
        }

    value_str = str(value).strip()
    if not value_str:
        return None, {}

    matches = [float(m) for m in PH_REGEX.findall(value_str)]
    metadata = {'ph_display': value_str}

    if matches:
        metadata['ph_min'] = min(matches)
        metadata['ph_max'] = max(matches)
        metadata['ph_values'] = matches
        # Use the midpoint of min/max as representative numeric value
        representative = (metadata['ph_min'] + metadata['ph_max']) / 2 if len(matches) >= 2 else matches[0]
        return representative, metadata

    return None, metadata

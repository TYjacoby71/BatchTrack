from app.extensions import db
from app.models.unit import Unit


COUNT_UNITS = [
    ("Piece", "pc"),
    ("Bar", None),
    ("Slice", None),
    ("Cookie", None),
    ("Bottle", None),
    ("Jar", None),
    ("Tablet", None),
    ("Capsule", None),
    ("Bomb", None),
    ("Loaf", None),
    ("Cupcake", None),
    ("Muffin", None),
]


def seed_count_units():
    for name, symbol in COUNT_UNITS:
        existing = Unit.query.filter_by(name=name, is_custom=False).first()
        if not existing:
            unit = Unit(
                name=name,
                symbol=symbol,
                unit_type='count',
                conversion_factor=1.0,
                base_unit='Piece',
                is_active=True,
                is_custom=False,
                is_mapped=True,
                organization_id=None
            )
            db.session.add(unit)
    db.session.commit()


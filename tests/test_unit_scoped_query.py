from uuid import uuid4

from flask_login import login_user

from app.models import Organization, Unit


def test_unit_scoped_includes_standard_and_current_org_custom_units(
    app, db_session, test_user
):
    other_org = Organization(name=f"Other Org {uuid4().hex[:8]}")
    db_session.add(other_org)
    db_session.flush()

    standard_name = f"std_{uuid4().hex[:8]}"
    own_custom_name = f"own_{uuid4().hex[:8]}"
    other_custom_name = f"other_{uuid4().hex[:8]}"

    standard_unit = Unit(
        name=standard_name,
        symbol=standard_name,
        unit_type="count",
        conversion_factor=1.0,
        base_unit="count",
        is_active=True,
        is_custom=False,
    )
    own_custom_unit = Unit(
        name=own_custom_name,
        symbol=own_custom_name,
        unit_type="count",
        conversion_factor=1.0,
        base_unit="count",
        is_active=True,
        is_custom=True,
        organization_id=test_user.organization_id,
        created_by=test_user.id,
    )
    other_custom_unit = Unit(
        name=other_custom_name,
        symbol=other_custom_name,
        unit_type="count",
        conversion_factor=1.0,
        base_unit="count",
        is_active=True,
        is_custom=True,
        organization_id=other_org.id,
        created_by=test_user.id,
    )
    db_session.add_all([standard_unit, own_custom_unit, other_custom_unit])
    db_session.commit()

    with app.test_request_context("/inventory/"):
        login_user(test_user)
        visible_units = Unit.scoped().filter(
            Unit.name.in_([standard_name, own_custom_name, other_custom_name])
        )
        visible_names = {unit.name for unit in visible_units.all()}

    assert standard_name in visible_names
    assert own_custom_name in visible_names
    assert other_custom_name not in visible_names

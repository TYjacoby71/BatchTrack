"""Conversion route service boundary.

Synopsis:
Encapsulates conversion-route persistence and scoped data access so
`app/blueprints/conversion/routes.py` remains transport-focused.

Glossary:
- Cross-type mapping: Custom conversion between unlike unit types (for example count->volume).
- Same-type mapping: Conversion between units with the same unit_type where base factor is derived.
"""

from __future__ import annotations

from app.extensions import db
from app.models import CustomUnitMapping, InventoryItem, Unit


class ConversionRouteService:
    """Data/session helpers for conversion blueprint routes."""

    BASE_UNITS = {
        "weight": "gram",
        "volume": "ml",
        "count": "count",
        "length": "cm",
        "area": "sqcm",
    }

    @staticmethod
    def get_unit_by_id(*, unit_id: int) -> Unit | None:
        return db.session.get(Unit, int(unit_id))

    @staticmethod
    def find_existing_unit_for_scope(
        *,
        name: str,
        user_type: str | None,
        user_organization_id: int | None,
        selected_org_id: int | None,
    ) -> Unit | None:
        if user_type == "developer":
            if selected_org_id:
                return Unit.query.filter_by(
                    name=name,
                    organization_id=selected_org_id,
                ).first()
            return Unit.query.filter_by(name=name).first()

        return Unit.query.filter(
            Unit.name == name,
            ((Unit.is_custom) & (Unit.organization_id == user_organization_id))
            | (Unit.is_custom.is_(False)),
        ).first()

    @staticmethod
    def delete_unit_and_mappings(*, unit: Unit) -> None:
        mapping_query = CustomUnitMapping.scoped().filter(
            (CustomUnitMapping.from_unit == unit.name)
            | (CustomUnitMapping.to_unit == unit.name)
        )
        if unit.organization_id:
            mapping_query = mapping_query.filter_by(organization_id=unit.organization_id)
        mapping_query.delete()
        db.session.delete(unit)
        db.session.commit()

    @staticmethod
    def create_custom_unit(
        *,
        name: str,
        symbol: str,
        unit_type: str,
        created_by: int | None,
        organization_id: int | None,
    ) -> Unit:
        new_unit = Unit(
            name=name,
            symbol=symbol,
            unit_type=unit_type,
            base_unit=ConversionRouteService.BASE_UNITS.get(unit_type, "count"),
            conversion_factor=1.0,
            is_custom=True,
            is_mapped=False,
            created_by=created_by,
            organization_id=organization_id,
        )
        db.session.add(new_unit)
        db.session.commit()
        return new_unit

    @staticmethod
    def find_unit_by_name(*, name: str) -> Unit | None:
        return Unit.query.filter_by(name=name).first()

    @staticmethod
    def find_mapping_by_from_unit(*, from_unit: str) -> CustomUnitMapping | None:
        return CustomUnitMapping.scoped().filter_by(from_unit=from_unit).first()

    @staticmethod
    def create_cross_type_mapping(
        *,
        custom_unit: Unit,
        comparable_unit: Unit,
        conversion_factor: float,
        created_by: int | None,
        organization_id: int | None,
    ) -> None:
        mapping = CustomUnitMapping(
            from_unit=custom_unit.name,
            to_unit=comparable_unit.name,
            conversion_factor=conversion_factor,
            notes=f"1 {custom_unit.name} = {conversion_factor} {comparable_unit.name} (cross-type)",
            created_by=created_by,
            organization_id=organization_id,
        )
        db.session.add(mapping)
        custom_unit.is_mapped = True
        db.session.commit()

    @staticmethod
    def create_same_type_mapping(
        *,
        custom_unit: Unit,
        comparable_unit: Unit,
        conversion_factor: float,
        created_by: int | None,
        organization_id: int | None,
    ) -> None:
        mapping = CustomUnitMapping(
            from_unit=custom_unit.name,
            to_unit=comparable_unit.name,
            conversion_factor=conversion_factor,
            notes=f"1 {custom_unit.name} = {conversion_factor} {comparable_unit.name}",
            created_by=created_by,
            organization_id=organization_id,
        )
        db.session.add(mapping)
        custom_unit.is_mapped = True
        custom_unit.conversion_factor = (
            conversion_factor * comparable_unit.conversion_factor
        )
        db.session.commit()

    @staticmethod
    def list_mappings_for_manage(
        *,
        is_authenticated: bool,
        user_type: str | None,
        user_organization_id: int | None,
        selected_org_id: int | None,
    ) -> list[CustomUnitMapping]:
        if not is_authenticated:
            return []

        if user_type == "developer":
            if selected_org_id:
                return (
                    CustomUnitMapping.scoped()
                    .filter_by(organization_id=selected_org_id)
                    .all()
                )
            return CustomUnitMapping.scoped().all()

        return (
            CustomUnitMapping.scoped()
            .filter_by(organization_id=user_organization_id)
            .all()
        )

    @staticmethod
    def get_mapping_for_delete(
        *,
        mapping_id: int,
        user_type: str | None,
        user_organization_id: int | None,
        selected_org_id: int | None,
    ) -> CustomUnitMapping:
        if user_type == "developer":
            if selected_org_id:
                return (
                    CustomUnitMapping.scoped()
                    .filter_by(id=mapping_id, organization_id=selected_org_id)
                    .first_or_404()
                )
            return CustomUnitMapping.scoped().filter_by(id=mapping_id).first_or_404()

        return (
            CustomUnitMapping.scoped()
            .filter_by(id=mapping_id, organization_id=user_organization_id)
            .first_or_404()
        )

    @staticmethod
    def delete_mapping(*, mapping: CustomUnitMapping) -> None:
        db.session.delete(mapping)
        db.session.commit()

    @staticmethod
    def get_inventory_item_by_id(*, item_id: int) -> InventoryItem | None:
        return db.session.get(InventoryItem, item_id)

    @staticmethod
    def create_api_mapping(
        *,
        from_unit: str,
        to_unit: str,
        multiplier: float,
        organization_id: int | None,
    ) -> None:
        mapping = CustomUnitMapping(
            from_unit=from_unit,
            to_unit=to_unit,
            conversion_factor=float(multiplier),
            organization_id=organization_id,
        )
        db.session.add(mapping)
        db.session.commit()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()

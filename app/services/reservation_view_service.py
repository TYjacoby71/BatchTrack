"""Reservation view/query service boundary.

Synopsis:
Encapsulates reservation list/detail queries and lot-lookup enrichment so
reservation routes avoid direct persistence access.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, desc

from app.extensions import db
from app.models import Reservation, UnifiedInventoryHistory
from app.models.inventory_lot import InventoryLot
from app.models.product import ProductSKU


class ReservationViewService:
    """Service helpers for reservation page/list/detail endpoints."""

    @staticmethod
    def list_reservations(
        *,
        organization_id: int | None,
        status_filter: str,
        order_id_filter: str,
    ) -> list[Reservation]:
        query = Reservation.scoped()
        if status_filter != "all":
            query = query.filter(Reservation.status == status_filter)
        if order_id_filter:
            query = query.filter(Reservation.order_id.contains(order_id_filter))
        if organization_id:
            query = query.filter(Reservation.organization_id == organization_id)
        return query.order_by(desc(Reservation.created_at)).limit(100).all()

    @staticmethod
    def _resolve_lot_number(source_fifo_id: int | None) -> str | None:
        if not source_fifo_id:
            return None
        lot = db.session.get(InventoryLot, source_fifo_id)
        if lot and getattr(lot, "lot_number", None):
            return lot.lot_number
        history_entry = db.session.get(UnifiedInventoryHistory, source_fifo_id)
        if history_entry and getattr(history_entry, "affected_lot", None):
            return history_entry.affected_lot.lot_number
        return None

    @classmethod
    def build_reservation_groups(
        cls,
        *,
        reservations: list[Reservation],
    ) -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        for reservation in reservations:
            if not reservation.product_item:
                continue
            sku_name = reservation.product_item.name
            groups.setdefault(sku_name, [])

            batch_label = None
            if reservation.source_batch_id and reservation.source_batch:
                batch_label = reservation.source_batch.label_code

            lot_number = cls._resolve_lot_number(reservation.source_fifo_id)
            groups[sku_name].append(
                {
                    "order_id": reservation.order_id,
                    "quantity": reservation.quantity,
                    "unit": reservation.unit,
                    "batch_id": reservation.source_batch_id,
                    "batch_label": batch_label,
                    "lot_number": lot_number,
                    "source_batch_id": reservation.source_batch_id,
                    "created_at": reservation.created_at,
                    "expires_at": reservation.expires_at,
                    "sale_price": reservation.sale_price,
                    "source": reservation.source,
                    "notes": reservation.notes,
                    "status": reservation.status,
                }
            )
        return groups

    @staticmethod
    def build_stats(*, organization_id: int | None) -> dict[str, int]:
        scoped = Reservation.scoped()
        return {
            "total_active": scoped.filter(
                and_(
                    Reservation.status == "active",
                    Reservation.organization_id == organization_id,
                )
            ).count(),
            "total_expired": scoped.filter(
                and_(
                    Reservation.status == "expired",
                    Reservation.organization_id == organization_id,
                )
            ).count(),
            "total_converted": scoped.filter(
                and_(
                    Reservation.status == "converted_to_sale",
                    Reservation.organization_id == organization_id,
                )
            ).count(),
        }

    @staticmethod
    def resolve_item_id_from_sku(
        *,
        sku_code: str,
        organization_id: int | None,
    ) -> int | None:
        sku = ProductSKU.scoped().filter_by(
            sku_code=sku_code,
            organization_id=organization_id,
            is_active=True,
        ).first()
        return sku.inventory_item_id if sku else None

    @staticmethod
    def list_item_reservations(
        *,
        item_id: int,
        organization_id: int | None,
    ) -> list[Reservation]:
        return (
            Reservation.scoped()
            .filter(
                and_(
                    Reservation.product_item_id == item_id,
                    Reservation.organization_id == organization_id,
                )
            )
            .order_by(desc(Reservation.created_at))
            .all()
        )

    @staticmethod
    def serialize_item_reservations(reservations: list[Reservation]) -> list[dict]:
        payload = []
        for reservation in reservations:
            payload.append(
                {
                    "id": reservation.id,
                    "order_id": reservation.order_id,
                    "quantity": reservation.quantity,
                    "unit": reservation.unit,
                    "status": reservation.status,
                    "source": reservation.source,
                    "created_at": (
                        reservation.created_at.isoformat()
                        if reservation.created_at
                        else None
                    ),
                    "expires_at": (
                        reservation.expires_at.isoformat()
                        if reservation.expires_at
                        else None
                    ),
                    "sale_price": reservation.sale_price,
                    "notes": reservation.notes,
                }
            )
        return payload

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)

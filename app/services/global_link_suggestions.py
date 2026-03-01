import logging
from typing import List, Optional, Tuple

from flask import current_app
from sqlalchemy import func

from ..models import GlobalItem, InventoryItem, Unit, db
from .density_assignment_service import DensityAssignmentService

logger = logging.getLogger(__name__)



class GlobalLinkSuggestionService:
    """Builds suggestions to link org-owned inventory items to curated GlobalItems."""

    @staticmethod
    def is_pair_compatible(
        global_unit_name: Optional[str], item_unit_name: Optional[str]
    ) -> bool:
        """Return True if unit classes match or are convertible (weight↔volume). Count↔(weight|volume) is disallowed."""
        if not global_unit_name or not item_unit_name:
            return False
        try:
            gunit: Optional[Unit] = (
                db.session.query(Unit).filter_by(name=global_unit_name).first()
            )
            iunit: Optional[Unit] = (
                db.session.query(Unit).filter_by(name=item_unit_name).first()
            )
            if not gunit or not iunit:
                return False
            gtype = (gunit.unit_type or "").lower()
            itype = (iunit.unit_type or "").lower()
            if gtype == itype:
                return True
            # Allow density-based convertibility between weight and volume
            if {gtype, itype} == {"weight", "volume"}:
                return True
            # Otherwise, not compatible (e.g., count vs volume/weight)
            return False
        except Exception:
            logger.warning("Suppressed exception fallback at app/services/global_link_suggestions.py:38", exc_info=True)
            return False

    @staticmethod
    def _name_match_confidence(item_name: str, global_item: GlobalItem) -> float:
        """Compute confidence based on exact/aka/similarity."""
        iname = (item_name or "").strip().lower()
        gname = (global_item.name or "").strip().lower()
        if not iname or not gname:
            return 0.0
        # Exact or case-insensitive match
        if iname == gname:
            return 1.0
        # Alias match
        try:
            aka = global_item.aliases or []
            if any((a or "").strip().lower() == iname for a in aka):
                return 0.98
        except Exception:
            logger.warning("Suppressed exception fallback at app/services/global_link_suggestions.py:56", exc_info=True)
            pass
        # Fuzzy
        try:
            return DensityAssignmentService._similarity_score(iname, gname)
        except Exception:
            logger.warning("Suppressed exception fallback at app/services/global_link_suggestions.py:61", exc_info=True)
            return 0.0

    @staticmethod
    def find_candidates_for_global(
        global_item_id: int, organization_id: int, threshold: float = 0.85
    ) -> List[InventoryItem]:
        gi: Optional[GlobalItem] = db.session.get(GlobalItem, int(global_item_id))
        if not gi or gi.item_type != "ingredient":
            return []

        # Base query: org-owned, unlinked, not archived, ingredient type
        query = db.session.query(InventoryItem).filter(
            InventoryItem.organization_id == organization_id,
            InventoryItem.global_item_id.is_(None),
            not InventoryItem.is_archived,
            InventoryItem.type == "ingredient",
        )

        candidates: List[Tuple[InventoryItem, float]] = []
        for item in query.limit(500).all():
            # Require known global unit and pair compatibility
            if (
                not gi.default_unit
                or not GlobalLinkSuggestionService.is_pair_compatible(
                    gi.default_unit, item.unit
                )
            ):
                continue
            conf = GlobalLinkSuggestionService._name_match_confidence(item.name, gi)
            if conf >= threshold:
                candidates.append((item, conf))

        # Sort by confidence desc, then name len asc for nicer UX
        candidates.sort(key=lambda t: (-t[1], len(t[0].name or "")))
        return [c[0] for c in candidates]

    @staticmethod
    def get_first_suggestion_for_org(
        organization_id: int, threshold: float = 0.85
    ) -> Tuple[Optional[GlobalItem], List[InventoryItem]]:
        """Return the first GlobalItem with at least one candidate for this org (pre-checked list)."""
        try:
            global_items = (
                db.session.query(GlobalItem)
                .filter(
                    not GlobalItem.is_archived, GlobalItem.item_type == "ingredient"
                )
                .order_by(func.length(GlobalItem.name).asc())
                .limit(200)
                .all()
            )
        except Exception as e:
            current_app.logger.warning(
                f"GlobalLinkSuggestionService: failed to load global items: {e}"
            )
            return None, []

        for gi in global_items:
            items = GlobalLinkSuggestionService.find_candidates_for_global(
                gi.id, organization_id, threshold
            )
            if items:
                return gi, items

        return None, []

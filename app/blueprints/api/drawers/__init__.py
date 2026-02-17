from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from app.utils.permissions import require_permission


class DrawerRegistry:
    """Simple in-memory registry for drawer actions and cadence checks."""

    def __init__(self) -> None:
        self._actions: Dict[str, Dict] = {}
        self._cadence_checks: Dict[str, Callable[[], Optional[Dict]]] = {}

    @property
    def actions(self) -> Dict[str, Dict]:
        return self._actions

    def register_action(self, action_id: str, **metadata) -> None:
        if action_id in self._actions:
            raise ValueError(f"Drawer action '{action_id}' is already registered")
        self._actions[action_id] = metadata

    def register_cadence_check(
        self, check_id: str
    ) -> Callable[[Callable[[], Optional[Dict]]], Callable[[], Optional[Dict]]]:
        def decorator(func: Callable[[], Optional[Dict]]):
            self._cadence_checks[check_id] = func
            return func

        return decorator

    def run_checks(
        self,
        include: Optional[Sequence[str]] = None,
        *,
        first_only: bool = True,
    ) -> List[Dict]:
        include_set = {value for value in include} if include else None
        payloads: List[Dict] = []

        for key, func in self._cadence_checks.items():
            if include_set and key not in include_set:
                continue

            try:
                payload = func()
            except Exception as exc:  # pragma: no cover - defensive logging
                current_app.logger.warning(
                    "Drawer cadence check '%s' failed: %s", key, exc
                )
                continue

            if payload:
                payload.setdefault("source", key)
                payloads.append(payload)

                if first_only:
                    break

        return payloads


drawer_registry = DrawerRegistry()
drawers_bp = Blueprint("drawers", __name__, url_prefix="/api/drawers")


def register_drawer_action(action_id: str, **metadata) -> None:
    drawer_registry.register_action(action_id, **metadata)


def register_cadence_check(check_id: str):
    return drawer_registry.register_cadence_check(check_id)


@drawers_bp.route("/check", methods=["GET"])
@login_required
@require_permission("dashboard.view")
def run_drawer_cadence_checks():
    """Execute registered cadence checks and return the next drawer payload, if any."""
    include_param = request.args.get("include")
    include = (
        [value.strip() for value in include_param.split(",") if value.strip()]
        if include_param
        else None
    )
    first_only = request.args.get("all", "false").lower() not in {"1", "true", "yes"}

    payloads = drawer_registry.run_checks(include=include, first_only=first_only)
    response = {
        "success": True,
        "drawer_payloads": payloads,
        "count": len(payloads),
        "needs_drawer": bool(payloads),
        "drawer_payload": payloads[0] if payloads else None,
    }
    return jsonify(response)


# Import action modules for side effects (route registration + registry hooks)
from . import drawer_actions  # noqa: E402,F401

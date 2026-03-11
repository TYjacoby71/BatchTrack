"""Signup info partial management and rendering helpers.

Synopsis:
Persist and resolve repository-backed HTML partials that render below signup
pricing cards, including manual or 50/50 split assignment modes.

Glossary:
- Partial: HTML snippet displayed below signup pricing cards.
- Assignment: Mapping from tier_id to the partial selection strategy.
- Split 50/50: Sticky variant chooser between primary and secondary partials.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app, session

from app.services.ai import GoogleAIClient, GoogleAIClientError
from app.utils.json_store import read_json_file, write_json_file

_VALID_STATUSES = {"draft", "active", "archived"}
_VALID_ASSIGNMENT_MODES = {"manual", "split_50_50"}
_SCRIPT_TAG_RE = re.compile(
    r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", flags=re.IGNORECASE
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", flags=re.DOTALL)


class SignupInfoPartialServiceError(RuntimeError):
    """Raised when signup info partial operations fail validation."""


class SignupInfoPartialService:
    """Repository-backed storage and selection logic for signup info partials."""

    _SESSION_BUCKET_KEY = "signup_info_partial_bucket_seed"
    _CONTENT_RELATIVE_PATH = Path("marketing/content/signup_info_partials.json")

    @classmethod
    def load_store(cls) -> dict[str, Any]:
        """Load and normalize the partial store from repository JSON."""
        content_path = cls._content_path()
        raw = read_json_file(content_path, default=None)
        normalized = cls._normalize_store(raw if isinstance(raw, dict) else {})
        if not content_path.exists():
            write_json_file(content_path, normalized)
        return normalized

    @classmethod
    def save_store(cls, store: dict[str, Any]) -> dict[str, Any]:
        """Normalize and persist the full partial store payload."""
        normalized = cls._normalize_store(store or {})
        write_json_file(cls._content_path(), normalized)
        return normalized

    @classmethod
    def list_partials(cls, *, include_archived: bool = True) -> list[dict[str, Any]]:
        """Return normalized partials sorted by updated timestamp descending."""
        store = cls.load_store()
        partials = list(store.get("partials") or [])
        if not include_archived:
            partials = [
                partial for partial in partials if partial.get("status") != "archived"
            ]
        partials.sort(
            key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""),
            reverse=True,
        )
        return partials

    @classmethod
    def list_selectable_partials(cls) -> list[dict[str, Any]]:
        """Return partials valid for assignment selects (non-archived)."""
        partials = cls.list_partials(include_archived=False)
        return [
            partial
            for partial in partials
            if str(partial.get("status") or "draft") in {"draft", "active"}
        ]

    @classmethod
    def get_partial(cls, partial_id: str) -> dict[str, Any] | None:
        """Return one partial by id."""
        if not partial_id:
            return None
        for partial in cls.load_store().get("partials") or []:
            if str(partial.get("id") or "") == str(partial_id):
                return partial
        return None

    @classmethod
    def create_partial(
        cls,
        *,
        name: str,
        html_content: str,
        status: str = "draft",
        parent_partial_id: str | None = None,
        lineage_key: str | None = None,
        version: int | None = None,
        source_prompt: str | None = None,
        ai_model: str | None = None,
    ) -> dict[str, Any]:
        """Create and persist a new partial."""
        clean_name = str(name or "").strip() or "Signup Info Partial"
        clean_status = cls._normalize_status(status)
        html_value = cls._sanitize_html(html_content)
        store = cls.load_store()
        partials = list(store.get("partials") or [])
        partial_id = cls._next_partial_id(clean_name, existing=partials)
        now_iso = cls._utc_now_iso()
        lineage_value = str(lineage_key or parent_partial_id or partial_id).strip()
        version_value = int(version or 1)

        created = {
            "id": partial_id,
            "name": clean_name,
            "slug": cls._slugify(clean_name),
            "status": clean_status,
            "version": max(1, version_value),
            "lineage_key": lineage_value,
            "parent_partial_id": str(parent_partial_id or "").strip() or None,
            "html_content": html_value,
            "source_prompt": str(source_prompt or "").strip() or None,
            "ai_model": str(ai_model or "").strip() or None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        partials.append(created)
        store["partials"] = partials
        cls.save_store(store)
        return created

    @classmethod
    def update_partial(
        cls,
        *,
        partial_id: str,
        name: str | None = None,
        status: str | None = None,
        html_content: str | None = None,
    ) -> dict[str, Any]:
        """Update mutable fields for one partial."""
        if not partial_id:
            raise SignupInfoPartialServiceError("Partial id is required.")
        store = cls.load_store()
        partials = list(store.get("partials") or [])
        target = next(
            (
                partial
                for partial in partials
                if str(partial.get("id") or "") == str(partial_id)
            ),
            None,
        )
        if not target:
            raise SignupInfoPartialServiceError("Partial not found.")

        if name is not None:
            clean_name = str(name).strip() or target.get("name") or "Signup Info Partial"
            target["name"] = clean_name
            target["slug"] = cls._slugify(clean_name)
        if status is not None:
            target["status"] = cls._normalize_status(status)
        if html_content is not None:
            target["html_content"] = cls._sanitize_html(html_content)
        target["updated_at"] = cls._utc_now_iso()

        store["partials"] = partials
        cls.save_store(store)
        return target

    @classmethod
    def clone_partial(
        cls,
        *,
        partial_id: str,
        as_name: str | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        """Create a new version draft from an existing partial."""
        base = cls.get_partial(partial_id)
        if not base:
            raise SignupInfoPartialServiceError("Base partial not found.")
        lineage_key = str(base.get("lineage_key") or base.get("id") or "").strip() or str(
            base.get("id") or ""
        )
        next_version = cls._next_lineage_version(lineage_key=lineage_key)
        clone_name = (
            str(as_name).strip()
            if as_name is not None and str(as_name).strip()
            else f"{base.get('name') or 'Signup Info Partial'} v{next_version}"
        )
        return cls.create_partial(
            name=clone_name,
            html_content=str(base.get("html_content") or ""),
            status=status,
            parent_partial_id=str(base.get("id") or ""),
            lineage_key=lineage_key,
            version=next_version,
            source_prompt=str(base.get("source_prompt") or "") or None,
            ai_model=str(base.get("ai_model") or "") or None,
        )

    @classmethod
    def create_ai_draft(
        cls,
        *,
        partial_id: str,
        prompt: str,
        tier_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate and persist an AI-authored draft from a base partial."""
        base = cls.get_partial(partial_id)
        if not base:
            raise SignupInfoPartialServiceError("Base partial not found.")
        clean_prompt = str(prompt or "").strip()
        if not clean_prompt:
            raise SignupInfoPartialServiceError("Prompt is required.")

        client = GoogleAIClient.from_app()
        model_name = (
            current_app.config.get("GOOGLE_AI_BATCHBOT_MODEL")
            or current_app.config.get("GOOGLE_AI_DEFAULT_MODEL")
            or "gemini-1.5-flash"
        )
        ai_payload = cls._generate_ai_payload(
            client=client,
            model_name=model_name,
            base_partial=base,
            prompt=clean_prompt,
            tier_names=tier_names or [],
        )
        lineage_key = str(base.get("lineage_key") or base.get("id") or "").strip() or str(
            base.get("id") or ""
        )
        next_version = cls._next_lineage_version(lineage_key=lineage_key)
        return cls.create_partial(
            name=ai_payload.get("name")
            or f"{base.get('name') or 'Signup Info Partial'} v{next_version}",
            html_content=ai_payload.get("html_content") or str(base.get("html_content") or ""),
            status="draft",
            parent_partial_id=str(base.get("id") or ""),
            lineage_key=lineage_key,
            version=next_version,
            source_prompt=clean_prompt,
            ai_model=model_name,
        )

    @classmethod
    def apply_ai_edit(
        cls,
        *,
        partial_id: str,
        prompt: str,
        tier_names: list[str] | None = None,
        allow_name_update: bool = False,
    ) -> dict[str, Any]:
        """Apply an AI rewrite directly to an existing partial."""
        base = cls.get_partial(partial_id)
        if not base:
            raise SignupInfoPartialServiceError("Draft partial not found.")
        clean_prompt = str(prompt or "").strip()
        if not clean_prompt:
            raise SignupInfoPartialServiceError("Prompt is required.")

        client = GoogleAIClient.from_app()
        model_name = (
            current_app.config.get("GOOGLE_AI_BATCHBOT_MODEL")
            or current_app.config.get("GOOGLE_AI_DEFAULT_MODEL")
            or "gemini-1.5-flash"
        )
        ai_payload = cls._generate_ai_payload(
            client=client,
            model_name=model_name,
            base_partial=base,
            prompt=clean_prompt,
            tier_names=tier_names or [],
        )
        updated = cls.update_partial(
            partial_id=str(partial_id),
            name=ai_payload.get("name") if allow_name_update else None,
            html_content=ai_payload.get("html_content") or str(base.get("html_content") or ""),
        )
        updated["source_prompt"] = clean_prompt
        updated["ai_model"] = model_name
        updated["updated_at"] = cls._utc_now_iso()

        store = cls.load_store()
        partials = list(store.get("partials") or [])
        for partial in partials:
            if str(partial.get("id") or "") == str(partial_id):
                partial.update(
                    {
                        "source_prompt": updated["source_prompt"],
                        "ai_model": updated["ai_model"],
                        "updated_at": updated["updated_at"],
                    }
                )
                break
        store["partials"] = partials
        cls.save_store(store)
        return updated

    @classmethod
    def get_assignments(cls) -> dict[str, Any]:
        """Return normalized assignment payload."""
        store = cls.load_store()
        assignments = store.get("assignments") or {}
        default_assignment = cls._normalize_assignment(assignments.get("default") or {})
        tier_assignments_raw = assignments.get("tiers") or {}
        tier_assignments: dict[str, dict[str, str]] = {}
        if isinstance(tier_assignments_raw, dict):
            for tier_id, assignment in tier_assignments_raw.items():
                tier_key = str(tier_id or "").strip()
                if not tier_key:
                    continue
                tier_assignments[tier_key] = cls._normalize_assignment(assignment or {})
        return {
            "default": default_assignment,
            "tiers": tier_assignments,
            "posthog": cls._normalize_posthog(store.get("posthog") or {}),
        }

    @classmethod
    def save_assignments(
        cls,
        *,
        default_assignment: dict[str, Any],
        tier_assignments: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Persist assignment updates."""
        store = cls.load_store()
        normalized_default = cls._normalize_assignment(default_assignment or {})
        normalized_tiers: dict[str, dict[str, str]] = {}
        for tier_id, assignment in (tier_assignments or {}).items():
            tier_key = str(tier_id or "").strip()
            if not tier_key:
                continue
            normalized_tiers[tier_key] = cls._normalize_assignment(assignment or {})
        store["assignments"] = {
            "default": normalized_default,
            "tiers": normalized_tiers,
        }
        store["updated_at"] = cls._utc_now_iso()
        return cls.save_store(store).get("assignments") or {}

    @classmethod
    def build_signup_panels(
        cls, *, tier_ids: list[str]
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        """Return tier->panel payload map and posthog config for signup template."""
        store = cls.load_store()
        assignments = cls.get_assignments()
        partial_lookup = {
            str(partial.get("id") or ""): partial
            for partial in list(store.get("partials") or [])
            if partial.get("id")
        }
        session_seed = cls._session_bucket_seed()
        panels: dict[str, dict[str, Any]] = {}
        for tier_id in tier_ids:
            tier_key = str(tier_id or "").strip()
            if not tier_key:
                continue
            assignment = assignments.get("tiers", {}).get(
                tier_key, assignments.get("default") or {}
            )
            panel = cls._resolve_panel_for_assignment(
                tier_id=tier_key,
                assignment=assignment,
                partial_lookup=partial_lookup,
                session_seed=session_seed,
            )
            if panel:
                panels[tier_key] = panel
        return panels, assignments.get("posthog") or {}

    @classmethod
    def build_preview_panel(
        cls,
        *,
        tier_id: str,
        mode: str,
        primary_partial_id: str,
        secondary_partial_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve one preview panel for an explicit assignment override."""
        store = cls.load_store()
        partial_lookup = {
            str(partial.get("id") or ""): partial
            for partial in list(store.get("partials") or [])
            if partial.get("id")
        }
        assignment = cls._normalize_assignment(
            {
                "mode": mode,
                "primary_partial_id": primary_partial_id,
                "secondary_partial_id": secondary_partial_id or "",
            }
        )
        session_seed = "preview-seed"
        return cls._resolve_panel_for_assignment(
            tier_id=str(tier_id or ""),
            assignment=assignment,
            partial_lookup=partial_lookup,
            session_seed=session_seed,
        )

    @classmethod
    def build_uniform_preview_panels(
        cls, *, partial_id: str, tier_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Return one draft override mapped to every preview tier."""
        selected = cls.get_partial(partial_id)
        if not selected:
            return {}
        selected_html = cls._sanitize_html(str(selected.get("html_content") or ""))
        if not selected_html:
            return {}
        selected_id = str(selected.get("id") or "")
        selected_name = str(selected.get("name") or "")
        preview_text = cls._preview_text(selected_html)
        panels: dict[str, dict[str, Any]] = {}
        for tier_id in tier_ids:
            tier_key = str(tier_id or "").strip()
            if not tier_key:
                continue
            panels[tier_key] = {
                "tier_id": tier_key,
                "partial_id": selected_id,
                "partial_name": selected_name,
                "assignment_mode": "preview_override",
                "variant_key": "PREVIEW",
                "html_content": selected_html,
                "preview_text": preview_text,
            }
        return panels

    @classmethod
    def _resolve_panel_for_assignment(
        cls,
        *,
        tier_id: str,
        assignment: dict[str, Any],
        partial_lookup: dict[str, dict[str, Any]],
        session_seed: str,
    ) -> dict[str, Any] | None:
        primary_id = str(assignment.get("primary_partial_id") or "").strip()
        secondary_id = str(assignment.get("secondary_partial_id") or "").strip()
        mode = str(assignment.get("mode") or "manual").strip()
        if mode not in _VALID_ASSIGNMENT_MODES:
            mode = "manual"

        selected_id = primary_id
        variant_key = "A"
        if (
            mode == "split_50_50"
            and primary_id
            and secondary_id
            and primary_id != secondary_id
        ):
            bucket = cls._stable_bucket(session_seed=session_seed, tier_id=tier_id)
            if bucket == 1:
                selected_id = secondary_id
                variant_key = "B"

        selected = partial_lookup.get(selected_id)
        if not selected:
            return None
        selected_html = cls._sanitize_html(str(selected.get("html_content") or ""))
        if not selected_html:
            return None
        return {
            "tier_id": tier_id,
            "partial_id": str(selected.get("id") or ""),
            "partial_name": str(selected.get("name") or ""),
            "assignment_mode": mode,
            "variant_key": variant_key,
            "html_content": selected_html,
            "preview_text": cls._preview_text(selected_html),
        }

    @classmethod
    def _normalize_store(cls, raw: dict[str, Any]) -> dict[str, Any]:
        partials_raw = raw.get("partials") if isinstance(raw, dict) else []
        if not isinstance(partials_raw, list):
            partials_raw = []
        if not partials_raw:
            partials_raw = cls._default_partials()
        normalized_partials: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for index, partial in enumerate(partials_raw):
            normalized = cls._normalize_partial(partial, index=index)
            if normalized["id"] in seen_ids:
                normalized["id"] = cls._next_partial_id(
                    normalized["name"], existing=normalized_partials
                )
            seen_ids.add(normalized["id"])
            normalized_partials.append(normalized)

        assignments_raw = raw.get("assignments") if isinstance(raw, dict) else {}
        if not isinstance(assignments_raw, dict):
            assignments_raw = {}
        default_assignment = cls._normalize_assignment(assignments_raw.get("default") or {})
        if not default_assignment.get("primary_partial_id"):
            default_assignment["primary_partial_id"] = str(
                normalized_partials[0].get("id") or ""
            )
        tier_assignments_raw = assignments_raw.get("tiers") or {}
        tier_assignments: dict[str, dict[str, str]] = {}
        if isinstance(tier_assignments_raw, dict):
            for tier_id, assignment in tier_assignments_raw.items():
                tier_key = str(tier_id or "").strip()
                if not tier_key:
                    continue
                tier_assignments[tier_key] = cls._normalize_assignment(assignment or {})

        posthog = cls._normalize_posthog(raw.get("posthog") if isinstance(raw, dict) else {})
        return {
            "partials": normalized_partials,
            "assignments": {
                "default": default_assignment,
                "tiers": tier_assignments,
            },
            "posthog": posthog,
            "updated_at": str(raw.get("updated_at") or cls._utc_now_iso()),
        }

    @classmethod
    def _normalize_partial(
        cls, raw: dict[str, Any], *, index: int
    ) -> dict[str, Any]:
        source = raw if isinstance(raw, dict) else {}
        now_iso = cls._utc_now_iso()
        name = str(source.get("name") or f"Signup Info Partial {index + 1}").strip()
        partial_id = str(source.get("id") or "").strip()
        if not partial_id:
            partial_id = cls._slugify(name) or f"signup_info_partial_{index + 1}"
        html_content = cls._sanitize_html(str(source.get("html_content") or ""))
        if not html_content:
            html_content = "<p>Add persuasive copy for this signup info partial.</p>"
        lineage_key = str(source.get("lineage_key") or partial_id).strip() or partial_id
        version = source.get("version")
        try:
            version_value = max(1, int(version))
        except (TypeError, ValueError):
            version_value = 1

        return {
            "id": partial_id,
            "name": name,
            "slug": cls._slugify(str(source.get("slug") or name)),
            "status": cls._normalize_status(source.get("status")),
            "version": version_value,
            "lineage_key": lineage_key,
            "parent_partial_id": str(source.get("parent_partial_id") or "").strip() or None,
            "html_content": html_content,
            "source_prompt": str(source.get("source_prompt") or "").strip() or None,
            "ai_model": str(source.get("ai_model") or "").strip() or None,
            "created_at": str(source.get("created_at") or now_iso),
            "updated_at": str(source.get("updated_at") or now_iso),
            "preview_text": cls._preview_text(html_content),
        }

    @staticmethod
    def _normalize_status(raw_status: Any) -> str:
        candidate = str(raw_status or "draft").strip().lower()
        return candidate if candidate in _VALID_STATUSES else "draft"

    @staticmethod
    def _normalize_assignment(raw_assignment: dict[str, Any]) -> dict[str, str]:
        source = raw_assignment if isinstance(raw_assignment, dict) else {}
        mode = str(source.get("mode") or "manual").strip().lower()
        if mode not in _VALID_ASSIGNMENT_MODES:
            mode = "manual"
        primary = str(source.get("primary_partial_id") or "").strip()
        secondary = str(source.get("secondary_partial_id") or "").strip()
        if mode == "split_50_50" and (not primary or not secondary):
            mode = "manual"
            secondary = ""
        return {
            "mode": mode,
            "primary_partial_id": primary,
            "secondary_partial_id": secondary,
        }

    @staticmethod
    def _normalize_posthog(raw_posthog: dict[str, Any]) -> dict[str, str]:
        source = raw_posthog if isinstance(raw_posthog, dict) else {}
        experiment_key = (
            str(source.get("experiment_key") or "signup_info_partial_experiment")
            .strip()
            .lower()
        )
        property_key = (
            str(source.get("property_key") or "signup_info_partial_id").strip().lower()
        )
        return {
            "experiment_key": experiment_key,
            "property_key": property_key,
        }

    @classmethod
    def _next_lineage_version(cls, *, lineage_key: str) -> int:
        if not lineage_key:
            return 1
        partials = cls.list_partials(include_archived=True)
        max_version = 0
        for partial in partials:
            if str(partial.get("lineage_key") or "") != lineage_key:
                continue
            try:
                max_version = max(max_version, int(partial.get("version") or 0))
            except (TypeError, ValueError):
                continue
        return max_version + 1

    @classmethod
    def _next_partial_id(cls, name: str, *, existing: list[dict[str, Any]]) -> str:
        base = cls._slugify(name) or "signup_info_partial"
        candidate = base
        existing_ids = {str(item.get("id") or "") for item in existing}
        suffix = 1
        while candidate in existing_ids:
            suffix += 1
            candidate = f"{base}_{suffix}"
        return candidate

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = _NON_SLUG_RE.sub("_", str(value or "").strip().lower()).strip("_")
        if not normalized:
            return ""
        if not normalized.startswith("signup_info_partial"):
            return f"signup_info_partial_{normalized}"
        return normalized

    @staticmethod
    def _sanitize_html(html_content: str) -> str:
        value = str(html_content or "").strip()
        if not value:
            return ""
        stripped = _SCRIPT_TAG_RE.sub("", value)
        return stripped.strip()

    @staticmethod
    def _preview_text(html_content: str, *, max_chars: int = 220) -> str:
        plain = _HTML_TAG_RE.sub(" ", str(html_content or ""))
        plain = _WHITESPACE_RE.sub(" ", plain).strip()
        if len(plain) <= max_chars:
            return plain
        return plain[: max_chars - 1].rstrip() + "…"

    @classmethod
    def _session_bucket_seed(cls) -> str:
        existing = session.get(cls._SESSION_BUCKET_KEY)
        if isinstance(existing, str) and existing.strip():
            return existing
        generated = uuid.uuid4().hex
        session[cls._SESSION_BUCKET_KEY] = generated
        return generated

    @staticmethod
    def _stable_bucket(*, session_seed: str, tier_id: str) -> int:
        digest = hashlib.sha256(f"{session_seed}:{tier_id}".encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % 2

    @classmethod
    def _content_path(cls) -> Path:
        return Path(current_app.root_path) / cls._CONTENT_RELATIVE_PATH

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _default_partials() -> list[dict[str, Any]]:
        now_iso = datetime.now(timezone.utc).isoformat()
        return [
            {
                "id": "signup_info_partial_a",
                "name": "Signup Info Partial A",
                "slug": "signup_info_partial_a",
                "status": "active",
                "version": 1,
                "lineage_key": "signup_info_partial_a",
                "parent_partial_id": None,
                "html_content": (
                    "<div class='signup-info-block'>"
                    "<h3>See value in your first 20 minutes.</h3>"
                    "<ul>"
                    "<li><strong>Start fast:</strong> set up your first tracked batch in one short session.</li>"
                    "<li><strong>Know what happened:</strong> keep each recipe, lot, and batch decision in one place.</li>"
                    "<li><strong>Avoid preventable waste:</strong> catch ingredient and process gaps before they become costly.</li>"
                    "<li><strong>Feel in control quickly:</strong> move from guessing to clear next steps today.</li>"
                    "</ul>"
                    "</div>"
                ),
                "source_prompt": None,
                "ai_model": None,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
            {
                "id": "signup_info_partial_b",
                "name": "Signup Info Partial B",
                "slug": "signup_info_partial_b",
                "status": "active",
                "version": 1,
                "lineage_key": "signup_info_partial_b",
                "parent_partial_id": None,
                "html_content": (
                    "<div class='signup-info-block'>"
                    "<h3>Start risk-free with the tools you need right now.</h3>"
                    "<ul>"
                    "<li><strong>No heavy lift:</strong> pick the tier that fits today and start immediately.</li>"
                    "<li><strong>Grow at your pace:</strong> upgrade only when your operation is ready.</li>"
                    "<li><strong>Better decisions:</strong> connect ingredients, batches, and costs in one flow.</li>"
                    "<li><strong>Built for makers:</strong> practical workflows your team can trust.</li>"
                    "</ul>"
                    "</div>"
                ),
                "source_prompt": None,
                "ai_model": None,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
        ]

    @classmethod
    def _generate_ai_payload(
        cls,
        *,
        client: GoogleAIClient,
        model_name: str,
        base_partial: dict[str, Any],
        prompt: str,
        tier_names: list[str],
    ) -> dict[str, str]:
        context_payload = {
            "base_partial_name": str(base_partial.get("name") or ""),
            "base_partial_html": str(base_partial.get("html_content") or ""),
            "tier_names": [str(name).strip() for name in tier_names if str(name).strip()],
            "task_prompt": prompt,
            "constraints": {
                "max_words": 220,
                "format": "valid html block with heading, paragraph, and bullet list",
            },
        }
        result = client.generate_content(
            model=model_name,
            system_instruction=(
                "You write conversion-focused signup page below-card copy for SaaS plans. "
                "Return strict JSON only with keys `name` and `html_content`. "
                "The html_content value must be safe marketing HTML without scripts."
            ),
            generation_config={
                "temperature": 0.55,
                "top_p": 0.85,
                "max_output_tokens": 1400,
            },
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Create a new draft variant based on this context:\n"
                                f"{json.dumps(context_payload)}"
                            )
                        }
                    ],
                }
            ],
        )
        parsed = cls._parse_ai_json(result.text)
        html_content = cls._sanitize_html(str(parsed.get("html_content") or ""))
        name = str(parsed.get("name") or "").strip()
        if not html_content:
            fallback_text = str(result.text or "").strip()
            html_content = f"<div class='signup-info-block'><p>{fallback_text}</p></div>"
        if not name:
            random_suffix = random.randint(100, 999)
            name = f"{base_partial.get('name') or 'Signup Info Partial'} AI Draft {random_suffix}"
        return {"name": name, "html_content": html_content}

    @staticmethod
    def _parse_ai_json(raw_text: str) -> dict[str, Any]:
        text = str(raw_text or "").strip()
        if not text:
            return {}
        fence_match = _JSON_FENCE_RE.search(text)
        candidate = fence_match.group(1).strip() if fence_match else text
        if not candidate.startswith("{"):
            first_brace = candidate.find("{")
            last_brace = candidate.rfind("}")
            if first_brace >= 0 and last_brace > first_brace:
                candidate = candidate[first_brace : last_brace + 1]
        try:
            loaded = json.loads(candidate)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}

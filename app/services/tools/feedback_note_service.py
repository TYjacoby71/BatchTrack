"""Tool feedback note persistence service.

Synopsis:
Stores lightweight user notes from tool UIs in JSON buckets that are grouped by
source first and flow second.

Glossary:
- Source: Origin area (for example, ``soap_formulator`` or ``tools_shell``).
- Flow: Feedback type bucket (question, missing feature, glitch, bad preset data).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import func, inspect

from app.extensions import db
from app.models.tool_feedback_note import ToolFeedbackNote
from app.utils.json_store import read_json_file, write_json_file

logger = logging.getLogger(__name__)


class ToolFeedbackNoteService:
    """Persist feedback notes to JSON files grouped by source and flow."""

    BASE_DIR = Path("data/tool_feedback_notes")
    DEFAULT_SOURCE = "unknown_source"
    FLOW_ORDER = (
        "question",
        "missing_feature",
        "glitch",
        "bad_preset_data",
    )
    FLOW_LABELS = {
        "question": "Question",
        "missing_feature": "Missing feature",
        "glitch": "Glitch",
        "bad_preset_data": "Bad preset data",
    }
    _SOURCE_SANITIZER = re.compile(r"[^a-z0-9_-]+")
    _FLOW_SANITIZER = re.compile(r"[^a-z0-9_]+")
    _FLOW_ALIASES = {
        "missing": "missing_feature",
        "missingfeature": "missing_feature",
        "feature_request": "missing_feature",
        "feature_requests": "missing_feature",
        "bug": "glitch",
        "issue": "glitch",
        "bad_data": "bad_preset_data",
        "bad_preset": "bad_preset_data",
        "bad_preset_info": "bad_preset_data",
        "bad_data_on_preset_info_like_soap_values": "bad_preset_data",
    }
    _PATH_SEGMENT_SANITIZER = re.compile(r"[^a-z0-9._-]+")
    _LIKELY_DYNAMIC_SEGMENT = re.compile(
        r"^(?:\d+|[0-9a-f]{8,}|[0-9a-f]{8}-[0-9a-f-]{27,})$"
    )

    @classmethod
    def allowed_flows(cls) -> list[str]:
        return list(cls.FLOW_ORDER)

    @classmethod
    def normalize_source(cls, raw_source: Any) -> str:
        if not isinstance(raw_source, str):
            return cls.DEFAULT_SOURCE
        cleaned = cls._SOURCE_SANITIZER.sub("_", raw_source.strip().lower()).strip(
            "._-"
        )
        return cleaned or cls.DEFAULT_SOURCE

    @classmethod
    def derive_location_source(
        cls,
        *,
        page_endpoint: Any = None,
        page_path: Any = None,
        fallback_source: Any = None,
    ) -> str:
        endpoint_value = cls._clean_text(page_endpoint, max_len=180)
        if endpoint_value:
            return cls.normalize_source(endpoint_value)

        path_value = cls._clean_text(page_path, max_len=512)
        if path_value:
            without_query = path_value.split("?", 1)[0].split("#", 1)[0]
            pieces: list[str] = []
            for part in without_query.split("/"):
                segment = cls._PATH_SEGMENT_SANITIZER.sub(
                    "_", part.strip().lower()
                ).strip("._-")
                if not segment:
                    continue
                if cls._LIKELY_DYNAMIC_SEGMENT.match(segment):
                    continue
                pieces.append(segment)
            if pieces:
                return cls.normalize_source("_".join(pieces))

        return cls.normalize_source(fallback_source)

    @classmethod
    def normalize_flow(cls, raw_flow: Any) -> str | None:
        if not isinstance(raw_flow, str):
            return None
        normalized = cls._FLOW_SANITIZER.sub("_", raw_flow.strip().lower()).strip("_")
        normalized = cls._FLOW_ALIASES.get(normalized, normalized)
        if normalized not in cls.FLOW_LABELS:
            return None
        return normalized

    @staticmethod
    def _clean_text(raw: Any, *, max_len: int) -> str | None:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        if len(text) > max_len:
            return text[:max_len]
        return text

    @classmethod
    def _clean_email(cls, raw: Any) -> str | None:
        value = cls._clean_text(raw, max_len=254)
        if not value or "@" not in value:
            return None
        return value.lower()

    @classmethod
    def _clean_metadata(cls, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        cleaned: dict[str, Any] = {}
        for key, value in raw.items():
            safe_key = cls._clean_text(key, max_len=64)
            if not safe_key:
                continue
            if isinstance(value, str):
                cleaned[safe_key] = cls._clean_text(value, max_len=240) or ""
            elif isinstance(value, (int, float, bool)) or value is None:
                cleaned[safe_key] = value
            else:
                cleaned[safe_key] = cls._clean_text(str(value), max_len=240) or ""
        return cleaned or None

    @classmethod
    def _bucket_path(cls, source: str, flow: str) -> Path:
        return cls.BASE_DIR / source / f"{flow}.json"

    @classmethod
    def _db_is_ready(cls) -> bool:
        try:
            return inspect(db.engine).has_table(ToolFeedbackNote.__tablename__)
        except Exception:
            return False

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    @classmethod
    def _entry_from_db_note(cls, note: ToolFeedbackNote) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": note.id,
            "submitted_at": (
                note.submitted_at.isoformat() if note.submitted_at else None
            ),
            "source": note.source,
            "flow": note.flow,
            "flow_label": note.flow_label,
            "title": note.title,
            "message": note.message,
            "context": note.context,
            "page_path": note.page_path,
            "page_url": note.page_url,
            "contact_email": note.contact_email,
        }
        if isinstance(note.metadata_json, dict) and note.metadata_json:
            entry["metadata"] = note.metadata_json
        if isinstance(note.request_json, dict) and note.request_json:
            entry["request"] = note.request_json
        if isinstance(note.user_json, dict) and note.user_json:
            entry["user"] = note.user_json
        return entry

    @classmethod
    def _save_note_to_db(cls, entry: dict[str, Any]) -> int | None:
        if not cls._db_is_ready():
            return None
        try:
            source = cls.normalize_source(entry.get("source"))
            flow = cls.normalize_flow(entry.get("flow"))
            if not flow:
                return None

            note = ToolFeedbackNote(
                id=str(entry.get("id") or uuid4().hex),
                submitted_at=cls._coerce_datetime(entry.get("submitted_at")),
                source=source,
                flow=flow,
                flow_label=cls.FLOW_LABELS.get(flow, flow.replace("_", " ").title()),
                title=cls._clean_text(entry.get("title"), max_len=160),
                message=cls._clean_text(entry.get("message"), max_len=4000) or "",
                context=cls._clean_text(entry.get("context"), max_len=120),
                page_path=cls._clean_text(entry.get("page_path"), max_len=240),
                page_url=cls._clean_text(entry.get("page_url"), max_len=512),
                contact_email=cls._clean_email(entry.get("contact_email")),
                metadata_json=(
                    entry.get("metadata")
                    if isinstance(entry.get("metadata"), dict)
                    else None
                ),
                request_json=(
                    entry.get("request")
                    if isinstance(entry.get("request"), dict)
                    else None
                ),
                user_json=(
                    entry.get("user") if isinstance(entry.get("user"), dict) else None
                ),
            )
            db.session.add(note)
            db.session.commit()

            bucket_count = (
                db.session.query(func.count(ToolFeedbackNote.id))
                .filter(
                    ToolFeedbackNote.source == source,
                    ToolFeedbackNote.flow == flow,
                )
                .scalar()
                or 0
            )
            return int(bucket_count)
        except Exception:
            db.session.rollback()
            logger.warning(
                "Unable to persist support note to DB; falling back to JSON",
                exc_info=True,
            )
            return None

    @classmethod
    def _load_global_index_from_db(cls) -> dict[str, Any] | None:
        if not cls._db_is_ready():
            return None
        try:
            grouped_rows = (
                db.session.query(
                    ToolFeedbackNote.source,
                    ToolFeedbackNote.flow,
                    func.count(ToolFeedbackNote.id),
                )
                .group_by(ToolFeedbackNote.source, ToolFeedbackNote.flow)
                .all()
            )
            latest_ts = db.session.query(
                func.max(ToolFeedbackNote.submitted_at)
            ).scalar()

            source_map: dict[str, dict[str, int]] = {}
            for source, flow, count in grouped_rows:
                source_key = cls.normalize_source(source)
                flow_key = cls.normalize_flow(flow)
                if not source_key or not flow_key:
                    continue
                flow_counts = source_map.setdefault(source_key, {})
                flow_counts[flow_key] = int(count or 0)

            sources: list[dict[str, Any]] = []
            for source_key in sorted(source_map.keys()):
                flow_counts = source_map.get(source_key, {})
                ordered_flows: list[dict[str, Any]] = []
                for flow in cls.FLOW_ORDER:
                    count = int(flow_counts.get(flow) or 0)
                    if count <= 0:
                        continue
                    ordered_flows.append(
                        {
                            "flow": flow,
                            "flow_label": cls.FLOW_LABELS.get(
                                flow, flow.replace("_", " ").title()
                            ),
                            "count": count,
                            "path": f"{source_key}/{flow}.json",
                        }
                    )
                if ordered_flows:
                    sources.append({"source": source_key, "flows": ordered_flows})

            return {
                "updated_at": (
                    latest_ts.isoformat()
                    if isinstance(latest_ts, datetime)
                    else datetime.now(timezone.utc).isoformat()
                ),
                "sources": sources,
            }
        except Exception:
            db.session.rollback()
            logger.warning(
                "Unable to load support-note global index from DB",
                exc_info=True,
            )
            return None

    @classmethod
    def _load_bucket_from_db(
        cls, *, source: str, flow: str, limit: int | None = None
    ) -> dict[str, Any] | None:
        if not cls._db_is_ready():
            return None
        try:
            base_query = ToolFeedbackNote.query.filter(
                ToolFeedbackNote.source == source,
                ToolFeedbackNote.flow == flow,
            )
            count = int(base_query.count() or 0)
            latest_ts = base_query.with_entities(
                func.max(ToolFeedbackNote.submitted_at)
            ).scalar()

            rows_query = base_query.order_by(
                ToolFeedbackNote.submitted_at.desc(),
                ToolFeedbackNote.id.desc(),
            )
            if isinstance(limit, int) and limit > 0:
                rows_query = rows_query.limit(limit)
            rows = rows_query.all()
            entries = [cls._entry_from_db_note(row) for row in rows]

            return {
                "source": source,
                "flow": flow,
                "flow_label": cls.FLOW_LABELS.get(flow, flow.replace("_", " ").title()),
                "count": count,
                "entries": entries,
                "bucket_path": f"{source}/{flow}.json",
                "updated_at": (
                    latest_ts.isoformat() if isinstance(latest_ts, datetime) else None
                ),
            }
        except Exception:
            db.session.rollback()
            logger.warning("Unable to load support-note bucket from DB", exc_info=True)
            return None

    @classmethod
    def _entry_payload(
        cls,
        payload: dict[str, Any],
        *,
        request_meta: dict[str, Any] | None = None,
        user: Any = None,
        source_override: str | None = None,
    ) -> dict[str, Any]:
        source = cls.normalize_source(source_override or payload.get("source"))
        flow = cls.normalize_flow(
            payload.get("flow") or payload.get("type") or payload.get("note_type")
        )
        if not flow:
            raise ValueError(
                "Choose one type: question, missing feature, glitch, or bad preset data."
            )

        message = cls._clean_text(
            payload.get("message") or payload.get("need") or payload.get("details"),
            max_len=4000,
        )
        if not message:
            raise ValueError("Please share what you need before submitting.")

        now_iso = datetime.now(timezone.utc).isoformat()
        entry: dict[str, Any] = {
            "id": uuid4().hex,
            "submitted_at": now_iso,
            "source": source,
            "flow": flow,
            "flow_label": cls.FLOW_LABELS[flow],
            "title": cls._clean_text(payload.get("title"), max_len=160),
            "message": message,
            "context": cls._clean_text(payload.get("context"), max_len=120),
            "page_path": cls._clean_text(payload.get("page_path"), max_len=240),
            "page_url": cls._clean_text(payload.get("page_url"), max_len=512),
            "contact_email": cls._clean_email(
                payload.get("contact_email") or payload.get("email")
            ),
        }

        metadata = cls._clean_metadata(payload.get("metadata"))
        if metadata:
            entry["metadata"] = metadata

        if request_meta:
            entry["request"] = {
                "ip": cls._clean_text(request_meta.get("ip"), max_len=80),
                "user_agent": cls._clean_text(
                    request_meta.get("user_agent"), max_len=240
                ),
                "referer": cls._clean_text(request_meta.get("referer"), max_len=512),
            }

        if user is not None and getattr(user, "is_authenticated", False):
            entry["user"] = {
                "id": getattr(user, "id", None),
                "username": cls._clean_text(
                    getattr(user, "username", None), max_len=120
                ),
                "email": cls._clean_email(getattr(user, "email", None)),
            }

        return entry

    @classmethod
    def _build_flow_summary(cls, source: str, flow: str) -> dict[str, Any]:
        bucket_path = cls._bucket_path(source, flow)
        bucket = read_json_file(bucket_path, default={}) or {}
        entries = bucket.get("entries") if isinstance(bucket, dict) else []
        count = len(entries) if isinstance(entries, list) else 0
        return {
            "flow": flow,
            "flow_label": cls.FLOW_LABELS.get(flow, flow.replace("_", " ").title()),
            "count": count,
            "path": f"{source}/{flow}.json",
        }

    @classmethod
    def _write_source_index(cls, source: str) -> dict[str, Any]:
        source_dir = cls.BASE_DIR / source
        flows: list[dict[str, Any]] = []
        for flow in cls.FLOW_ORDER:
            bucket_path = cls._bucket_path(source, flow)
            if not bucket_path.exists():
                continue
            flows.append(cls._build_flow_summary(source, flow))

        source_index = {
            "source": source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "flows": flows,
        }
        write_json_file(source_dir / "index.json", source_index)
        return source_index

    @classmethod
    def _write_global_index(cls) -> dict[str, Any]:
        cls.BASE_DIR.mkdir(parents=True, exist_ok=True)
        sources: list[dict[str, Any]] = []
        source_dirs = sorted(
            [path for path in cls.BASE_DIR.iterdir() if path.is_dir()],
            key=lambda item: item.name,
        )
        for source_dir in source_dirs:
            source = source_dir.name
            source_index_path = source_dir / "index.json"
            source_index = read_json_file(source_index_path, default={}) or {}
            raw_flows = (
                source_index.get("flows") if isinstance(source_index, dict) else []
            )
            flow_lookup: dict[str, dict[str, Any]] = {}
            if isinstance(raw_flows, list):
                for row in raw_flows:
                    if isinstance(row, dict) and row.get("flow"):
                        flow_lookup[str(row["flow"])] = row

            ordered_flows: list[dict[str, Any]] = []
            for flow in cls.FLOW_ORDER:
                row = flow_lookup.get(flow) or cls._build_flow_summary(source, flow)
                if (
                    int(row.get("count") or 0) <= 0
                    and not cls._bucket_path(source, flow).exists()
                ):
                    continue
                ordered_flows.append(
                    {
                        "flow": flow,
                        "flow_label": cls.FLOW_LABELS.get(
                            flow, flow.replace("_", " ").title()
                        ),
                        "count": int(row.get("count") or 0),
                        "path": f"{source}/{flow}.json",
                    }
                )

            sources.append({"source": source, "flows": ordered_flows})

        index_payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sources": sources,
        }
        write_json_file(cls.BASE_DIR / "index.json", index_payload)
        return index_payload

    @classmethod
    def save_note(
        cls,
        payload: dict[str, Any] | None,
        *,
        request_meta: dict[str, Any] | None = None,
        user: Any = None,
        source_override: str | None = None,
    ) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        entry = cls._entry_payload(
            payload,
            request_meta=request_meta,
            user=user,
            source_override=source_override,
        )
        source = entry["source"]
        flow = entry["flow"]
        bucket_path = cls._bucket_path(source, flow)

        db_bucket_count = cls._save_note_to_db(entry)

        legacy_bucket_count: int | None = None
        try:
            current_bucket = read_json_file(bucket_path, default={}) or {}
            entries = (
                current_bucket.get("entries")
                if isinstance(current_bucket, dict)
                else []
            )
            if not isinstance(entries, list):
                entries = []
            entries.append(entry)
            entries.sort(
                key=lambda row: str(row.get("submitted_at") or ""), reverse=True
            )

            bucket_payload = {
                "source": source,
                "flow": flow,
                "flow_label": cls.FLOW_LABELS[flow],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(entries),
                "entries": entries,
            }
            write_json_file(bucket_path, bucket_payload)
            cls._write_source_index(source)
            cls._write_global_index()
            legacy_bucket_count = len(entries)
        except Exception:
            logger.warning(
                "Unable to persist legacy JSON feedback note bucket",
                exc_info=True,
            )

        return {
            "id": entry["id"],
            "source": source,
            "flow": flow,
            "flow_label": cls.FLOW_LABELS[flow],
            "bucket_path": f"{source}/{flow}.json",
            "bucket_count": int(
                db_bucket_count
                if db_bucket_count is not None
                else (legacy_bucket_count if legacy_bucket_count is not None else 1)
            ),
        }

    @classmethod
    def load_global_index(cls, *, refresh: bool = False) -> dict[str, Any]:
        """Return the global source/flow index for support dashboards."""
        db_payload = cls._load_global_index_from_db()
        if isinstance(db_payload, dict) and isinstance(db_payload.get("sources"), list):
            if db_payload["sources"]:
                return db_payload

        if refresh:
            return cls._write_global_index()

        index_path = cls.BASE_DIR / "index.json"
        payload = read_json_file(index_path, default={}) or {}
        if not isinstance(payload, dict) or "sources" not in payload:
            payload = cls._write_global_index()
        return payload if isinstance(payload, dict) else {"sources": []}

    @classmethod
    def load_bucket(
        cls, *, source: Any, flow: Any, limit: int | None = None
    ) -> dict[str, Any]:
        """Load a normalized feedback bucket and optionally cap returned entries."""
        normalized_source = cls.normalize_source(source)
        normalized_flow = cls.normalize_flow(flow)
        if not normalized_flow:
            raise ValueError(
                "Choose one type: question, missing feature, glitch, or bad preset data."
            )

        db_bucket = cls._load_bucket_from_db(
            source=normalized_source,
            flow=normalized_flow,
            limit=limit,
        )
        if isinstance(db_bucket, dict) and int(db_bucket.get("count") or 0) > 0:
            return db_bucket

        bucket_path = cls._bucket_path(normalized_source, normalized_flow)
        bucket = read_json_file(bucket_path, default={}) or {}
        entries = bucket.get("entries") if isinstance(bucket, dict) else []
        if not isinstance(entries, list):
            entries = []

        if isinstance(limit, int) and limit > 0:
            entries = entries[:limit]

        count = (
            int(bucket.get("count") or 0) if isinstance(bucket, dict) else len(entries)
        )
        return {
            "source": normalized_source,
            "flow": normalized_flow,
            "flow_label": cls.FLOW_LABELS.get(
                normalized_flow, normalized_flow.replace("_", " ").title()
            ),
            "count": count,
            "entries": entries,
            "bucket_path": f"{normalized_source}/{normalized_flow}.json",
            "updated_at": (
                bucket.get("updated_at") if isinstance(bucket, dict) else None
            ),
        }

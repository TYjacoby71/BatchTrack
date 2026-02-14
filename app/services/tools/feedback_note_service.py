"""Tool feedback note persistence service.

Synopsis:
Stores lightweight user notes from tool UIs in JSON buckets that are grouped by
source first and flow second.

Glossary:
- Source: Origin area (for example, ``soap_formulator`` or ``tools_shell``).
- Flow: Feedback type bucket (question, missing feature, glitch, bad preset data).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.utils.json_store import read_json_file, write_json_file


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
        cleaned = cls._SOURCE_SANITIZER.sub("_", raw_source.strip().lower()).strip("._-")
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
                segment = cls._PATH_SEGMENT_SANITIZER.sub("_", part.strip().lower()).strip("._-")
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
            raise ValueError("Choose one type: question, missing feature, glitch, or bad preset data.")

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
            "contact_email": cls._clean_email(payload.get("contact_email") or payload.get("email")),
        }

        metadata = cls._clean_metadata(payload.get("metadata"))
        if metadata:
            entry["metadata"] = metadata

        if request_meta:
            entry["request"] = {
                "ip": cls._clean_text(request_meta.get("ip"), max_len=80),
                "user_agent": cls._clean_text(request_meta.get("user_agent"), max_len=240),
                "referer": cls._clean_text(request_meta.get("referer"), max_len=512),
            }

        if user is not None and getattr(user, "is_authenticated", False):
            entry["user"] = {
                "id": getattr(user, "id", None),
                "username": cls._clean_text(getattr(user, "username", None), max_len=120),
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
            raw_flows = source_index.get("flows") if isinstance(source_index, dict) else []
            flow_lookup: dict[str, dict[str, Any]] = {}
            if isinstance(raw_flows, list):
                for row in raw_flows:
                    if isinstance(row, dict) and row.get("flow"):
                        flow_lookup[str(row["flow"])] = row

            ordered_flows: list[dict[str, Any]] = []
            for flow in cls.FLOW_ORDER:
                row = flow_lookup.get(flow) or cls._build_flow_summary(source, flow)
                if int(row.get("count") or 0) <= 0 and not cls._bucket_path(source, flow).exists():
                    continue
                ordered_flows.append(
                    {
                        "flow": flow,
                        "flow_label": cls.FLOW_LABELS.get(flow, flow.replace("_", " ").title()),
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

        current_bucket = read_json_file(bucket_path, default={}) or {}
        entries = current_bucket.get("entries") if isinstance(current_bucket, dict) else []
        if not isinstance(entries, list):
            entries = []
        entries.append(entry)
        entries.sort(key=lambda row: str(row.get("submitted_at") or ""), reverse=True)

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

        return {
            "id": entry["id"],
            "source": source,
            "flow": flow,
            "flow_label": cls.FLOW_LABELS[flow],
            "bucket_path": f"{source}/{flow}.json",
            "bucket_count": len(entries),
        }

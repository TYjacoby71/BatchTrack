from __future__ import annotations

import logging
import os
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional

from flask import current_app
from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import (
    CommunityScoutBatch,
    CommunityScoutCandidate,
    CommunityScoutJobState,
    GlobalItem,
    InventoryItem,
    UnifiedInventoryHistory,
)
from ..utils.timezone_utils import TimezoneUtils
from .global_link_suggestions import GlobalLinkSuggestionService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GlobalCatalogEntry:
    id: int
    name: str
    normalized_name: str
    normalized_tokens: set[str]
    item_type: str
    default_unit: str | None
    density: float | None
    category_id: int | None
    normalized_inci: str | None
    aliases: list[str]
    normalized_aliases: list[str]
    normalized_alias_tokens: list[set[str]]


class CommunityScoutService:
    """Core orchestration for Community Scout indexing, matching, and resolution."""

    DEFAULT_BATCH_SIZE = 100
    DEFAULT_PAGE_SIZE = 500
    REVIEW_SCORE_THRESHOLD = 0.65
    MIN_FUZZY_THRESHOLD = 0.45
    HIGH_TRUST_MATCHES = {'exact', 'aka', 'inci'}

    COMMON_TRANSLATIONS = {
        'leche': 'milk',
        'miel': 'honey',
        'azucar': 'sugar',
        'harina': 'flour',
        'queso': 'cheese',
        'huevo': 'egg',
        'huevos': 'eggs',
        'cacao': 'cocoa',
        'cafe': 'coffee',
        'piel': 'skin',
        'aceite': 'oil',
        'manteca': 'butter',
        'agua': 'water',
        'carne': 'meat',
    }

    SENSITIVE_ALIAS_TERMS = {
        'niggertoe',
        'niggertoes',
        'nigger_toe',
        'nigger_toes',
        'negrotoe',
        'negrotoes',
        'negro_toe',
        'negro_toes',
    }

    INVENTORY_QUERY = text(
        """
        SELECT
            ii.id,
            ii.organization_id,
            org.name AS organization_name,
            ii.name,
            ii.type,
            ii.unit,
            ii.quantity,
            ii.density,
            ii.inci_name,
            ii.created_at,
            ii.updated_at
        FROM inventory_item AS ii
        LEFT JOIN organization AS org ON org.id = ii.organization_id
        WHERE
            ii.global_item_id IS NULL
            AND (ii.is_archived IS NULL OR ii.is_archived = FALSE)
            AND ii.name IS NOT NULL
            AND ii.id > :after_id
        ORDER BY ii.id ASC
        LIMIT :limit
        """
    )

    _read_engine: Engine | None = None
    _last_data_source: str = 'unknown'

    @classmethod
    def generate_batches(
        cls,
        batch_size: int | None = None,
        page_size: int | None = None,
        max_batches: int | None = None,
        job_name: str = 'community_scout_generate',
        allow_primary_fallback: bool = True,
    ) -> Dict[str, Any]:
        """Nightly/off-hours batch builder."""
        size = max(1, batch_size or cls.DEFAULT_BATCH_SIZE)
        page = max(size, page_size or cls.DEFAULT_PAGE_SIZE)
        stats = {
            'scanned': 0,
            'candidates_created': 0,
            'batches_created': 0,
            'skipped_existing': 0,
            'locked': False,
            'read_source': 'unknown',
            'skipped': False,
            'skipped_reason': None,
        }
        start_clock = perf_counter()

        job_state = cls._get_or_create_job_state(job_name)
        job_id = f"{job_name}-{TimezoneUtils.utc_now().isoformat()}"

        if not job_state.acquire_lock(owner=job_id):
            stats['locked'] = True
            logger.info("Community Scout job already running; skipping new invocation.")
            return stats

        if not allow_primary_fallback:
            # Force replica availability before doing any work
            if cls._get_read_engine() is None:
                stats['skipped'] = True
                stats['skipped_reason'] = 'replica_unavailable'
                job_state.last_error = "Replica required but unavailable"
                job_state.lock_owner = None
                job_state.lock_expires_at = None
                db.session.commit()
                cls._log_job_stats(stats, 0.0)
                return stats

        catalog = cls._build_global_catalog()
        if not catalog.entries:
            logger.warning("Community Scout: no global catalog entries available.")

        cls._last_data_source = 'replica' if cls._has_replica_config() else 'primary'

        current_batch: CommunityScoutBatch | None = None
        current_batch_count = 0
        last_id = job_state.last_inventory_id_processed or 0
        wrapped = False
        stop_requested = False

        try:
            while True:
                page_rows = cls._fetch_inventory_page(after_id=last_id, limit=page)
                if not page_rows:
                    if wrapped:
                        break
                    # Reset to beginning and continue one more pass
                    last_id = 0
                    wrapped = True
                    continue

                wrapped = False
                for row in page_rows:
                    last_id = row['id']
                    job_state.last_inventory_id_processed = last_id
                    stats['scanned'] += 1

                    if cls._candidate_exists(row['id']):
                        stats['skipped_existing'] += 1
                        continue

                    snapshot = cls._build_snapshot(row)
                    match_payload = cls._evaluate_snapshot(snapshot, catalog)
                    if not match_payload:
                        continue

                    current_batch, current_batch_count, ok = cls._ensure_batch(
                        batch=current_batch,
                        current_count=current_batch_count,
                        batch_size=size,
                        job_id=job_id,
                        stats=stats,
                        max_batches=max_batches,
                    )
                    if not ok:
                        stop_requested = True
                        break

                    candidate = CommunityScoutCandidate(
                        batch_id=current_batch.id,
                        organization_id=snapshot['organization_id'],
                        inventory_item_id=snapshot['id'],
                        item_snapshot_json=snapshot,
                        classification=match_payload['classification'],
                        match_scores=match_payload['match'],
                        sensitivity_flags=match_payload['sensitivity'],
                    )
                    db.session.add(candidate)
                    current_batch_count += 1
                    stats['candidates_created'] += 1

                    if current_batch_count >= size:
                        current_batch = None
                        current_batch_count = 0

                db.session.commit()

                if stop_requested:
                    break

                if max_batches and stats['batches_created'] >= max_batches and not current_batch:
                    break

            job_state.last_run_at = TimezoneUtils.utc_now()
            job_state.lock_owner = None
            job_state.lock_expires_at = None
            job_state.last_error = None
            stats['read_source'] = cls._last_data_source
            db.session.commit()
            duration = perf_counter() - start_clock
            cls._log_job_stats(stats, duration)
            return stats
        except Exception as exc:
            db.session.rollback()
            job_state.last_error = str(exc)
            job_state.lock_owner = None
            job_state.lock_expires_at = None
            job_state.last_run_at = TimezoneUtils.utc_now()
            db.session.commit()
            stats['read_source'] = cls._last_data_source
            stats['error'] = str(exc)
            duration = perf_counter() - start_clock
            cls._log_job_stats(stats, duration)
            logger.exception("Community Scout batch generation failed: %s", exc)
            raise

    @classmethod
    def _ensure_batch(
        cls,
        batch: CommunityScoutBatch | None,
        current_count: int,
        batch_size: int,
        job_id: str,
        stats: Dict[str, Any],
        max_batches: int | None,
    ) -> tuple[CommunityScoutBatch | None, int, bool]:
        if batch and current_count < batch_size:
            return batch, current_count, True

        if max_batches and stats['batches_created'] >= max_batches:
            return None, current_count, False

        new_batch = CommunityScoutBatch(status='pending', generated_by_job_id=job_id)
        db.session.add(new_batch)
        db.session.flush()
        stats['batches_created'] += 1
        return new_batch, 0, True

    @classmethod
    def _candidate_exists(cls, inventory_item_id: int) -> bool:
        existing = (
            CommunityScoutCandidate.query.filter(
                CommunityScoutCandidate.inventory_item_id == inventory_item_id,
                CommunityScoutCandidate.state == 'open',
            )
            .with_entities(CommunityScoutCandidate.id)
            .first()
        )
        return existing is not None

    @classmethod
    def _fetch_inventory_page(cls, after_id: int, limit: int) -> List[Dict[str, Any]]:
        params = {'after_id': after_id, 'limit': limit}
        engine = cls._get_read_engine()
        if engine:
            cls._last_data_source = 'replica'
            with engine.connect() as conn:
                result = conn.execute(cls.INVENTORY_QUERY, params)
                return [dict(row) for row in result.mappings()]
        cls._last_data_source = 'primary'
        result = db.session.execute(cls.INVENTORY_QUERY, params)
        return [dict(row) for row in result.mappings()]

    @classmethod
    def _get_read_engine(cls) -> Engine | None:
        if cls._read_engine is not None:
            return cls._read_engine
        dsn = cls._replica_dsn()
        if not dsn:
            return None
        try:
            cls._read_engine = create_engine(dsn, pool_pre_ping=True)
        except Exception as exc:
            logger.warning("Community Scout unable to create read replica engine: %s", exc)
            cls._read_engine = None
        return cls._read_engine

    @classmethod
    def _build_snapshot(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        normalized_name = cls._normalize(row.get('name', ''))
        tokens = cls._tokenize(normalized_name)
        translated_tokens = cls._translate_tokens(tokens)
        combined_tokens = tokens.union(translated_tokens)
        normalized_inci = cls._normalize(row.get('inci_name', '') or '')

        return {
            'id': row['id'],
            'organization_id': row.get('organization_id'),
            'organization_name': row.get('organization_name'),
            'name': row.get('name'),
            'normalized_name': normalized_name,
            'tokens': sorted(combined_tokens),
            'type': (row.get('type') or 'ingredient').lower(),
            'unit': row.get('unit'),
            'quantity': row.get('quantity'),
            'density': row.get('density'),
            'inci_name': row.get('inci_name'),
            'normalized_inci': normalized_inci or None,
            'created_at': row.get('created_at').isoformat() if row.get('created_at') else None,
            'updated_at': row.get('updated_at').isoformat() if row.get('updated_at') else None,
        }

    @classmethod
    def _build_global_catalog(cls) -> 'CatalogBundle':
        entries: List[GlobalCatalogEntry] = []
        alias_index: dict[str, list[GlobalCatalogEntry]] = defaultdict(list)
        name_index: dict[str, list[GlobalCatalogEntry]] = defaultdict(list)
        inci_index: dict[str, list[GlobalCatalogEntry]] = defaultdict(list)

        items = (
            GlobalItem.query.filter(GlobalItem.is_archived != True)
            .options(joinedload(GlobalItem.ingredient_category))
            .all()
        )

        for item in items:
            normalized_name = cls._normalize(item.name)
            tokens = cls._tokenize(normalized_name)
            aliases = item.aliases or []
            normalized_aliases = [cls._normalize(a) for a in aliases if a]
            alias_tokens = [cls._tokenize(alias) for alias in normalized_aliases]
            normalized_inci = cls._normalize(item.inci_name or '')

            entry = GlobalCatalogEntry(
                id=item.id,
                name=item.name,
                normalized_name=normalized_name,
                normalized_tokens=tokens,
                item_type=(item.item_type or 'ingredient').lower(),
                default_unit=item.default_unit,
                density=item.density,
                category_id=item.ingredient_category_id,
                normalized_inci=normalized_inci or None,
                aliases=aliases,
                normalized_aliases=normalized_aliases,
                normalized_alias_tokens=alias_tokens,
            )

            entries.append(entry)
            name_index[normalized_name].append(entry)
            if normalized_inci:
                inci_index[normalized_inci].append(entry)
            for alias_norm in normalized_aliases:
                if alias_norm:
                    alias_index[alias_norm].append(entry)

        return CatalogBundle(entries, name_index, alias_index, inci_index)

    @classmethod
    def _evaluate_snapshot(cls, snapshot: Dict[str, Any], catalog: 'CatalogBundle') -> Optional[Dict[str, Any]]:
        normalized_name = snapshot['normalized_name']
        tokens = set(snapshot['tokens'])
        top_matches: List[Dict[str, Any]] = []
        sensitivity_flags: List[Dict[str, Any]] = []
        seen_ids: set[int] = set()

        # Exact matches
        for entry in catalog.name_index.get(normalized_name, []):
            top_matches.append(cls._build_match(entry, 1.0, 'exact'))
            seen_ids.add(entry.id)

        # Alias matches
        for entry in catalog.alias_index.get(normalized_name, []):
            top_matches.append(cls._build_match(entry, 0.98, 'aka'))
            seen_ids.add(entry.id)
            if normalized_name in cls.SENSITIVE_ALIAS_TERMS:
                sensitivity_flags.append({
                    'global_item_id': entry.id,
                    'alias_used': snapshot['name'],
                    'reason': 'flagged_alias',
                })

        # INCI matches
        normalized_inci = snapshot.get('normalized_inci')
        if normalized_inci:
            for entry in catalog.inci_index.get(normalized_inci, []):
                if entry.id in seen_ids:
                    continue
                top_matches.append(cls._build_match(entry, 0.95, 'inci'))
                seen_ids.add(entry.id)

        # Token overlap + fuzzy scoring
        for entry in catalog.entries:
            if entry.id in seen_ids:
                continue

            if entry.item_type != snapshot['type']:
                continue

            overlap_score = cls._token_overlap(tokens, entry.normalized_tokens)
            alias_overlap_score = 0.0
            if entry.normalized_alias_tokens:
                alias_overlap_score = max(
                    cls._token_overlap(tokens, alias_tokens)
                    for alias_tokens in entry.normalized_alias_tokens
                )
            fuzzy_score = cls._fuzzy_score(normalized_name, entry.normalized_name)

            candidates = [
                ('partial', overlap_score),
                ('partial_alias', alias_overlap_score),
                ('phonetic', fuzzy_score),
            ]

            for match_type, score in candidates:
                if score < cls.MIN_FUZZY_THRESHOLD:
                    continue
                normalized_type = 'partial' if match_type == 'partial_alias' else match_type
                top_matches.append(cls._build_match(entry, float(score), normalized_type))
                seen_ids.add(entry.id)
                break

        if not top_matches:
            return None

        top_matches.sort(key=lambda m: (-m['score'], m['name']))
        classification = 'unique'
        top_score = top_matches[0]['score']
        top_type = top_matches[0]['match_type']
        if top_type in cls.HIGH_TRUST_MATCHES or top_score >= cls.REVIEW_SCORE_THRESHOLD:
            classification = 'needs_review'

        return {
            'classification': classification,
            'match': {'top_matches': top_matches[:5]},
            'sensitivity': sensitivity_flags or None,
        }

    @classmethod
    def _build_match(cls, entry: GlobalCatalogEntry, score: float, match_type: str) -> Dict[str, Any]:
        return {
            'global_item_id': entry.id,
            'name': entry.name,
            'match_type': match_type,
            'score': round(score, 3),
            'item_type': entry.item_type,
            'default_unit': entry.default_unit,
        }

    @classmethod
    def _token_overlap(cls, item_tokens: Iterable[str], reference_tokens: Iterable[str]) -> float:
        item_set = set(t for t in item_tokens if t)
        ref_set = set(t for t in reference_tokens if t)
        if not item_set or not ref_set:
            return 0.0
        common = len(item_set & ref_set)
        return common / float(max(len(item_set), len(ref_set)))

    @classmethod
    def _fuzzy_score(cls, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    @classmethod
    def _normalize(cls, value: str | None) -> str:
        if not value:
            return ''
        normalized = unicodedata.normalize('NFKD', value)
        normalized = normalized.encode('ascii', 'ignore').decode('ascii')
        normalized = normalized.lower()
        normalized = re.sub(r'[^a-z0-9]+', ' ', normalized).strip()
        return re.sub(r'\s+', ' ', normalized)

    @classmethod
    def _tokenize(cls, normalized_value: str) -> set[str]:
        if not normalized_value:
            return set()
        return {token for token in normalized_value.split(' ') if token}

    @classmethod
    def _translate_tokens(cls, tokens: Iterable[str]) -> set[str]:
        translated = set()
        for token in tokens:
            mapped = cls.COMMON_TRANSLATIONS.get(token)
            if mapped:
                translated.add(mapped)
        return translated

    # ----- Candidate Actions -----

    @classmethod
    def promote_candidate(cls, candidate_id: int, payload: Dict[str, Any], acting_user_id: int) -> Dict[str, Any]:
        candidate = cls._get_candidate(candidate_id)
        if candidate.state != 'open':
            raise ValueError("Candidate already resolved.")

        cls._mark_batch_in_review(candidate.batch_id)

        name = (payload.get('name') or candidate.item_snapshot_json.get('name') or '').strip()
        item_type = (payload.get('item_type') or candidate.item_snapshot_json.get('type') or 'ingredient').strip()
        default_unit = payload.get('default_unit') or candidate.item_snapshot_json.get('unit')

        if not name:
            raise ValueError("Global item name is required.")

        aliases = payload.get('aliases')
        if isinstance(aliases, str):
            aliases = [aliases]
        if not aliases:
            fallback_alias = candidate.item_snapshot_json.get('name')
            aliases = [fallback_alias] if fallback_alias else []

        global_item = GlobalItem(
            name=name,
            item_type=item_type,
            default_unit=default_unit,
            density=payload.get('density') or candidate.item_snapshot_json.get('density'),
            inci_name=payload.get('inci_name') or candidate.item_snapshot_json.get('inci_name'),
            aliases=aliases,
        )
        db.session.add(global_item)
        db.session.flush()

        cls._link_inventory_item(candidate.inventory_item_id, global_item, acting_user_id)

        candidate.mark_resolved(
            resolution_payload={
                'action': 'promote',
                'global_item_id': global_item.id,
                'payload': payload,
            },
            resolved_by_user_id=acting_user_id,
        )

        cls._maybe_close_batch(candidate.batch_id)
        db.session.commit()
        return {'global_item_id': global_item.id}

    @classmethod
    def link_candidate(cls, candidate_id: int, global_item_id: int, acting_user_id: int) -> Dict[str, Any]:
        candidate = cls._get_candidate(candidate_id)
        if candidate.state != 'open':
            raise ValueError("Candidate already resolved.")

        cls._mark_batch_in_review(candidate.batch_id)

        global_item = db.session.get(GlobalItem, int(global_item_id))
        if not global_item:
            raise ValueError("Global item not found.")

        cls._link_inventory_item(candidate.inventory_item_id, global_item, acting_user_id)

        candidate.mark_resolved(
            resolution_payload={
                'action': 'link',
                'global_item_id': global_item_id,
            },
            resolved_by_user_id=acting_user_id,
        )

        cls._maybe_close_batch(candidate.batch_id)
        db.session.commit()
        return {'linked': True}

    @classmethod
    def reject_candidate(cls, candidate_id: int, reason: str, acting_user_id: int) -> Dict[str, Any]:
        candidate = cls._get_candidate(candidate_id)
        if candidate.state != 'open':
            raise ValueError("Candidate already resolved.")

        cls._mark_batch_in_review(candidate.batch_id)

        candidate.mark_resolved(
            resolution_payload={
                'action': 'reject',
                'reason': reason,
            },
            resolved_by_user_id=acting_user_id,
        )
        cls._maybe_close_batch(candidate.batch_id)
        db.session.commit()
        return {'rejected': True}

    @classmethod
    def flag_candidate(cls, candidate_id: int, flag_payload: Dict[str, Any], acting_user_id: int) -> Dict[str, Any]:
        candidate = cls._get_candidate(candidate_id)
        cls._mark_batch_in_review(candidate.batch_id)
        flags = candidate.sensitivity_flags or []
        flags.append({
            'flagged_by': acting_user_id,
            'payload': flag_payload,
            'flagged_at': TimezoneUtils.utc_now().isoformat(),
        })
        candidate.sensitivity_flags = flags
        db.session.commit()
        return {'flagged': True}

    # ----- Batch retrieval for UI -----

    @classmethod
    def get_next_batch(cls) -> Optional[CommunityScoutBatch]:
        return (
            CommunityScoutBatch.query.filter(
                CommunityScoutBatch.status == 'pending',
            )
            .order_by(CommunityScoutBatch.generated_at.asc())
            .first()
        )

    @classmethod
    def serialize_batch(cls, batch: CommunityScoutBatch | None) -> Optional[Dict[str, Any]]:
        if not batch:
            return None

        return {
            'id': batch.id,
            'status': batch.status,
            'generated_at': batch.generated_at.isoformat() if batch.generated_at else None,
            'claimed_by_user_id': batch.claimed_by_user_id,
            'claimed_at': batch.claimed_at.isoformat() if batch.claimed_at else None,
            'metadata': {
                'pending': sum(1 for c in batch.candidates if c.state == 'open'),
                'resolved': sum(1 for c in batch.candidates if c.state != 'open'),
            },
            'candidates': [cls._serialize_candidate(c) for c in batch.candidates],
        }

    @classmethod
    def _serialize_candidate(cls, candidate: CommunityScoutCandidate) -> Dict[str, Any]:
        snapshot = candidate.item_snapshot_json or {}
        return {
            'id': candidate.id,
            'state': candidate.state,
            'classification': candidate.classification,
            'snapshot': snapshot,
            'match_scores': candidate.match_scores or {},
            'sensitivity_flags': candidate.sensitivity_flags or [],
            'resolved_at': candidate.resolved_at.isoformat() if candidate.resolved_at else None,
            'resolved_by': candidate.resolved_by,
        }

    # ----- Helpers -----

    @classmethod
    def _get_or_create_job_state(cls, job_name: str) -> CommunityScoutJobState:
        state = db.session.get(CommunityScoutJobState, job_name)
        if not state:
            state = CommunityScoutJobState(job_name=job_name)
            db.session.add(state)
            db.session.commit()
        return state

    @classmethod
    def _get_candidate(cls, candidate_id: int) -> CommunityScoutCandidate:
        candidate = db.session.get(CommunityScoutCandidate, int(candidate_id))
        if not candidate:
            raise ValueError("Candidate not found.")
        return candidate

    @classmethod
    def _mark_batch_in_review(cls, batch_id: int | None) -> None:
        if not batch_id:
            return
        batch = db.session.get(CommunityScoutBatch, batch_id)
        if not batch:
            return
        if batch.status == 'pending':
            batch.status = 'in_review'
            batch.claimed_at = TimezoneUtils.utc_now()

    @classmethod
    def _maybe_close_batch(cls, batch_id: int | None) -> None:
        if not batch_id:
            return
        batch = db.session.get(CommunityScoutBatch, batch_id)
        if not batch:
            return
        if any(c.state == 'open' for c in batch.candidates):
            return
        batch.mark_completed()

    @classmethod
    def _link_inventory_item(cls, inventory_item_id: int | None, global_item: GlobalItem, acting_user_id: int) -> None:
        if not inventory_item_id:
            return
        inventory_item = db.session.get(InventoryItem, inventory_item_id)
        if not inventory_item:
            return
        if inventory_item.global_item_id:
            return

        if not GlobalLinkSuggestionService.is_pair_compatible(global_item.default_unit, inventory_item.unit):
            return

        old_name = inventory_item.name
        inventory_item.name = global_item.name
        inventory_item.global_item_id = global_item.id
        inventory_item.density = inventory_item.density or global_item.density
        if inventory_item.type == 'ingredient':
            inventory_item.inci_name = global_item.inci_name or inventory_item.inci_name

        history_event = UnifiedInventoryHistory(
            inventory_item_id=inventory_item.id,
            change_type='link_global',
            quantity_change=0.0,
            unit=inventory_item.unit or 'count',
            notes=f"Linked via Community Scout to GlobalItem '{global_item.name}' (was '{old_name}')",
            created_by=acting_user_id,
            organization_id=inventory_item.organization_id,
        )
        db.session.add(history_event)

    @classmethod
    def check_replica_health(cls) -> Dict[str, Any]:
        dsn = cls._replica_dsn()
        if not dsn:
            return {
                'status': 'missing',
                'message': 'COMMUNITY_SCOUT_READ_DSN is not configured; job will read from the primary database.',
                'severity': 'warning',
            }
        try:
            engine = cls._get_read_engine()
            if not engine:
                return {
                    'status': 'error',
                    'message': 'Replica DSN configured but engine could not be initialized.',
                    'severity': 'danger',
                }
            start = perf_counter()
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            latency = (perf_counter() - start) * 1000
            return {
                'status': 'ok',
                'latency_ms': round(latency, 2),
            }
        except Exception as exc:
            logger.warning("Community Scout replica health check failed: %s", exc)
            return {
                'status': 'error',
                'message': str(exc),
                'severity': 'danger',
            }

    @classmethod
    def _log_job_stats(cls, stats: Dict[str, Any], duration: float) -> None:
        payload = dict(stats)
        payload['duration_seconds'] = round(duration, 3)
        log_target = current_app.logger if current_app else logger
        log_target.info("Community Scout job completed: %s", payload)

    @classmethod
    def _has_replica_config(cls) -> bool:
        return bool(cls._replica_dsn())

    @staticmethod
    def _replica_dsn() -> str | None:
        config = getattr(current_app, 'config', {}) if current_app else {}
        dsn = config.get('COMMUNITY_SCOUT_READ_DSN')
        if not dsn:
            dsn = os.environ.get('COMMUNITY_SCOUT_READ_DSN')
        return dsn


@dataclass(slots=True)
class CatalogBundle:
    entries: List[GlobalCatalogEntry]
    name_index: dict[str, List[GlobalCatalogEntry]]
    alias_index: dict[str, List[GlobalCatalogEntry]]
    inci_index: dict[str, List[GlobalCatalogEntry]]

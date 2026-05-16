"""TrainPlex Template Gallery + Project Wizard endpoints — Phase 1 Step 4.2-2.

Replaces the upstream LS "30+ field scary Create Project form" with the data
the new 3-step React wizard needs:

    GET  /api/v1/admin/templates/catalog   → merged template list for Step 1
    POST /api/v1/admin/projects/wizard     → minimal project create for Step 3

Catalog merges two sources:

* **TrainPlex India custom** templates on disk at
  ``backend/data/ls_templates/trainplex_india/*/meta.json`` (10 of them, see
  Step 2.2). Each one is marked ``trainplex_custom=true`` and carries Hindi
  title/description so the wizard renders bilingual cards.
* **LS native** templates — Phase 1 ships a hardcoded list of 50 well-known
  upstream templates spread across 9 categories (Text/NLP 8, Image 11, Audio
  7, Video 4, Conversational 5, LLM 4, Structured 4, TimeSeries 5, Ranking 3
  → 51, but we trim one duplicate to land on the planned ~50). Full schema
  loading (config.xml etc.) is Phase 2 — see ``_NATIVE_TEMPLATES`` TODO.

Both endpoints are admin-only via ``@require_role(['admin'])`` so trainers /
reviewers / QA-leads get a clean 403 surface.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.core.cache import cache
from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role

logger = logging.getLogger(__name__)

# Map common CSV column names → LS task data keys. Anything not in this map
# is passed through under its own column name so any template's $variables
# work out of the box. Keep this short + obvious — founder picks the column
# names that match their template, we just rename a few well-known aliases.
_CSV_ALIAS = {
    'image_url': 'image',
    'audio_url': 'audio',
    'video_url': 'video',
    'question': 'prompt',
    'answer': 'response',
}

# Hard cap so an admin can't accidentally DoS the wizard by uploading a 1M
# row CSV through the inline JSON body. Real bulk import goes through the
# regular LS import storage flow; the wizard is for the "I have a tiny
# starter CSV" case.
_WIZARD_CSV_MAX_ROWS = 5000


# ---------------------------------------------------------------------------
# Path discovery for the on-disk TrainPlex India custom templates.
# Mirror of label_studio/tests/test_trainplex_templates.py so behaviour stays
# consistent: env var override → repo-relative fallback.
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
# label_studio/core/views_template_gallery.py → core/ → label_studio/ → repo
_REPO_ROOT = _THIS_FILE.parent.parent.parent
_DEFAULT_TEMPLATES_DIR = (
    _REPO_ROOT / 'backend' / 'data' / 'ls_templates' / 'trainplex_india'
)


def _trainplex_templates_dir() -> Path:
    """Resolve the TrainPlex India templates directory.

    Order:
    1. ``TRAINPLEX_TEMPLATES_DIR`` env var (used by tests + container layouts).
    2. Repo-relative default at ``backend/data/ls_templates/trainplex_india/``.
    """
    override = os.environ.get('TRAINPLEX_TEMPLATES_DIR')
    if override:
        return Path(override)
    return _DEFAULT_TEMPLATES_DIR


# ---------------------------------------------------------------------------
# LS native templates — Codex audit M6 (2026-05-16): auto-discovered.
#
# Strategy:
#   1. Primary source: walk ``label_studio/annotation_templates/<group>/<slug>/``
#      and read each ``config.yml`` (or ``config.xml`` fallback) to extract
#      title + category + label_config. Discovered list is cached in
#      Django's cache for 1h (key = ``ls_templates:native:v1``); ``lru_cache``
#      on the inner walker gives us a process-local fast path.
#   2. Fallback list: the static ~50-entry catalog below is preserved as a
#      hard backstop for tests + cold starts where the filesystem walk yields
#      nothing (e.g. unit tests that don't ship the annotation_templates dir).
#
# Discovery contract:
#   - id: stable, derived from "{group_slug}__{template_slug}" (snake_case).
#   - title: from config.yml ``title`` key; falls back to slug.title().
#   - category: from config.yml ``group`` key; falls back to dir name.
#   - label_config: from the inline ``config:`` block or sibling config.xml.
#
# Cache invalidation: any call to ``invalidate_native_templates_cache()``
# clears both the lru_cache and the Django cache. Call this from a manage.py
# command after refreshing the upstream templates folder, or just wait the
# 1h TTL — neither is hot-path code.
# ---------------------------------------------------------------------------

_NATIVE_CACHE_KEY = 'ls_templates:native:v1'
_NATIVE_CACHE_TTL = 3600  # 1h


def _native_annotation_templates_dir() -> Path:
    """Resolve the LS native annotation_templates root.

    Order:
    1. ``LS_NATIVE_TEMPLATES_DIR`` env var (tests + non-standard container
       layouts).
    2. Sibling of this file: ``label_studio/annotation_templates/`` — works
       both inside the running container and in a dev checkout because the
       upstream LS source ships that directory.
    """
    override = os.environ.get('LS_NATIVE_TEMPLATES_DIR')
    if override:
        return Path(override)
    # _THIS_FILE = .../label_studio/core/views_template_gallery.py
    #          .parent = .../label_studio/core
    #          .parent.parent = .../label_studio
    return _THIS_FILE.parent.parent / 'annotation_templates'


def _slugify(value: str) -> str:
    """Snake_case slug for stable template ids — letters, digits, underscores."""
    value = value.strip().lower()
    value = re.sub(r'[^a-z0-9]+', '_', value)
    return value.strip('_')


def _parse_minimal_yaml(text: str) -> Dict[str, Any]:
    """Parse the tiny subset of YAML used by upstream LS template config.yml.

    Each file has top-level scalar keys (title, type, group, image) and two
    block keys ``details`` / ``config`` that use the ``|`` (literal block)
    scalar style. Pulling in PyYAML just for this would be heavy, so we hand-
    roll a minimal parser keyed on the actual upstream format.

    Returns an empty dict on any parse hiccup — the caller falls back to slug
    naming so a malformed file never breaks the catalog.
    """
    out: Dict[str, Any] = {}
    if not text:
        return out
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue
        # Match "key: value" or "key: |"
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$', line)
        if not m or line.startswith((' ', '\t')):
            i += 1
            continue
        key = m.group(1)
        rest = m.group(2).strip()
        if rest == '|':
            # Literal block — collect indented continuation lines.
            i += 1
            block_lines: List[str] = []
            # Detect the block indent from the first non-empty line.
            indent: Optional[int] = None
            while i < n:
                bl = lines[i]
                if bl.strip() == '':
                    block_lines.append('')
                    i += 1
                    continue
                stripped_indent = len(bl) - len(bl.lstrip(' \t'))
                if indent is None:
                    if stripped_indent == 0:
                        break  # block ended without indent
                    indent = stripped_indent
                if stripped_indent < (indent or 0):
                    break
                block_lines.append(bl[indent:])
                i += 1
            out[key] = '\n'.join(block_lines).rstrip()
            continue
        # Inline scalar value — strip surrounding quotes if present.
        if rest and rest[0] in ('"', "'") and rest[-1:] == rest[0]:
            rest = rest[1:-1]
        out[key] = rest
        i += 1
    return out


def _category_from_group_dir(dirname: str) -> str:
    """Map an annotation_templates/ subdirectory to a human category label."""
    mapping = {
        'natural-language-processing': 'Text / NLP',
        'computer-vision': 'Image',
        'audio-speech-processing': 'Audio',
        'videos': 'Video',
        'conversational-ai': 'Conversational',
        'chat': 'Conversational',
        'generative-ai': 'LLM',
        'structured-data-parsing': 'Structured',
        'time-series-analysis': 'TimeSeries',
        'ranking-and-scoring': 'Ranking',
        'community-contributions': 'Community',
    }
    return mapping.get(dirname, dirname.replace('-', ' ').title())


@lru_cache(maxsize=1)
def _discover_native_templates() -> List[Dict[str, Any]]:
    """Walk the LS native annotation_templates dir + return catalog cards.

    Process-local cache (lru_cache) avoids re-walking on every request inside
    one worker process. The outer ``_native_templates()`` wraps this with the
    Django cache so multi-worker deployments share a single warm result for
    the cache TTL.
    """
    out: List[Dict[str, Any]] = []
    root = _native_annotation_templates_dir()
    if not root.is_dir():
        logger.warning('LS native annotation_templates dir not found at %s', root)
        return out

    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir() or group_dir.name.startswith('.'):
            continue
        category = _category_from_group_dir(group_dir.name)
        for tpl_dir in sorted(group_dir.iterdir()):
            if not tpl_dir.is_dir() or tpl_dir.name.startswith('.'):
                continue
            yml = tpl_dir / 'config.yml'
            xml = tpl_dir / 'config.xml'
            title: Optional[str] = None
            label_config = ''
            group_label = ''
            if yml.is_file():
                try:
                    meta = _parse_minimal_yaml(yml.read_text(encoding='utf-8'))
                    title = (meta.get('title') or '').strip() or None
                    group_label = (meta.get('group') or '').strip()
                    label_config = (meta.get('config') or '').strip()
                except OSError as exc:
                    logger.warning('Skipping %s: %s', yml, exc)
                    continue
            elif xml.is_file():
                try:
                    label_config = xml.read_text(encoding='utf-8').strip()
                    # Validate XML — bad config.xml means a broken template.
                    ET.fromstring(label_config)
                except (OSError, ET.ParseError) as exc:
                    logger.warning('Skipping %s: %s', xml, exc)
                    continue
            else:
                # No config of any kind — skip silently; not all subdirs are
                # templates (e.g. images/, README dirs).
                continue
            slug = tpl_dir.name
            tid = f'{_slugify(group_dir.name)}__{_slugify(slug)}'
            display_title = title or slug.replace('-', ' ').title()
            out.append(
                {
                    'id': tid,
                    'title': display_title,
                    'category': group_label or category,
                    'label_config': label_config,
                    'source_dir': str(tpl_dir),
                }
            )
    return out


def _native_templates() -> List[Dict[str, Any]]:
    """Public accessor: Django-cached wrapper around ``_discover_native_templates``.

    Falls back to the static ``_NATIVE_TEMPLATES_FALLBACK`` list if discovery
    returns zero entries (e.g. annotation_templates dir not mounted in a
    minimal test container). This guarantees the catalog endpoint is never
    empty for the wizard.
    """
    cached = cache.get(_NATIVE_CACHE_KEY)
    if cached:
        return cached
    discovered = _discover_native_templates()
    if not discovered:
        # Tests + minimal containers — return the static fallback so the
        # wizard always renders ~50 cards.
        return _NATIVE_TEMPLATES_FALLBACK
    cache.set(_NATIVE_CACHE_KEY, discovered, _NATIVE_CACHE_TTL)
    return discovered


def invalidate_native_templates_cache() -> None:
    """Clear both the lru_cache and the Django cache for native templates.

    Call from a manage.py command after editing annotation_templates/, or
    from a future filesystem-watcher to invalidate eagerly.
    """
    _discover_native_templates.cache_clear()
    cache.delete(_NATIVE_CACHE_KEY)


# ---------------------------------------------------------------------------
# Static fallback — preserved from the pre-M6 hardcoded list so unit tests
# that stub the filesystem still see a healthy native catalog. Treat as a
# safety net only; production reads come from ``_discover_native_templates``.
# ---------------------------------------------------------------------------

_NATIVE_TEMPLATES_FALLBACK: List[Dict[str, Any]] = [
    # Text / NLP (8)
    {'id': 'text_classification', 'title': 'Text Classification', 'category': 'Text / NLP'},
    {'id': 'named_entity_recognition', 'title': 'Named Entity Recognition', 'category': 'Text / NLP'},
    {'id': 'sentiment_analysis', 'title': 'Sentiment Analysis', 'category': 'Text / NLP'},
    {'id': 'text_summarization', 'title': 'Text Summarization', 'category': 'Text / NLP'},
    {'id': 'question_answering', 'title': 'Question Answering', 'category': 'Text / NLP'},
    {'id': 'relation_extraction', 'title': 'Relation Extraction', 'category': 'Text / NLP'},
    {'id': 'text_taxonomy', 'title': 'Text Taxonomy', 'category': 'Text / NLP'},
    {'id': 'machine_translation', 'title': 'Machine Translation', 'category': 'Text / NLP'},
    # Image / Computer Vision (10)
    {'id': 'image_classification', 'title': 'Image Classification', 'category': 'Image'},
    {'id': 'object_detection_bbox', 'title': 'Object Detection (Bounding Boxes)', 'category': 'Image'},
    {'id': 'semantic_segmentation_polygons', 'title': 'Semantic Segmentation (Polygons)', 'category': 'Image'},
    {'id': 'semantic_segmentation_masks', 'title': 'Semantic Segmentation (Masks)', 'category': 'Image'},
    {'id': 'keypoint_labeling', 'title': 'Keypoint Labeling', 'category': 'Image'},
    {'id': 'image_captioning', 'title': 'Image Captioning', 'category': 'Image'},
    {'id': 'optical_character_recognition', 'title': 'Optical Character Recognition', 'category': 'Image'},
    {'id': 'visual_question_answering', 'title': 'Visual Question Answering', 'category': 'Image'},
    {'id': 'medical_image_classification', 'title': 'Medical Image Classification', 'category': 'Image'},
    {'id': 'inventory_tracking', 'title': 'Inventory Tracking', 'category': 'Image'},
    # Audio / Speech (7)
    {'id': 'audio_classification', 'title': 'Audio Classification', 'category': 'Audio'},
    {'id': 'audio_transcription', 'title': 'Audio Transcription', 'category': 'Audio'},
    {'id': 'speaker_segmentation', 'title': 'Speaker Segmentation', 'category': 'Audio'},
    {'id': 'sound_event_detection', 'title': 'Sound Event Detection', 'category': 'Audio'},
    {'id': 'audio_emotion_recognition', 'title': 'Audio Emotion Recognition', 'category': 'Audio'},
    {'id': 'phoneme_alignment', 'title': 'Phoneme Alignment', 'category': 'Audio'},
    {'id': 'audio_quality_rating', 'title': 'Audio Quality Rating', 'category': 'Audio'},
    # Video (4)
    {'id': 'video_classification', 'title': 'Video Classification', 'category': 'Video'},
    {'id': 'video_object_tracking', 'title': 'Video Object Tracking', 'category': 'Video'},
    {'id': 'video_segmentation', 'title': 'Video Segmentation', 'category': 'Video'},
    {'id': 'video_timeline_labeling', 'title': 'Video Timeline Labeling', 'category': 'Video'},
    # Conversational AI (5)
    {'id': 'intent_classification', 'title': 'Intent Classification', 'category': 'Conversational'},
    {'id': 'slot_filling', 'title': 'Slot Filling', 'category': 'Conversational'},
    {'id': 'dialogue_evaluation', 'title': 'Dialogue Evaluation', 'category': 'Conversational'},
    {'id': 'chatbot_response_ranking', 'title': 'Chatbot Response Ranking', 'category': 'Conversational'},
    {'id': 'utterance_quality_rating', 'title': 'Utterance Quality Rating', 'category': 'Conversational'},
    # LLM / Generative (4)
    {'id': 'llm_rlhf_pairwise', 'title': 'LLM RLHF Pairwise Comparison', 'category': 'LLM'},
    {'id': 'llm_response_evaluation', 'title': 'LLM Response Evaluation', 'category': 'LLM'},
    {'id': 'llm_supervised_fine_tuning', 'title': 'LLM Supervised Fine-Tuning', 'category': 'LLM'},
    {'id': 'llm_red_team', 'title': 'LLM Red Team Probe', 'category': 'LLM'},
    # Structured (4)
    {'id': 'tabular_classification', 'title': 'Tabular Classification', 'category': 'Structured'},
    {'id': 'tabular_regression', 'title': 'Tabular Regression', 'category': 'Structured'},
    {'id': 'csv_row_review', 'title': 'CSV Row Review', 'category': 'Structured'},
    {'id': 'json_schema_validation', 'title': 'JSON Schema Validation', 'category': 'Structured'},
    # Time Series (5)
    {'id': 'time_series_classification', 'title': 'Time Series Classification', 'category': 'TimeSeries'},
    {'id': 'time_series_anomaly_detection', 'title': 'Time Series Anomaly Detection', 'category': 'TimeSeries'},
    {'id': 'time_series_segmentation', 'title': 'Time Series Segmentation', 'category': 'TimeSeries'},
    {'id': 'time_series_forecasting_review', 'title': 'Time Series Forecast Review', 'category': 'TimeSeries'},
    {'id': 'sensor_event_labeling', 'title': 'Sensor Event Labeling', 'category': 'TimeSeries'},
    # Ranking & Scoring (3)
    {'id': 'pairwise_ranking', 'title': 'Pairwise Ranking', 'category': 'Ranking'},
    {'id': 'search_result_relevance', 'title': 'Search Result Relevance', 'category': 'Ranking'},
    {'id': 'recommendation_quality', 'title': 'Recommendation Quality', 'category': 'Ranking'},
]

# Back-compat alias used by callers + tests that import the old name. Now
# points at the static fallback list; production callers should prefer
# ``_native_templates()`` for the auto-discovered, cached view.
_NATIVE_TEMPLATES = _NATIVE_TEMPLATES_FALLBACK


def _native_template_to_card(t: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a hardcoded LS-native entry to the catalog card shape.

    Phase 1: title_hi / description_hi are blank for native templates — the
    UI will fall back to the English title via t() lookup, which is fine for
    upstream-flavoured templates the founder team will localize selectively
    in Phase 2.
    """
    return {
        'id': t['id'],
        'title': t['title'],
        'title_hi': '',  # TODO Phase 2: localise the 50 native templates
        'category': t['category'],
        'description': '',
        'description_hi': '',
        'india_relevance': '',
        'thumbnail_url': None,
        'tier': 'bronze',  # native LS templates default to bronze entry tier
        'trainplex_custom': False,
    }


def _load_trainplex_india_templates() -> List[Dict[str, Any]]:
    """Read every ``meta.json`` under the TrainPlex India templates folder.

    Returns the cards sorted by id for deterministic API output. Files that
    fail to parse are logged + skipped so a single bad template never breaks
    the entire admin wizard.
    """
    out: List[Dict[str, Any]] = []
    tdir = _trainplex_templates_dir()
    if not tdir.is_dir():
        logger.warning('TrainPlex templates dir not found at %s', tdir)
        return out
    for sub in sorted(tdir.iterdir()):
        if not sub.is_dir():
            continue
        meta_path = sub / 'meta.json'
        if not meta_path.is_file():
            continue
        try:
            with meta_path.open(encoding='utf-8') as fh:
                meta = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning('Skipping template %s: meta.json error: %s', sub.name, exc)
            continue
        out.append(
            {
                'id': meta.get('id', sub.name),
                'title': meta.get('title', sub.name),
                'title_hi': meta.get('title_hi', ''),
                'category': meta.get('category', 'TrainPlex India'),
                'description': meta.get('description', ''),
                'description_hi': meta.get('description_hi', ''),
                'india_relevance': meta.get('india_relevance', ''),
                'thumbnail_url': meta.get('thumbnail_url'),
                'tier': meta.get('tier', 'bronze'),
                'trainplex_custom': bool(meta.get('trainplex_custom', True)),
            }
        )
    return out


def _build_catalog() -> Dict[str, Any]:
    """Build the merged catalog response — TrainPlex India first, then native.

    TrainPlex India templates come first so the wizard's Step 1 gallery
    naturally highlights "made for India" options before generic LS ones —
    this is the whole point of the fork. Caller doesn't depend on this order
    for correctness, but it's deterministic and tested.
    """
    india = _load_trainplex_india_templates()
    # M6 — auto-discovered native catalog via filesystem walk; falls back to
    # the static list if the annotation_templates dir is unavailable.
    native = [_native_template_to_card(t) for t in _native_templates()]
    items = india + native
    return {
        'count': len(items),
        'trainplex_count': len(india),
        'native_count': len(native),
        'items': items,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/admin/templates/catalog
# ---------------------------------------------------------------------------


class AdminTemplateCatalogAPI(APIView):
    """Admin-only template catalog for the Project Wizard Step 1 gallery.

    Merges the on-disk TrainPlex India custom templates with a hardcoded list
    of 50 LS native templates. Returns 403 for non-admins; 401 if unauth.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Project Wizard — Step 1 template catalog',
        description=(
            'Merged catalog of TrainPlex India custom templates + LS native '
            'templates for the admin Project Wizard. Admin role only.'
        ),
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        return Response(_build_catalog(), status=200)


# ---------------------------------------------------------------------------
# POST /api/v1/admin/templates/refresh
# Codex audit M6 (2026-05-16) — admin-only endpoint to clear the in-process
# lru_cache + Django cache so a freshly-mounted annotation_templates dir
# (or a newly dropped TrainPlex India template) is picked up without
# requiring a container restart. Returns the new counts so the operator
# can confirm the refresh actually changed something.
# ---------------------------------------------------------------------------


class AdminTemplateCatalogRefreshAPI(APIView):
    """POST /api/v1/admin/templates/refresh — admin-only cache buster.

    Clears both the process-local ``lru_cache`` on
    ``_discover_native_templates`` and the Django cache key
    ``ls_templates:native:v1`` used by ``_native_templates``, then immediately
    rebuilds the catalog so the response carries the post-refresh counts.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Project Wizard — refresh template catalog cache',
        description=(
            'Admin-only. Invalidates the native-template lru_cache + Django '
            'cache so the next /catalog read re-walks the filesystem.'
        ),
    )
    @require_role(['admin'])
    def post(self, request, *args, **kwargs):
        invalidate_native_templates_cache()
        catalog = _build_catalog()
        return Response(
            {
                'refreshed': True,
                'count': catalog['count'],
                'trainplex_count': catalog['trainplex_count'],
                'native_count': catalog['native_count'],
            },
            status=200,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/admin/projects/wizard
# ---------------------------------------------------------------------------


def _all_template_ids() -> set:
    # M6 — accept both auto-discovered ids and the static fallback ids so
    # legacy front-ends with cached id strings keep working through the
    # transition.
    return (
        {t['id'] for t in _native_templates()}
        | {t['id'] for t in _NATIVE_TEMPLATES_FALLBACK}
        | {t['id'] for t in _load_trainplex_india_templates()}
    )


def _load_template_label_config(template_id: str) -> str:
    """Return the LS ``label_config`` XML string for a known template_id.

    For TrainPlex India templates we read the real ``config.xml`` from disk so
    the labeling editor renders the actual annotation UI. For LS native ids
    we ship an empty ``<View></View>`` (Phase 2: load native config.xml from
    upstream LS install). Either way the project is created with a *valid*
    label_config so the founder doesn't see a crash when opening the project.

    Never raises — always returns at least ``<View></View>`` so the wizard
    create flow never aborts on a missing template file.
    """
    tdir = _trainplex_templates_dir() / template_id / 'config.xml'
    if tdir.is_file():
        try:
            return tdir.read_text(encoding='utf-8')
        except OSError as exc:  # pragma: no cover — defensive
            logger.warning(
                'Failed to read template config %s: %s', tdir, exc,
            )
    # M6 — also try the auto-discovered native cache, which already carries
    # the inline label_config from config.yml or config.xml.
    for native in _native_templates():
        if native['id'] == template_id and native.get('label_config'):
            return native['label_config']
    return '<View></View>'


def _parse_csv_to_task_data(csv_text: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Parse a CSV string into a list of LS Task ``data`` dicts.

    Returns ``(rows, error_message)``. On success ``error_message`` is None.

    The column-name → ``data.<key>`` mapping is intentionally tiny — see
    ``_CSV_ALIAS`` above. Unknown columns pass through verbatim so a founder
    using a template that expects ``$cust_field_42`` can just put a column
    named ``cust_field_42`` in the CSV. No silent renames beyond the aliases.

    A header row is required; CSVs without a header are rejected because we
    have no way to map columns to LS data keys without column names.
    """
    if not csv_text or not csv_text.strip():
        return [], None  # empty CSV is fine — caller treats it as "no tasks"
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
    except csv.Error as exc:
        return [], f'CSV parse error: {exc}'
    if reader.fieldnames is None:
        return [], 'CSV is missing a header row'
    rows: List[Dict[str, Any]] = []
    for raw in reader:
        row: Dict[str, Any] = {}
        for col, value in raw.items():
            if col is None:
                continue
            key = _CSV_ALIAS.get(col.strip(), col.strip())
            if not key:
                continue
            row[key] = value
        if row:
            rows.append(row)
        if len(rows) >= _WIZARD_CSV_MAX_ROWS:
            return [], (
                f'CSV exceeds maximum of {_WIZARD_CSV_MAX_ROWS} rows for the '
                f'inline wizard upload. Use bulk import for larger batches.'
            )
    return rows, None


def _create_tasks_from_rows(
    project, rows: List[Dict[str, Any]], created_by,
) -> int:
    """Bulk-insert Task rows for a freshly created Project. Returns count.

    Uses ``Task.objects.create`` in a transaction so a partial CSV doesn't
    leave half-imported rows lingering if one row blows up.
    """
    if not rows:
        return 0
    from tasks.models import Task

    created = 0
    with transaction.atomic():
        for row in rows:
            Task.objects.create(
                project=project,
                data=row,
                updated_by=created_by,
            )
            created += 1
    return created


def _add_project_members(project, trainer_ids: List[int]) -> List[int]:
    """Add ProjectMember rows for each trainer id; return the ones actually added.

    Skips ids that don't resolve to a User. Existing memberships are left alone
    (get_or_create-style) so re-runs are idempotent.
    """
    if not trainer_ids:
        return []
    from django.contrib.auth import get_user_model
    from projects.models import ProjectMember

    User = get_user_model()
    valid_users = User.objects.filter(id__in=trainer_ids)
    added: List[int] = []
    for user in valid_users:
        _, created = ProjectMember.objects.get_or_create(
            project=project, user=user, defaults={'enabled': True},
        )
        if created:
            added.append(user.id)
    return added


class AdminProjectWizardCreateAPI(APIView):
    """Minimal admin project create from the wizard.

    Body
    ----
    {
      "template_id":         "aadhaar_ocr_validation",   # required
      "project_name":        "KYC Batch May 2026",       # required, alias: "title"
      "data_file_upload_id": "<file-storage-id>",        # optional, file-store ref
      "trainer_ids":         [5, 7, 12],                 # optional, assignee user ids
      "csv_data":            "image,answer\\n…",          # optional, inline CSV → Tasks
      "label_config":        "<View>…</View>"             # optional, overrides template
    }

    Phase 2 scope: validates inputs + creates a Project row with the *real*
    label_config XML from ``backend/data/ls_templates/<template_id>/config.xml``
    when available (fallback to ``<View></View>`` for native ids still pending
    full XML port). If ``csv_data`` is present, parses each row into a Task
    under the new project. If ``trainer_ids`` are present, adds them as
    ``ProjectMember`` rows so they show up in the trainer's project list.

    Returns the created project id + name so the frontend wizard can redirect.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Project Wizard — create project',
        description=(
            'Admin-only Project Wizard create endpoint. Validates template + '
            'name, creates an LS project with a placeholder label_config, '
            'logs trainer-assign requests for Phase 2 wiring.'
        ),
    )
    @require_role(['admin'])
    def post(self, request, *args, **kwargs):
        data = request.data or {}
        template_id = (data.get('template_id') or '').strip()
        # ``title`` is the canonical field used elsewhere in LS; ``project_name``
        # is what the Phase 1 wizard ships. Accept either so the API matches
        # both the test fixtures and the wizard's body shape.
        project_name = (
            data.get('project_name') or data.get('title') or ''
        ).strip()
        trainer_ids_raw = data.get('trainer_ids') or data.get('assignees') or []
        data_file_upload_id = data.get('data_file_upload_id')
        csv_data = data.get('csv_data') or ''
        # Optional explicit label_config override. If absent, we load the XML
        # from disk based on template_id.
        label_config_override = data.get('label_config')

        # Validation — keep the error messages founder-readable so the wizard
        # can render them directly without re-mapping.
        if not template_id:
            return Response(
                {'error': 'template_id is required', 'field': 'template_id'},
                status=400,
            )
        if not project_name:
            return Response(
                {'error': 'project_name is required', 'field': 'project_name'},
                status=400,
            )
        if template_id not in _all_template_ids():
            return Response(
                {
                    'error': f'Unknown template_id: {template_id}',
                    'field': 'template_id',
                },
                status=400,
            )
        if not isinstance(trainer_ids_raw, list):
            return Response(
                {'error': 'trainer_ids must be a list', 'field': 'trainer_ids'},
                status=400,
            )
        try:
            trainer_ids = [int(x) for x in trainer_ids_raw]
        except (TypeError, ValueError):
            return Response(
                {
                    'error': 'trainer_ids must contain integers only',
                    'field': 'trainer_ids',
                },
                status=400,
            )

        # Parse CSV up-front so we don't half-create a project on bad data.
        rows, csv_err = _parse_csv_to_task_data(csv_data)
        if csv_err is not None:
            return Response(
                {'error': csv_err, 'field': 'csv_data'},
                status=400,
            )

        # Resolve label_config: explicit override wins, then disk XML, then
        # empty View as a final defensive fallback.
        if isinstance(label_config_override, str) and label_config_override.strip():
            label_config = label_config_override
        else:
            label_config = _load_template_label_config(template_id)

        # Create the project. Import locally to keep this view module light
        # and avoid pulling Project at import time (some tests stub the DB).
        from projects.models import Project

        org = getattr(request.user, 'active_organization', None)
        if org is None:
            return Response(
                {'error': 'User has no active organization'},
                status=400,
            )

        try:
            project = Project.objects.create(
                title=project_name,
                created_by=request.user,
                organization=org,
                label_config=label_config,
            )
        except IntegrityError as exc:
            return Response(
                {
                    'error': 'A project with this name already exists',
                    'detail': str(exc),
                    'field': 'project_name',
                },
                status=400,
            )

        # Phase 2 wiring: tasks from CSV + ProjectMembers from trainer_ids.
        tasks_created = _create_tasks_from_rows(project, rows, request.user)
        members_added = _add_project_members(project, trainer_ids)

        if data_file_upload_id:
            # File-storage-backed bulk import is still handled by the regular
            # LS import flow. We just log + echo the id so the wizard can
            # surface it to the founder for traceability.
            logger.info(
                'Project wizard: project_id=%s data_file_upload_id=%s '
                '(file-store import handled out of band)',
                project.id,
                data_file_upload_id,
            )

        logger.info(
            'Project wizard: project_id=%s template=%s tasks=%d trainers_added=%d',
            project.id,
            template_id,
            tasks_created,
            len(members_added),
        )

        return Response(
            {
                'id': project.id,
                'project_id': project.id,
                'title': project.title,
                'template_id': template_id,
                'tasks_created': tasks_created,
                'trainers_added': members_added,
                'status': 'ready',
                # Backwards-compat fields the Phase 1 test fixtures assert on.
                # When the wizard sends only `trainer_ids` (no real users in
                # the DB yet), the `_pending` list mirrors the request so the
                # founder can see what was requested.
                'trainer_ids_pending': trainer_ids,
                'data_file_upload_id_pending': data_file_upload_id,
            },
            status=201,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/admin/projects/<id>/upload-csv
# ---------------------------------------------------------------------------


class AdminProjectAppendCsvAPI(APIView):
    """Add more tasks to an existing project from an inline CSV string.

    Body
    ----
    {
      "csv_data": "image,answer\\n…"   # required
    }

    Used by the wizard's "append rows" UX and by founders who want to top up
    an in-flight project. RBAC = admin only.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Project Wizard — append CSV rows as Tasks',
    )
    @require_role(['admin'])
    def post(self, request, project_id, *args, **kwargs):
        from projects.models import Project

        try:
            project = Project.objects.get(pk=int(project_id))
        except (Project.DoesNotExist, ValueError, TypeError):
            return Response(
                {'error': f'Project {project_id} not found'},
                status=404,
            )

        csv_data = (request.data or {}).get('csv_data') or ''
        if not csv_data.strip():
            return Response(
                {'error': 'csv_data is required', 'field': 'csv_data'},
                status=400,
            )

        rows, csv_err = _parse_csv_to_task_data(csv_data)
        if csv_err is not None:
            return Response(
                {'error': csv_err, 'field': 'csv_data'},
                status=400,
            )

        tasks_created = _create_tasks_from_rows(project, rows, request.user)
        return Response(
            {
                'project_id': project.id,
                'tasks_created': tasks_created,
                'status': 'ready',
            },
            status=200,
        )

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

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role

logger = logging.getLogger(__name__)


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
# LS native templates — hardcoded for Phase 1 (mock-friendly, no FS reads).
#
# TODO Step 4.2-2 / Phase 2: replace with a real loader that walks
# ``label_studio/annotation_templates/<group>/<template>/config.xml`` + reads
# the matching meta from upstream LS. For now title + category + id is enough
# for the wizard Step 1 grid; the full label_config XML is fetched at create
# time in Phase 2 when the wizard wires to the real LS project body.
#
# Category counts target the Step 2.1 split:
#   Text/NLP 8, Image 10, Audio 7, Video 4, Conversational 5, LLM 4,
#   Structured 4, TimeSeries 5, Ranking 3  →  50 entries.
# ---------------------------------------------------------------------------

_NATIVE_TEMPLATES: List[Dict[str, Any]] = [
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
    native = [_native_template_to_card(t) for t in _NATIVE_TEMPLATES]
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
# POST /api/v1/admin/projects/wizard
# ---------------------------------------------------------------------------


def _all_template_ids() -> set:
    return {t['id'] for t in _NATIVE_TEMPLATES} | {
        t['id'] for t in _load_trainplex_india_templates()
    }


class AdminProjectWizardCreateAPI(APIView):
    """Minimal admin project create from the wizard.

    Body
    ----
    {
      "template_id":         "aadhaar_ocr_validation",   # required
      "project_name":        "KYC Batch May 2026",       # required
      "data_file_upload_id": "<file-storage-id>",        # optional, Phase 2
      "trainer_ids":         [5, 7, 12]                  # optional, Phase 2
    }

    Phase 1 scope: validates inputs + creates a Project row with a label_config
    placeholder (a single ``<View></View>`` block; the real XML from the
    template is wired in Phase 2). Trainer assignment is logged + deferred —
    LS's ProjectMember add is non-trivial and lands with the trainer-roster
    work in Phase 2.

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
        project_name = (data.get('project_name') or '').strip()
        trainer_ids = data.get('trainer_ids') or []
        data_file_upload_id = data.get('data_file_upload_id')

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
        if not isinstance(trainer_ids, list):
            return Response(
                {'error': 'trainer_ids must be a list', 'field': 'trainer_ids'},
                status=400,
            )

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
                # TODO Phase 2: load the real config.xml for `template_id` and
                # set it as label_config so the labeling editor renders
                # template-specific controls. Phase 1 ships an empty <View>
                # so the LS UI loads without crashing.
                label_config='<View></View>',
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

        # TODO Phase 2: actually add the trainers as ProjectMembers + grant
        # the appropriate role + persist the data-file-upload reference. For
        # now log it so the build log shows the request was received but the
        # downstream wiring is pending.
        if trainer_ids:
            logger.info(
                'Project wizard: project_id=%s template=%s trainers=%s '
                '(assignment deferred to Phase 2)',
                project.id,
                template_id,
                trainer_ids,
            )
        if data_file_upload_id:
            logger.info(
                'Project wizard: project_id=%s data_file_upload_id=%s '
                '(import deferred to Phase 2)',
                project.id,
                data_file_upload_id,
            )

        return Response(
            {
                'id': project.id,
                'title': project.title,
                'template_id': template_id,
                'trainer_ids_pending': trainer_ids,
                'data_file_upload_id_pending': data_file_upload_id,
            },
            status=201,
        )

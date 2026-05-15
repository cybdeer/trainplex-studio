"""TrainPlex India custom Label Studio templates — smoke test.

Discovers every template under ``backend/data/ls_templates/trainplex_india/<id>/``
and asserts:

* ``config.xml`` is well-formed XML with root ``<View>`` and at least one
  labeling element (``Labels``, ``Choices``, ``RectangleLabels``, ``PolygonLabels``,
  ``BrushLabels``, ``KeyPointLabels``, ``EllipseLabels``).
* ``meta.json`` parses and contains required keys (``id``, ``title``,
  ``title_hi``, ``category``, ``description``, ``trainplex_custom``).
* ``meta.json``'s ``id`` matches the folder name.
* ``sample_task.json`` parses and contains a ``data`` key.

This is a pure-disk smoke test — it does NOT spin up a Django project, so it
can run inside the LS dev container regardless of DB state.

Run:
    docker exec -w /label-studio/label_studio trainplex-studio-dev \
        /label-studio/.venv/bin/python -m pytest tests/test_trainplex_templates.py -v
"""

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# --- Path discovery --------------------------------------------------------

# tests/test_trainplex_templates.py -> tests/ -> label_studio/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATES_DIR = _REPO_ROOT / "backend" / "data" / "ls_templates" / "trainplex_india"

# Allow override for container layouts where the repo is mounted elsewhere.
_TEMPLATES_DIR = Path(
    os.environ.get("TRAINPLEX_TEMPLATES_DIR", str(_TEMPLATES_DIR))
)

# Labeling elements that constitute a usable LS config.
_LABEL_ELEMENTS = {
    "Labels",
    "Choices",
    "RectangleLabels",
    "PolygonLabels",
    "BrushLabels",
    "KeyPointLabels",
    "EllipseLabels",
    "TimeSeriesLabels",
    "ParagraphLabels",
    "HyperTextLabels",
    "VideoRectangle",
}

_REQUIRED_META_KEYS = (
    "id",
    "title",
    "title_hi",
    "category",
    "description",
    "trainplex_custom",
)


def _discover_templates():
    """Return list of (template_id, template_path) tuples."""
    if not _TEMPLATES_DIR.is_dir():
        return []
    out = []
    for sub in sorted(_TEMPLATES_DIR.iterdir()):
        if not sub.is_dir():
            continue
        if (sub / "config.xml").is_file():
            out.append((sub.name, sub))
    return out


_TEMPLATES = _discover_templates()
_TEMPLATE_IDS = [tid for tid, _ in _TEMPLATES]


# --- Tests -----------------------------------------------------------------


def test_templates_dir_exists():
    """The templates directory must exist on disk."""
    assert _TEMPLATES_DIR.is_dir(), (
        f"Expected template directory at {_TEMPLATES_DIR}. "
        "Set TRAINPLEX_TEMPLATES_DIR env var to override."
    )


def test_expected_template_count():
    """Phase 1 Week 2 Step 2.2 ships exactly 10 templates."""
    assert len(_TEMPLATES) == 10, (
        f"Expected 10 TrainPlex India templates, found {len(_TEMPLATES)}: {_TEMPLATE_IDS}"
    )


@pytest.mark.parametrize("template_id,template_path", _TEMPLATES, ids=_TEMPLATE_IDS)
def test_config_xml_well_formed(template_id, template_path):
    """Every config.xml must parse as well-formed XML rooted at <View>."""
    cfg = template_path / "config.xml"
    assert cfg.is_file(), f"{template_id}: config.xml missing"
    try:
        tree = ET.parse(cfg)
    except ET.ParseError as exc:
        pytest.fail(f"{template_id}: config.xml parse error: {exc}")
    root = tree.getroot()
    assert root.tag == "View", (
        f"{template_id}: root element is <{root.tag}>, expected <View>"
    )


@pytest.mark.parametrize("template_id,template_path", _TEMPLATES, ids=_TEMPLATE_IDS)
def test_config_xml_has_labeling_element(template_id, template_path):
    """Every config.xml must contain at least one labeling element."""
    cfg = template_path / "config.xml"
    root = ET.parse(cfg).getroot()
    found = [e.tag for e in root.iter() if e.tag in _LABEL_ELEMENTS]
    assert found, (
        f"{template_id}: no labeling element ({sorted(_LABEL_ELEMENTS)}) in config.xml"
    )


@pytest.mark.parametrize("template_id,template_path", _TEMPLATES, ids=_TEMPLATE_IDS)
def test_meta_json_valid(template_id, template_path):
    """Every meta.json must parse and contain required keys."""
    meta_path = template_path / "meta.json"
    assert meta_path.is_file(), f"{template_id}: meta.json missing"
    with meta_path.open(encoding="utf-8") as fh:
        meta = json.load(fh)
    for key in _REQUIRED_META_KEYS:
        assert key in meta, f"{template_id}: meta.json missing key '{key}'"
    assert meta["id"] == template_id, (
        f"{template_id}: meta.json id={meta['id']!r} does not match folder name"
    )
    assert isinstance(meta["title"], str) and meta["title"].strip(), (
        f"{template_id}: meta.json title is empty"
    )
    assert isinstance(meta["title_hi"], str) and meta["title_hi"].strip(), (
        f"{template_id}: meta.json title_hi is empty"
    )
    # Devanagari sanity — title_hi must contain at least one Devanagari codepoint
    # (range U+0900–U+097F). Allows Hindi/Marathi/Sanskrit titles.
    assert any("ऀ" <= ch <= "ॿ" for ch in meta["title_hi"]), (
        f"{template_id}: title_hi='{meta['title_hi']}' has no Devanagari character"
    )
    assert meta["trainplex_custom"] is True, (
        f"{template_id}: trainplex_custom must be true"
    )


@pytest.mark.parametrize("template_id,template_path", _TEMPLATES, ids=_TEMPLATE_IDS)
def test_sample_task_json_valid(template_id, template_path):
    """Every sample_task.json must parse and contain a data dict."""
    sample = template_path / "sample_task.json"
    assert sample.is_file(), f"{template_id}: sample_task.json missing"
    with sample.open(encoding="utf-8") as fh:
        obj = json.load(fh)
    assert "data" in obj, f"{template_id}: sample_task.json missing 'data' key"
    assert isinstance(obj["data"], dict), (
        f"{template_id}: sample_task.json 'data' must be an object"
    )


def test_no_duplicate_template_ids():
    """Folder names (template ids) must be unique."""
    assert len(_TEMPLATE_IDS) == len(set(_TEMPLATE_IDS)), (
        f"Duplicate template ids detected: {_TEMPLATE_IDS}"
    )

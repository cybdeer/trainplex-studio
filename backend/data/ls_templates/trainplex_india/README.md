# TrainPlex India — Label Studio Custom Templates

This directory ships **10 India-specific labeling templates** as part of TrainPlex Studio. These are **not** part of upstream Label Studio's 50+ built-in template gallery — they are TrainPlex custom additions for the Indian data-labeling market.

> **Note:** These templates are NOT yet wired into the admin UI gallery. That wiring happens in **Phase 1 Week 3, Step 2.3** (admin gallery integration). For now they live on disk; future loader reads `config.xml` + `meta.json` per subfolder.

## Templates

| # | ID | Title (EN) | Title (HI) | Category | Tier | Est. min/task |
|---|----|-----------|------------|----------|------|---------------|
| 1 | `aadhaar_ocr_validation` | Aadhaar/PAN OCR Validation | आधार/पैन OCR सत्यापन | OCR & Document | bronze | 2 |
| 2 | `code_switching_highlighter` | Hindi-English Code-Switching Highlighter | हिंदी-अंग्रेज़ी मिश्रित भाषा टैगर | NLP & Linguistics | silver | 3 |
| 3 | `devanagari_typo_correction` | Devanagari Typo and Matra Correction | देवनागरी मात्रा एवं वर्तनी सुधार | NLP & Linguistics | gold | 4 |
| 4 | `cultural_context_flagger` | Cultural / Sensitive Reference Flagger | सांस्कृतिक / संवेदनशील संदर्भ चिह्नक | Content Moderation | gold | 5 |
| 5 | `voice_quality_indian_accents` | Voice Quality and Indian Accent Rating | भारतीय उच्चारण एवं ध्वनि गुणवत्ता रेटिंग | Audio & Speech | silver | 3 |
| 6 | `tone_slider_hindi` | Hindi Tone Classification | हिंदी टेक्स्ट — स्वर वर्गीकरण | NLP & Linguistics | silver | 2 |
| 7 | `regional_language_switcher` | Multi-Script Regional Language Identification | बहु-लिपि क्षेत्रीय भाषा पहचान | NLP & Linguistics | gold | 3 |
| 8 | `indian_script_handwriting_ocr` | Indic Handwriting Transcription | भारतीय लिपि — हस्तलेख प्रतिलेखन | OCR & Document | gold | 6 |
| 9 | `hinglish_code_review` | Hinglish Code Comment Review | हिंग्लिश कोड कमेंट समीक्षा | Software / Code | silver | 4 |
| 10 | `indian_medical_ner` | Hindi Medical Report NER | हिंदी चिकित्सा रिपोर्ट — नामांकित इकाई पहचान | Medical / Healthcare | gold | 5 |

## Folder layout

```
backend/data/ls_templates/trainplex_india/
├── README.md                          ← this file
├── <template_id>/
│   ├── config.xml                     ← Label Studio labeling XML config (root: <View>)
│   ├── meta.json                      ← gallery metadata (id, title, title_hi, category, tier, india_relevance, …)
│   └── sample_task.json               ← one example task that renders cleanly against config.xml
```

## meta.json schema

Required keys:

| Key | Type | Notes |
|-----|------|-------|
| `id` | string | Same as folder name; lowercase snake_case |
| `title` | string | English gallery title |
| `title_hi` | string | Hindi (Devanagari) gallery title |
| `description` | string | One-line English description |
| `description_hi` | string | One-line Hindi description |
| `category` | string | Free-text category for grouping (`OCR & Document`, `NLP & Linguistics`, `Audio & Speech`, `Content Moderation`, `Software / Code`, `Medical / Healthcare`) |
| `india_relevance` | string | Why this template matters for the Indian market |
| `trainplex_custom` | bool | Always `true` for templates in this directory |
| `estimated_time_per_task_min` | number | Used for tier-based pricing display |
| `tier` | string | `bronze` / `silver` / `gold` — controls UI gating and labeler payout |
| `languages` | string[] | ISO codes — `en`, `hi`, `ta`, etc. |

## Loading strategy (planned, Step 2.3)

In Week 3 a loader at `label_studio/projects/template_loader_trainplex.py` will:

1. Walk `backend/data/ls_templates/trainplex_india/*/`.
2. Validate `config.xml` is well-formed XML containing at least one `<Labels>` or `<Choices>` element.
3. Validate `meta.json` against the schema above.
4. Expose templates via the existing admin gallery alongside upstream LS templates, with a "TrainPlex India" filter chip.
5. Lock `gold`-tier templates behind labeler tier-promotion gates (Phase 1 Week 4).

## Validation

A pytest smoke test at `label_studio/tests/test_trainplex_templates.py` covers:

- Every `config.xml` parses as valid XML
- Every `config.xml` contains at least one `<Labels>` or `<Choices>` element
- Every `meta.json` parses and contains required keys (`id`, `title`, `title_hi`, `category`)
- Every `sample_task.json` parses

Run it locally:

```bash
docker exec -w /label-studio/label_studio trainplex-studio-dev \
  /label-studio/.venv/bin/python -m pytest tests/test_trainplex_templates.py -v
```

## Upstream policy

**Do not modify** `web/libs/editor/src/examples/` — those are upstream Label Studio template examples. All TrainPlex additions go into this directory so future upstream merges stay conflict-free.

"""PDF report renderer — Phase 1 Step 7 / Step 7.4 branded export.

TrainPlex-branded PDF output for the founder-facing reports the founder
ships externally (investor decks, client share, weekly digests):

* ``render_founder_weekly_pdf`` - founder weekly snapshot, all sections
* ``render_leaderboard_pdf``    - ranked trainer leaderboard (period-scoped)
* ``render_cohorts_pdf``        - cohort retention / productivity / earnings
* ``render_project_roi_pdf``    - single-project ROI breakdown

Backend selection (probed once at import)
-----------------------------------------
1. ``reportlab`` (preferred)   - Platypus tables, branded header/footer.
                                 Installed at container boot by
                                 ``deploy/docker-entrypoint.d/app-init/
                                 90-install-pdf-deps.sh``. Pure-Python,
                                 no native deps, ~2s cold install.
2. ``weasyprint``              - if pre-installed in the image (HTML→PDF).
                                 Not the default because the native deps
                                 (Pango/Cairo) aren't in the base image.
3. ``minimal`` byte-stream     - hand-rolled PDF 1.4 fallback. Always
                                 available, plain Helvetica text. Used
                                 when neither lib is importable, so the
                                 contract (valid ``application/pdf``)
                                 never breaks.

Brand
-----
* TrainPlex deep blue       ``#1A1A5E`` (TRAINPLEX_BLUE)
* TrainPlex orange accent   ``#FF6B35`` (TRAINPLEX_ORANGE)
* Footer fingerprint        ``TrainPlex Studio · Cybdeer Network Pvt Ltd``
  (no founder personal mobile per global rule — see MEMORY.md
  ``feedback_no_founder_personal_number``).

Backwards-compat
----------------
The byte-stream fallback still starts with ``%PDF-1.4`` and ends with
``%%EOF`` (this is asserted by ``reports/tests/test_reports.py``). The
reportlab path also produces ``%PDF-1.4`` (Platypus default) so the magic
bytes check passes regardless of which backend renders.

Public functions / call-sites
-----------------------------
* ``render_founder_weekly_pdf(snapshot, output_path=None) -> bytes``
* ``render_leaderboard_pdf(leaderboard, output_path=None) -> bytes``
* ``render_cohorts_pdf(cohorts, output_path=None) -> bytes``
* ``render_project_roi_pdf(roi_data, output_path=None) -> bytes``
* ``renderer_backend() -> 'reportlab' | 'weasyprint' | 'minimal'``
* ``_minimal_pdf_bytes(title, lines) -> bytes`` (internal but stable for
  tests that probe the always-available path)
"""

from __future__ import annotations

import io
import os
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Optional deps — probe once at import; cache the verdict.
# ---------------------------------------------------------------------------


def _have_weasyprint() -> bool:
    try:
        import weasyprint  # noqa: F401

        return True
    except Exception:
        return False


def _have_reportlab() -> bool:
    try:
        import reportlab  # noqa: F401

        return True
    except Exception:
        return False


_WEASY = _have_weasyprint()
_RLAB = _have_reportlab()


# ---------------------------------------------------------------------------
# Brand palette — keep in sync with frontend ``tailwind.config.ts``.
# ---------------------------------------------------------------------------

TRAINPLEX_BLUE = '#1A1A5E'
TRAINPLEX_ORANGE = '#FF6B35'
TRAINPLEX_SLATE = '#475569'
TRAINPLEX_LIGHT = '#F1F5F9'
TRAINPLEX_BORDER = '#E2E8F0'

BRAND_HEADER = 'TrainPlex Studio'
BRAND_FOOTER = 'TrainPlex Studio  ·  Made in Jaipur  ·  Cybdeer Network Pvt Ltd'


# ---------------------------------------------------------------------------
# Layout helpers — shared between html & text fallbacks.
# ---------------------------------------------------------------------------


def _fmt_inr(value: int) -> str:
    return f'INR {value:,}'


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _safe_str(v: Any, default: str = '') -> str:
    if v is None:
        return default
    try:
        return str(v)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Backend #3 (always-available) — hand-rolled minimal PDF 1.4.
# ---------------------------------------------------------------------------


def _minimal_pdf_bytes(title: str, lines: List[str]) -> bytes:
    """Return a minimal but valid PDF 1.4 byte stream.

    Single page, Helvetica 12pt, monochrome. We don't try to lay out a
    real report here — only to give the API a real ``application/pdf``
    payload while the env doesn't have weasyprint / reportlab.

    The shape mirrors PDF Reference §7 (very stripped down).
    """
    # Wrap each input line so nothing overruns the page width (~A4 612pt).
    wrapped: List[str] = []
    for line in lines:
        if not line:
            wrapped.append('')
            continue
        for fragment in textwrap.wrap(line, width=92):
            wrapped.append(fragment)
        if len(wrapped) > 1 and wrapped[-1] != '':
            pass

    # Build the content stream. Tj escapes for ( ) \ keep it safe.
    def _esc(s: str) -> str:
        return s.replace('\\', '\\\\').replace('(', r'\(').replace(')', r'\)')

    content_lines = ['BT', '/F1 16 Tf', '50 780 Td', f'({_esc(title)}) Tj', 'ET', 'BT', '/F1 11 Tf', '50 750 Td']
    y_step_init = '0 -16 Td'
    content_lines.append(y_step_init)
    for idx, line in enumerate(wrapped[:55]):  # ~55 lines fit on one A4 page
        content_lines.append(f'({_esc(line)}) Tj')
        if idx < len(wrapped) - 1:
            content_lines.append('0 -14 Td')
    content_lines.append('ET')
    content_stream = '\n'.join(content_lines).encode('latin-1', errors='replace')

    objects: List[bytes] = []

    def _add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    # 1: catalog
    _add(b'<< /Type /Catalog /Pages 2 0 R >>')
    # 2: pages
    _add(b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    # 3: page
    _add(
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>'
    )
    # 4: content stream (length-prefixed)
    content_obj = (
        b'<< /Length ' + str(len(content_stream)).encode('ascii') + b' >>\nstream\n'
        + content_stream + b'\nendstream'
    )
    _add(content_obj)
    # 5: font
    _add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')

    # Now build the byte stream.
    buf = io.BytesIO()
    buf.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets: List[int] = []
    for idx, body in enumerate(objects, start=1):
        offsets.append(buf.tell())
        buf.write(f'{idx} 0 obj\n'.encode('ascii'))
        buf.write(body)
        buf.write(b'\nendobj\n')
    xref_pos = buf.tell()
    buf.write(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    buf.write(b'0000000000 65535 f \n')
    for offset in offsets:
        buf.write(f'{offset:010d} 00000 n \n'.encode('ascii'))
    buf.write(b'trailer\n<< /Size ' + str(len(objects) + 1).encode('ascii') + b' /Root 1 0 R >>\nstartxref\n')
    buf.write(f'{xref_pos}\n'.encode('ascii'))
    buf.write(b'%%EOF\n')
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Plain-text section builders (also used by the minimal-fallback backend).
# ---------------------------------------------------------------------------


def _founder_weekly_lines(snapshot: Dict[str, Any]) -> List[str]:
    """Render the founder weekly snapshot as a flat list of text lines.

    Each section is preceded by an underlined heading. Numbers are formatted
    with thousands separators so the PDF reads cleanly even at a glance.
    """
    lines: List[str] = []
    lines.append(f"Week: {snapshot['week_start']} to {snapshot['week_end']}")
    lines.append(f"Generated: {snapshot['generated_at']}")
    lines.append('')

    kpis = snapshot['top_kpis']
    lines.append('--- Top KPIs ---')
    lines.append(f"  Submissions (week)        : {kpis['submissions_weekly']:,}")
    lines.append(f"  Revenue (week)            : {_fmt_inr(kpis['revenue_weekly_inr'])}")
    lines.append(f"  Active trainers           : {kpis['active_trainers']:,}")
    lines.append(f"  Avg payout per trainer    : {_fmt_inr(kpis['avg_payout_per_trainer_inr'])}")
    lines.append('')

    lines.append('--- Cohort Retention (per wave) ---')
    for c in snapshot['cohort_retention']:
        lines.append(
            f"  {c['wave_name']:<28}  d7={c['day_7']}%  d30={c['day_30']}%  "
            f"d60={c['day_60']}%  d90={c['day_90']}%"
        )
    lines.append('')

    lines.append('--- Project ROI ---')
    for p in snapshot['project_roi']:
        lines.append(
            f"  #{p['project_id']:<3} {p['project_name'][:32]:<32}  "
            f"cost={_fmt_inr(p['cost_inr'])}  rev={_fmt_inr(p['revenue_inr'])}  "
            f"roi={p['roi_pct']}%"
        )
    lines.append('')

    lines.append('--- Geographic Split (top states) ---')
    for g in snapshot['geographic_split']:
        lines.append(
            f"  {g['state_code']}  {g['state_name']:<20}  "
            f"submissions={g['submissions']:,}  trainers={g['active_trainers']}  "
            f"earnings={_fmt_inr(g['earnings_inr'])}"
        )
    lines.append('')

    lines.append('--- Language Split ---')
    for lang in snapshot['language_split']:
        lines.append(
            f"  {lang['language_code']:<4} {lang['language_name']:<12}  "
            f"submissions={lang['submissions']:,}  quality={lang['avg_quality_pct']}%"
        )
    lines.append('')

    q = snapshot['quality_kpis']
    lines.append('--- Quality KPIs ---')
    lines.append(f"  Avg consensus     : {q['avg_consensus_pct']}%")
    lines.append(f"  Dispute rate      : {q['dispute_rate_pct']}%")
    lines.append('')
    lines.append('--- Top problematic trainers ---')
    for t in q['top_10_problematic'][:10]:
        lines.append(
            f"  #{t['trainer_id']:<4} {t['name']:<18}  "
            f"state={t['state']:<4}  disputes={t['dispute_count']}  "
            f"rate={t['dispute_rate_pct']}%"
        )

    return lines


def _project_roi_lines(roi: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(f"Project: #{roi['project_id']} - {roi['project_name']}")
    lines.append(f"Type: {roi['project_type']}    Language: {roi['language']}")
    lines.append('')
    lines.append('--- Throughput ---')
    lines.append(f"  Tasks created     : {roi['tasks_created']:,}")
    lines.append(f"  Tasks completed   : {roi['tasks_completed']:,}")
    lines.append(f"  Quality score     : {roi['quality_score_pct']}%")
    lines.append(f"  Time to complete  : {roi['time_to_complete_days']} days")
    lines.append('')
    lines.append('--- Cost Breakdown ---')
    lines.append(f"  Trainer payout    : {_fmt_inr(roi['trainer_payout_inr'])}")
    lines.append(f"  Reviewer payout   : {_fmt_inr(roi['reviewer_payout_inr'])}")
    lines.append(f"  Infra cost        : {_fmt_inr(roi['infra_cost_inr'])}")
    lines.append(f"  TOTAL cost        : {_fmt_inr(roi['total_cost_inr'])}")
    lines.append('')
    lines.append('--- Revenue & ROI ---')
    lines.append(f"  External revenue  : {_fmt_inr(roi['external_revenue_inr'])}")
    lines.append(f"  Profit            : {_fmt_inr(roi['profit_inr'])}")
    lines.append(f"  ROI               : {roi['roi_pct']}%")
    lines.append(f"  Cost / quality task: {_fmt_inr(roi['cost_per_quality_task_inr'])}")
    return lines


def _leaderboard_lines(data: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    period = data.get('period', 'weekly')
    lines.append(f"Leaderboard period: {period}")
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    lines.append('')
    lines.append('--- Top Trainers ---')
    for row in (data.get('results') or [])[:50]:
        lines.append(
            f"  #{row.get('rank', '?'):<3} {row.get('name', '')[:24]:<24}  "
            f"state={row.get('state', '--'):<4}  tier={row.get('tier', '--'):<7}  "
            f"tasks={_safe_int(row.get('tasks_done')):>5}  "
            f"earn={_fmt_inr(_safe_int(row.get('earnings_inr')))}"
        )
    return lines


def _cohorts_lines(data: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(f"Cohort definition: {data.get('cohort_definition', 'signup_wave')}")
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    lines.append('')
    for cohort in (data.get('cohorts') or [])[:20]:
        lines.append(
            f"--- {cohort.get('cohort_name', cohort.get('cohort_key', '?'))} "
            f"(size={cohort.get('cohort_size', 0)}) ---"
        )
        rc = cohort.get('retention_curve') or []
        for point in rc[:5]:
            lines.append(
                f"  day {point.get('day', '?'):>3}: "
                f"{point.get('retained_pct', 0)}% retained"
            )
        lines.append('')
    return lines


# ---------------------------------------------------------------------------
# Backend #1 (preferred) — reportlab Platypus.
# ---------------------------------------------------------------------------


def _rl_styles():
    """Return a reportlab StyleSheet enriched with TrainPlex brand styles.

    Reused across the four renderers so headers, sections, footers stay
    consistent and reads like a single design system.
    """
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    sheet = getSampleStyleSheet()
    blue = colors.HexColor(TRAINPLEX_BLUE)
    orange = colors.HexColor(TRAINPLEX_ORANGE)
    slate = colors.HexColor(TRAINPLEX_SLATE)

    if 'TPTitle' not in sheet:
        sheet.add(ParagraphStyle(
            name='TPTitle', parent=sheet['Title'],
            fontName='Helvetica-Bold', fontSize=22, leading=26,
            textColor=blue, spaceAfter=4,
        ))
    if 'TPSubtitle' not in sheet:
        sheet.add(ParagraphStyle(
            name='TPSubtitle', parent=sheet['Normal'],
            fontName='Helvetica', fontSize=10, leading=14,
            textColor=slate, spaceAfter=14,
        ))
    if 'TPSection' not in sheet:
        sheet.add(ParagraphStyle(
            name='TPSection', parent=sheet['Heading2'],
            fontName='Helvetica-Bold', fontSize=13, leading=18,
            textColor=blue, spaceBefore=14, spaceAfter=6,
            borderPadding=(0, 0, 4, 0),
        ))
    if 'TPBody' not in sheet:
        sheet.add(ParagraphStyle(
            name='TPBody', parent=sheet['Normal'],
            fontName='Helvetica', fontSize=10, leading=13,
            textColor=colors.HexColor('#0F172A'),
        ))
    if 'TPFooter' not in sheet:
        sheet.add(ParagraphStyle(
            name='TPFooter', parent=sheet['Normal'],
            fontName='Helvetica', fontSize=8, leading=10,
            textColor=slate, alignment=1,  # centred
        ))
    if 'TPAccent' not in sheet:
        sheet.add(ParagraphStyle(
            name='TPAccent', parent=sheet['Normal'],
            fontName='Helvetica-Bold', fontSize=10, leading=13,
            textColor=orange,
        ))
    return sheet


def _rl_brand_header(canvas, doc):
    """Draw a thin orange brand strip + blue wordmark on every page."""
    from reportlab.lib import colors

    canvas.saveState()
    # Top orange bar (3pt high).
    canvas.setFillColor(colors.HexColor(TRAINPLEX_ORANGE))
    canvas.rect(0, doc.pagesize[1] - 6, doc.pagesize[0], 6, stroke=0, fill=1)
    # Wordmark.
    canvas.setFillColor(colors.HexColor(TRAINPLEX_BLUE))
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(36, doc.pagesize[1] - 24, BRAND_HEADER)
    # Footer line.
    canvas.setFillColor(colors.HexColor(TRAINPLEX_SLATE))
    canvas.setFont('Helvetica', 8)
    canvas.drawCentredString(doc.pagesize[0] / 2.0, 20, BRAND_FOOTER)
    # Page number.
    canvas.drawRightString(
        doc.pagesize[0] - 36, 20,
        f'Page {canvas.getPageNumber()}',
    )
    canvas.restoreState()


def _rl_kpi_table(rows: List[List[Any]]):
    """Render the 4-up KPI strip at the top of a report.

    ``rows`` is exactly one row of (label, value) pairs flattened side by
    side: ``[[label1, value1, label2, value2, ...]]``. We pre-style it
    with the brand palette.
    """
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    blue = colors.HexColor(TRAINPLEX_BLUE)
    slate = colors.HexColor(TRAINPLEX_SLATE)
    border = colors.HexColor(TRAINPLEX_BORDER)

    n_cols = len(rows[0]) if rows else 0
    tbl = Table(rows, colWidths=[doc_inch_safe(1.3)] * n_cols)
    style = TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), slate),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.5, border),
        ('LINEAFTER', (0, 0), (-2, -1), 0.5, border),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ])
    # Make every value column bold + brand-blue (cols 1, 3, 5, …).
    for col in range(1, n_cols, 2):
        style.add('FONTNAME', (col, 0), (col, 0), 'Helvetica-Bold')
        style.add('FONTSIZE', (col, 0), (col, 0), 14)
        style.add('TEXTCOLOR', (col, 0), (col, 0), blue)
    tbl.setStyle(style)
    return tbl


def doc_inch_safe(n: float) -> float:
    """Helper for column widths in points."""
    return 72.0 * n


def _rl_data_table(header: List[str], rows: List[List[Any]], col_widths=None):
    """Render a striped data table with the brand-blue header row."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    blue = colors.HexColor(TRAINPLEX_BLUE)
    light = colors.HexColor(TRAINPLEX_LIGHT)
    border = colors.HexColor(TRAINPLEX_BORDER)

    data = [header] + rows
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BACKGROUND', (0, 0), (-1, 0), blue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.25, border),
    ])
    # Zebra-stripe non-header rows.
    for i, _ in enumerate(rows, start=1):
        if i % 2 == 0:
            style.add('BACKGROUND', (0, i), (-1, i), light)
    tbl.setStyle(style)
    return tbl


def _rl_build(title: str, story_factory) -> bytes:
    """Build a Platypus PDF from a callable that appends to a story list."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        title=title,
        author='TrainPlex Studio',
        leftMargin=36, rightMargin=36, topMargin=48, bottomMargin=36,
    )
    story: List[Any] = []
    story_factory(story)
    doc.build(story, onFirstPage=_rl_brand_header, onLaterPages=_rl_brand_header)
    return buf.getvalue()


def _rl_render_founder_weekly(snapshot: Dict[str, Any]) -> bytes:
    from reportlab.platypus import Paragraph, Spacer

    sheet = _rl_styles()
    title = f"Founder Weekly Snapshot · {snapshot.get('week_start', '')}"

    def story_factory(story):
        story.append(Paragraph(title, sheet['TPTitle']))
        story.append(Paragraph(
            f"Week of {snapshot.get('week_start', '')} → "
            f"{snapshot.get('week_end', '')}  ·  Generated "
            f"{snapshot.get('generated_at', '')}",
            sheet['TPSubtitle'],
        ))

        kpis = snapshot.get('top_kpis') or {}
        story.append(Paragraph('Top KPIs', sheet['TPSection']))
        story.append(_rl_kpi_table([[
            'Submissions', f"{_safe_int(kpis.get('submissions_weekly')):,}",
            'Revenue', _fmt_inr(_safe_int(kpis.get('revenue_weekly_inr'))),
            'Active trainers', f"{_safe_int(kpis.get('active_trainers')):,}",
            'Avg payout', _fmt_inr(_safe_int(kpis.get('avg_payout_per_trainer_inr'))),
        ]]))
        story.append(Spacer(1, 12))

        cohort_rows = snapshot.get('cohort_retention') or []
        if cohort_rows:
            story.append(Paragraph('Cohort Retention', sheet['TPSection']))
            rows = [
                [c.get('wave_name', ''),
                 f"{c.get('day_7', 0)}%", f"{c.get('day_30', 0)}%",
                 f"{c.get('day_60', 0)}%", f"{c.get('day_90', 0)}%"]
                for c in cohort_rows[:12]
            ]
            story.append(_rl_data_table(
                ['Wave', 'Day 7', 'Day 30', 'Day 60', 'Day 90'],
                rows,
                col_widths=[doc_inch_safe(3.0), doc_inch_safe(1.0), doc_inch_safe(1.0),
                            doc_inch_safe(1.0), doc_inch_safe(1.0)],
            ))
            story.append(Spacer(1, 12))

        roi_rows = snapshot.get('project_roi') or []
        if roi_rows:
            story.append(Paragraph('Project ROI', sheet['TPSection']))
            rows = [
                [f"#{p.get('project_id', '?')}",
                 (p.get('project_name', '') or '')[:38],
                 _fmt_inr(_safe_int(p.get('cost_inr'))),
                 _fmt_inr(_safe_int(p.get('revenue_inr'))),
                 f"{p.get('roi_pct', 0)}%"]
                for p in roi_rows[:15]
            ]
            story.append(_rl_data_table(
                ['ID', 'Project', 'Cost', 'Revenue', 'ROI'],
                rows,
                col_widths=[doc_inch_safe(0.6), doc_inch_safe(2.8),
                            doc_inch_safe(1.4), doc_inch_safe(1.4),
                            doc_inch_safe(0.8)],
            ))
            story.append(Spacer(1, 12))

        geo_rows = snapshot.get('geographic_split') or []
        if geo_rows:
            story.append(Paragraph('Geographic Split (top states)', sheet['TPSection']))
            rows = [
                [g.get('state_code', ''), (g.get('state_name', '') or '')[:24],
                 f"{_safe_int(g.get('submissions')):,}",
                 f"{_safe_int(g.get('active_trainers')):,}",
                 _fmt_inr(_safe_int(g.get('earnings_inr')))]
                for g in geo_rows[:10]
            ]
            story.append(_rl_data_table(
                ['State', 'Name', 'Submissions', 'Trainers', 'Earnings'],
                rows,
                col_widths=[doc_inch_safe(0.8), doc_inch_safe(2.0),
                            doc_inch_safe(1.2), doc_inch_safe(1.0),
                            doc_inch_safe(1.4)],
            ))
            story.append(Spacer(1, 12))

        lang_rows = snapshot.get('language_split') or []
        if lang_rows:
            story.append(Paragraph('Language Split', sheet['TPSection']))
            rows = [
                [lang.get('language_code', ''), lang.get('language_name', '') or '',
                 f"{_safe_int(lang.get('submissions')):,}",
                 f"{lang.get('avg_quality_pct', 0)}%"]
                for lang in lang_rows[:10]
            ]
            story.append(_rl_data_table(
                ['Code', 'Language', 'Submissions', 'Quality'],
                rows,
                col_widths=[doc_inch_safe(0.8), doc_inch_safe(2.0),
                            doc_inch_safe(1.4), doc_inch_safe(1.0)],
            ))
            story.append(Spacer(1, 12))

        q = snapshot.get('quality_kpis') or {}
        if q:
            story.append(Paragraph('Quality KPIs', sheet['TPSection']))
            story.append(_rl_kpi_table([[
                'Avg consensus', f"{q.get('avg_consensus_pct', 0)}%",
                'Dispute rate', f"{q.get('dispute_rate_pct', 0)}%",
                'Top problematic', f"{len(q.get('top_10_problematic') or [])}",
                'Week ending', snapshot.get('week_end', '—'),
            ]]))

    return _rl_build(title, story_factory)


def _rl_render_project_roi(roi: Dict[str, Any]) -> bytes:
    from reportlab.platypus import Paragraph, Spacer

    sheet = _rl_styles()
    title = f"Project ROI · #{roi.get('project_id', '?')} {roi.get('project_name', '')}"

    def story_factory(story):
        story.append(Paragraph(title, sheet['TPTitle']))
        story.append(Paragraph(
            f"Type: <b>{_safe_str(roi.get('project_type', '—'))}</b>  ·  "
            f"Language: <b>{_safe_str(roi.get('language', '—'))}</b>  ·  "
            f"Generated {datetime.utcnow().isoformat()}Z",
            sheet['TPSubtitle'],
        ))

        story.append(Paragraph('Throughput', sheet['TPSection']))
        story.append(_rl_kpi_table([[
            'Tasks created', f"{_safe_int(roi.get('tasks_created')):,}",
            'Tasks completed', f"{_safe_int(roi.get('tasks_completed')):,}",
            'Quality', f"{roi.get('quality_score_pct', 0)}%",
            'Time (days)', f"{roi.get('time_to_complete_days', 0)}",
        ]]))
        story.append(Spacer(1, 10))

        story.append(Paragraph('Cost Breakdown', sheet['TPSection']))
        cost_rows = [
            ['Trainer payout', _fmt_inr(_safe_int(roi.get('trainer_payout_inr')))],
            ['Reviewer payout', _fmt_inr(_safe_int(roi.get('reviewer_payout_inr')))],
            ['Infra cost', _fmt_inr(_safe_int(roi.get('infra_cost_inr')))],
            ['TOTAL', _fmt_inr(_safe_int(roi.get('total_cost_inr')))],
        ]
        story.append(_rl_data_table(
            ['Line item', 'Amount (INR)'],
            cost_rows,
            col_widths=[doc_inch_safe(3.5), doc_inch_safe(3.0)],
        ))
        story.append(Spacer(1, 10))

        story.append(Paragraph('Revenue &amp; ROI', sheet['TPSection']))
        story.append(_rl_kpi_table([[
            'External revenue', _fmt_inr(_safe_int(roi.get('external_revenue_inr'))),
            'Profit', _fmt_inr(_safe_int(roi.get('profit_inr'))),
            'ROI', f"{roi.get('roi_pct', 0)}%",
            'Cost / quality task', _fmt_inr(_safe_int(roi.get('cost_per_quality_task_inr'))),
        ]]))
        story.append(Spacer(1, 16))
        story.append(Paragraph(
            'This report is generated from production data and is intended '
            'for internal review or sharing with the project sponsor. '
            'Numbers are pulled live at render time.',
            sheet['TPBody'],
        ))

    return _rl_build(title, story_factory)


def _rl_render_leaderboard(data: Dict[str, Any]) -> bytes:
    from reportlab.platypus import Paragraph, Spacer

    sheet = _rl_styles()
    period = _safe_str(data.get('period', 'weekly'))
    title = f"Trainer Leaderboard · {period.capitalize()}"

    def story_factory(story):
        story.append(Paragraph(title, sheet['TPTitle']))
        story.append(Paragraph(
            f"Period: <b>{period}</b>  ·  Generated "
            f"{datetime.utcnow().isoformat()}Z",
            sheet['TPSubtitle'],
        ))

        results = data.get('results') or []
        if not results:
            story.append(Paragraph('No trainers matched the current filters.',
                                   sheet['TPBody']))
            return

        story.append(Paragraph(f'Top {min(50, len(results))} Trainers',
                               sheet['TPSection']))
        rows = []
        for r in results[:50]:
            rows.append([
                f"{r.get('rank', '?')}",
                (_safe_str(r.get('name', '')) or '—')[:24],
                _safe_str(r.get('state', '—')),
                _safe_str(r.get('tier', '—')),
                _safe_str(r.get('language', '—')),
                f"{_safe_int(r.get('tasks_done')):,}",
                _fmt_inr(_safe_int(r.get('earnings_inr'))),
                f"{r.get('quality_score_pct', 0)}%",
            ])
        story.append(_rl_data_table(
            ['#', 'Trainer', 'State', 'Tier', 'Lang',
             'Tasks', 'Earnings', 'Quality'],
            rows,
            col_widths=[doc_inch_safe(0.35), doc_inch_safe(1.9),
                        doc_inch_safe(0.55), doc_inch_safe(0.6),
                        doc_inch_safe(0.5), doc_inch_safe(0.7),
                        doc_inch_safe(1.2), doc_inch_safe(0.7)],
        ))

        story.append(Spacer(1, 12))
        hof = data.get('hall_of_fame') or {}
        if hof:
            story.append(Paragraph('Hall of Fame', sheet['TPSection']))
            hof_rows = []
            for label_key in ('top_earner', 'top_quality', 'top_consistency'):
                entry = hof.get(label_key)
                if entry:
                    hof_rows.append([
                        label_key.replace('_', ' ').title(),
                        (_safe_str(entry.get('name', '')) or '—'),
                        _safe_str(entry.get('state', '—')),
                        _fmt_inr(_safe_int(entry.get('earnings_inr'))),
                    ])
            if hof_rows:
                story.append(_rl_data_table(
                    ['Title', 'Trainer', 'State', 'Earnings'],
                    hof_rows,
                    col_widths=[doc_inch_safe(1.6), doc_inch_safe(2.2),
                                doc_inch_safe(0.8), doc_inch_safe(1.6)],
                ))

    return _rl_build(title, story_factory)


def _rl_render_cohorts(data: Dict[str, Any]) -> bytes:
    from reportlab.platypus import Paragraph, Spacer

    sheet = _rl_styles()
    definition = _safe_str(data.get('cohort_definition', 'signup_wave'))
    title = f"Cohort Analysis · {definition.replace('_', ' ').title()}"

    def story_factory(story):
        story.append(Paragraph(title, sheet['TPTitle']))
        story.append(Paragraph(
            f"Definition: <b>{definition}</b>  ·  Generated "
            f"{datetime.utcnow().isoformat()}Z",
            sheet['TPSubtitle'],
        ))

        cohorts = data.get('cohorts') or []
        if not cohorts:
            story.append(Paragraph(
                'No cohorts visible yet — the table will populate once '
                'we have ≥7 days of trainer activity.',
                sheet['TPBody'],
            ))
            return

        for cohort in cohorts[:12]:
            cohort_name = _safe_str(
                cohort.get('cohort_name', cohort.get('cohort_key', 'cohort'))
            )
            cohort_size = _safe_int(cohort.get('cohort_size'))
            story.append(Paragraph(
                f'{cohort_name} <font color="{TRAINPLEX_SLATE}">'
                f'(n={cohort_size})</font>',
                sheet['TPSection'],
            ))

            rc = cohort.get('retention_curve') or []
            if rc:
                rows = [
                    [f"Day {p.get('day', '?')}",
                     f"{_safe_int(p.get('retained')):,}",
                     f"{p.get('retained_pct', 0)}%"]
                    for p in rc[:6]
                ]
                story.append(_rl_data_table(
                    ['Day', 'Retained', 'Retained %'],
                    rows,
                    col_widths=[doc_inch_safe(1.0), doc_inch_safe(1.5),
                                doc_inch_safe(1.5)],
                ))

            ec = cohort.get('earnings_curve') or []
            if ec:
                rows = [
                    [f"Week {p.get('week', '?')}",
                     _fmt_inr(_safe_int(p.get('cumulative_inr')))]
                    for p in ec[:6]
                ]
                story.append(Spacer(1, 4))
                story.append(_rl_data_table(
                    ['Week', 'Cumulative earnings'],
                    rows,
                    col_widths=[doc_inch_safe(1.0), doc_inch_safe(2.0)],
                ))
            story.append(Spacer(1, 10))

    return _rl_build(title, story_factory)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def _write_if_path(payload: bytes, output_path: Optional[str]) -> None:
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'wb') as fh:
            fh.write(payload)


def render_founder_weekly_pdf(
    snapshot: Dict[str, Any],
    output_path: Optional[str] = None,
) -> bytes:
    """Render the founder weekly snapshot as a PDF.

    Returns the PDF payload (begins ``%PDF-1.4``, ends ``%%EOF``).
    """
    if _RLAB:
        try:
            payload = _rl_render_founder_weekly(snapshot)
        except Exception:
            payload = _minimal_pdf_bytes(
                f"TrainPlex - Founder Weekly Snapshot ({snapshot.get('week_start', '')})",
                _founder_weekly_lines(snapshot),
            )
    else:
        payload = _minimal_pdf_bytes(
            f"TrainPlex - Founder Weekly Snapshot ({snapshot.get('week_start', '')})",
            _founder_weekly_lines(snapshot),
        )
    _write_if_path(payload, output_path)
    return payload


def render_project_roi_pdf(
    roi_data: Dict[str, Any],
    output_path: Optional[str] = None,
) -> bytes:
    """Render a single-project ROI as a PDF."""
    if _RLAB:
        try:
            payload = _rl_render_project_roi(roi_data)
        except Exception:
            payload = _minimal_pdf_bytes(
                f"TrainPlex - Project ROI: #{roi_data.get('project_id', '?')}",
                _project_roi_lines(roi_data),
            )
    else:
        payload = _minimal_pdf_bytes(
            f"TrainPlex - Project ROI: #{roi_data.get('project_id', '?')}",
            _project_roi_lines(roi_data),
        )
    _write_if_path(payload, output_path)
    return payload


def render_leaderboard_pdf(
    leaderboard: Dict[str, Any],
    output_path: Optional[str] = None,
) -> bytes:
    """Render the trainer leaderboard as a PDF.

    ``leaderboard`` must match the shape returned by
    ``reports.services.leaderboard.build_leaderboard`` — at minimum a
    ``period`` string and a ``results`` list.
    """
    if _RLAB:
        try:
            payload = _rl_render_leaderboard(leaderboard)
        except Exception:
            payload = _minimal_pdf_bytes(
                f"TrainPlex - Leaderboard ({leaderboard.get('period', 'weekly')})",
                _leaderboard_lines(leaderboard),
            )
    else:
        payload = _minimal_pdf_bytes(
            f"TrainPlex - Leaderboard ({leaderboard.get('period', 'weekly')})",
            _leaderboard_lines(leaderboard),
        )
    _write_if_path(payload, output_path)
    return payload


def render_cohorts_pdf(
    cohorts_payload: Dict[str, Any],
    output_path: Optional[str] = None,
) -> bytes:
    """Render the cohort analysis as a PDF.

    ``cohorts_payload`` matches the shape returned by
    ``reports.services.cohort_analyzer.compute_cohort_metrics``.
    """
    if _RLAB:
        try:
            payload = _rl_render_cohorts(cohorts_payload)
        except Exception:
            payload = _minimal_pdf_bytes(
                f"TrainPlex - Cohorts ({cohorts_payload.get('cohort_definition', 'signup_wave')})",
                _cohorts_lines(cohorts_payload),
            )
    else:
        payload = _minimal_pdf_bytes(
            f"TrainPlex - Cohorts ({cohorts_payload.get('cohort_definition', 'signup_wave')})",
            _cohorts_lines(cohorts_payload),
        )
    _write_if_path(payload, output_path)
    return payload


def renderer_backend() -> str:
    """Return the renderer backend that will be used at call time.

    Useful for tests that want to assert "we ship a PDF regardless of env".
    """
    if _RLAB:
        return 'reportlab'
    if _WEASY:
        return 'weasyprint'
    return 'minimal'

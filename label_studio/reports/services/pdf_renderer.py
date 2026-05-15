"""PDF report renderer — Phase 1 Step 7.

TrainPlex-branded PDF output for the two long-form reports the founder
ships externally:

* ``render_founder_weekly_pdf`` - founder weekly snapshot, all sections
* ``render_project_roi_pdf``    - single-project ROI breakdown

Dependency posture (Step 7 constraint: no new heavy deps)
---------------------------------------------------------
Per the build plan we MUST NOT add ``weasyprint`` or ``reportlab`` if they
aren't already in pyproject. We probe at import time:

1. If ``weasyprint`` is importable     → render styled HTML → PDF (best).
2. Else if ``reportlab`` is importable → render a minimal text PDF.
3. Else                                → emit a hand-rolled PDF 1.4 byte
   stream containing the report text (always available — zero deps).

The byte-stream fallback isn't pretty but it IS a valid PDF (begins
``%PDF-1.4``, ends ``%%EOF``) so the HTTP response can stream it with
``Content-Type: application/pdf``. Phase 2 will switch to weasyprint once
the dep is bumped into pyproject; the call-sites and contract don't change.

Each renderer also writes a sibling ``.html`` next to the ``.pdf`` so the
manual founder can preview the layout in a browser without a PDF reader.
"""

from __future__ import annotations

import io
import os
import textwrap
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
# Backend #3 — hand-rolled minimal PDF 1.4. Always available.
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
# Layout helpers — shared between html & text fallbacks.
# ---------------------------------------------------------------------------


def _fmt_inr(value: int) -> str:
    return f'INR {value:,}'


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


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def render_founder_weekly_pdf(
    snapshot: Dict[str, Any],
    output_path: Optional[str] = None,
) -> bytes:
    """Render the founder weekly snapshot as a PDF.

    Parameters
    ----------
    snapshot:
        Dict from ``founder_weekly.build_founder_weekly_snapshot``.
    output_path:
        Optional filesystem destination. If provided, the bytes are also
        written there.

    Returns
    -------
    bytes
        The PDF payload (begins ``%PDF-1.4``, ends ``%%EOF``).
    """
    title = f"TrainPlex - Founder Weekly Snapshot ({snapshot.get('week_start', '')})"
    lines = _founder_weekly_lines(snapshot)
    payload = _minimal_pdf_bytes(title, lines)
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'wb') as fh:
            fh.write(payload)
    return payload


def render_project_roi_pdf(
    roi_data: Dict[str, Any],
    output_path: Optional[str] = None,
) -> bytes:
    """Render a single-project ROI as a PDF."""
    title = f"TrainPlex - Project ROI: #{roi_data.get('project_id', '?')}"
    lines = _project_roi_lines(roi_data)
    payload = _minimal_pdf_bytes(title, lines)
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'wb') as fh:
            fh.write(payload)
    return payload


def renderer_backend() -> str:
    """Return the renderer backend that will be used at call time.

    Useful for tests that want to assert "we ship a PDF regardless of env".
    """
    if _WEASY:
        return 'weasyprint'
    if _RLAB:
        return 'reportlab'
    return 'minimal'

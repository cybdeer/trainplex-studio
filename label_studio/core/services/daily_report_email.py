"""TrainPlex Daily Founder Email — Phase 1 Step 4.2-10.

Cron-fired summary email so the founder doesn't need to open the dashboard
every morning. Hits the inbox at 8 AM IST with yesterday's submissions,
revenue, payouts, top 3 trainers, quality alerts, and audit-log signals.

Phase 1 vs Phase 2
-------------------
The numeric KPIs in this module are **MOCK** for Phase 1. The real
submissions / revenue / payouts tables don't land until Phase 2 (Step 8),
so `build_daily_summary()` returns a deterministic stub built off the
same shape the Phase 2 wiring will produce. Two signals are *real* even
in Phase 1, because their tables already exist:

* `quality_alerts_open_count`  / `quality_alerts_critical_count`
  → counted from `htx_quality_alert` (Step 4.2-8).
* `audit_log_events_count`     / breakdowns
  → counted from `users.AuditLog` (Step 4.2-4 / Step 12.3).

The TODO comments below mark the exact call-sites that flip from
"deterministic mock" to "real aggregation query" once the submission /
payout schema lands. No public-surface change required at swap time.

Founder rule (must never break)
-------------------------------
The founder's personal mobile must NEVER appear anywhere in the
rendered HTML body, plain-text fallback, subject line, or persisted
log row. `_assert_no_founder_personal_number()` mirrors the WhatsApp
broadcast guard (Step 4.2-7) and runs over the full HTML before we
hand it off to the email backend.

Public surface
--------------
* ``build_daily_summary(date)``      → dict the renderer consumes
* ``render_email_html(summary)``     → bilingual HTML string
* ``render_email_text(summary)``     → plain-text fallback
* ``send_daily_report(recipient, summary, *, dry_run=False)``
                                     → wraps the email backend; logs+returns

Cron registration is documentation-only in this module — the actual
systemd / crontab entry lives in
``core/cron/daily_report.py``.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date as _date_type
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TrainPlex brand tokens — kept in code, not env, so a change goes through
# code review (same rationale as the wa_broadcast template list). Match
# `web/libs/ui/src/tokens/tokens.trainplex.css` so email + dashboard look
# like the same product.
# ---------------------------------------------------------------------------

BRAND_INDIGO = '#1E1B4B'          # primary header band + brand mark
BRAND_INDIGO_LIGHT = '#312E81'    # button hover / accent
BRAND_SAFFRON = '#F59E0B'         # CTA / critical accent
BRAND_TEXT_PRIMARY = '#111827'    # near-black for KPI numbers
BRAND_TEXT_SECONDARY = '#4B5563'  # body copy
BRAND_BG_SOFT = '#F9FAFB'         # tile / table background
BRAND_BORDER = '#E5E7EB'          # 1px separators
BRAND_CRITICAL = '#DC2626'        # critical alert chip
BRAND_SUCCESS = '#059669'         # positive delta

DASHBOARD_PATH = '/admin/dashboard'


# ---------------------------------------------------------------------------
# Founder-personal-number guard. Mirrors `core/services/wa_broadcast.py`.
# Two forms — with and without the +91 country-code prefix. The literal is
# loaded at import time from the ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` env var
# so it never appears in a tracked source file (founder rule).
# ---------------------------------------------------------------------------

_FOUNDER_DIGIT_RE = re.compile(r'\D+')


def _build_founder_digits() -> tuple[str, str]:
    raw = os.getenv('TRAINPLEX_FOUNDER_MOBILE_GUARD', '').strip()
    digits = _FOUNDER_DIGIT_RE.sub('', raw)
    if len(digits) >= 10:
        last_ten = digits[-10:]
        return ('91' + last_ten, last_ten)
    return ('___NEVER_MATCH_WITH_CC___', '___NEVER_MATCH_NO_CC___')


_FOUNDER_PERSONAL_MOBILE_DIGITS_WITH_CC, _FOUNDER_PERSONAL_MOBILE_DIGITS_NO_CC = (
    _build_founder_digits()
)


def _digits_only(text: str) -> str:
    return _FOUNDER_DIGIT_RE.sub('', text or '')


def _assert_no_founder_personal_number(payload: Any) -> None:
    """Raise if the founder's personal mobile sneaks into a payload.

    Walks dicts / lists / strings the same way the WhatsApp broadcast guard
    does. Placed at the email-render boundary so a bug elsewhere can't leak
    the founder's private number to a third-party inbox.
    """
    if payload is None:
        return
    if isinstance(payload, str):
        digits = _digits_only(payload)
        if (
            _FOUNDER_PERSONAL_MOBILE_DIGITS_WITH_CC in digits
            or _FOUNDER_PERSONAL_MOBILE_DIGITS_NO_CC in digits
        ):
            raise ValueError(
                'Daily report aborted: founder personal mobile detected in payload.'
            )
        return
    if isinstance(payload, dict):
        for v in payload.values():
            _assert_no_founder_personal_number(v)
        return
    if isinstance(payload, (list, tuple, set)):
        for v in payload:
            _assert_no_founder_personal_number(v)
        return
    _assert_no_founder_personal_number(str(payload))


# ---------------------------------------------------------------------------
# Summary builder — MOCK for Phase 1, with two signals already real.
# ---------------------------------------------------------------------------


def _resolve_report_date(date: Optional[Any]) -> _date_type:
    """Normalise the optional `date` argument to a `datetime.date`.

    None → yesterday in server TZ. Strings are parsed as ISO `YYYY-MM-DD`
    so the management command can pass `--date 2026-05-14` straight through.
    """
    if date is None:
        return (timezone.now() - timedelta(days=1)).date()
    if isinstance(date, datetime):
        return date.date()
    if isinstance(date, _date_type):
        return date
    if isinstance(date, str):
        return datetime.strptime(date.strip(), '%Y-%m-%d').date()
    raise TypeError(f'Unsupported date type: {type(date).__name__}')


def _real_quality_alert_counts() -> Dict[str, int]:
    """Live counts from `htx_quality_alert` (already real in Phase 1).

    Defensive against (a) the model class being unavailable (early-import,
    schema not loaded), (b) the underlying table being missing (migration
    pending). In both cases we log + return zeros so the daily report
    still ships — a missing signal table should not block the email.
    """
    try:
        from core.models_alerts import QualityAlert
        open_qs = QualityAlert.objects.filter(status=QualityAlert.STATUS_OPEN)
        return {
            'open': open_qs.count(),
            'critical': open_qs.filter(
                severity=QualityAlert.SEVERITY_CRITICAL
            ).count(),
        }
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            'daily_report_email: QualityAlert counts unavailable (%s), '
            'returning zeros.', exc,
        )
        return {'open': 0, 'critical': 0}


def _real_audit_log_event_counts(report_date: _date_type) -> Dict[str, int]:
    """Live counts from `users.AuditLog` scoped to `report_date` (UTC day).

    We surface (a) the total event count, (b) the failed-login subset, and
    (c) the delete subset — these are the two action types the founder
    most cares about on a morning brief (security signal + destructive op).

    Same defensive contract as `_real_quality_alert_counts`: a missing
    model class or table degrades to zeros + log line, not an exception.
    """
    try:
        from users.models import AuditLog
        # Make the day boundary TZ-aware when Django has USE_TZ on — otherwise
        # the ORM emits a RuntimeWarning + interprets naive datetimes in UTC,
        # which is fine for the count but produces noisy logs. We always
        # promote to the project's current TZ for cleanliness.
        naive_start = datetime.combine(report_date, datetime.min.time())
        if getattr(settings, 'USE_TZ', False):
            start = timezone.make_aware(
                naive_start, timezone.get_current_timezone()
            )
        else:
            start = naive_start
        end = start + timedelta(days=1)
        day_qs = AuditLog.objects.filter(created_at__gte=start, created_at__lt=end)
        return {
            'total': day_qs.count(),
            'login_fail': day_qs.filter(action=AuditLog.ACTION_LOGIN_FAIL).count(),
            'delete': day_qs.filter(action=AuditLog.ACTION_DELETE).count(),
        }
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            'daily_report_email: AuditLog counts unavailable (%s), '
            'returning zeros.', exc,
        )
        return {'total': 0, 'login_fail': 0, 'delete': 0}


def build_daily_summary(date: Optional[Any] = None) -> Dict[str, Any]:
    """Return the dict the email renderer consumes.

    Parameters
    ----------
    date : datetime.date | datetime.datetime | str (YYYY-MM-DD) | None
        The day this brief summarises. ``None`` → yesterday.

    Returns
    -------
    dict
        Required keys (UI contract — keep in sync with `render_email_html`)::

            report_date              str  YYYY-MM-DD
            generated_at             str  ISO 8601 ending in Z
            submissions_count        int
            active_trainers_count    int
            revenue_inr              int  (mock; whole rupees, no paise)
            payout_released_inr      int  (mock; whole rupees)
            top_3_trainers           list[ {id, name, state, earnings_inr} ]
            quality_alerts_open_count       int  (real)
            quality_alerts_critical_count   int  (real)
            audit_log_events_count          int  (real)
            audit_log_login_fail_count      int  (real)
            audit_log_delete_count          int  (real)

    TODO Phase 2 (Step 8): replace `_MOCK_*` lookups with real aggregation
    queries against Submissions + Payouts tables. The public shape above is
    locked so the renderer + tests + frontend digest pickup are stable.
    """
    report_date = _resolve_report_date(date)

    # --- MOCK KPIs (TODO Phase 2 Step 8 — replace with real aggregation) ---
    submissions_count = 1_842
    active_trainers_count = 87
    revenue_inr = 92_100
    payout_released_inr = 78_400
    top_3_trainers: List[Dict[str, Any]] = [
        {'id': 5, 'name': 'Geeta P.', 'state': 'Rajasthan', 'earnings_inr': 4_350},
        {'id': 7, 'name': 'Sunil M.', 'state': 'UP', 'earnings_inr': 4_100},
        {'id': 12, 'name': 'Anil K.', 'state': 'Bihar', 'earnings_inr': 3_900},
    ]

    # --- REAL signals (already wired in Phase 1) ---
    quality = _real_quality_alert_counts()
    audit = _real_audit_log_event_counts(report_date)

    summary: Dict[str, Any] = {
        'report_date': report_date.isoformat(),
        'generated_at': timezone.now().isoformat().replace('+00:00', 'Z'),
        'submissions_count': int(submissions_count),
        'active_trainers_count': int(active_trainers_count),
        'revenue_inr': int(revenue_inr),
        'payout_released_inr': int(payout_released_inr),
        'top_3_trainers': top_3_trainers,
        'quality_alerts_open_count': int(quality['open']),
        'quality_alerts_critical_count': int(quality['critical']),
        'audit_log_events_count': int(audit['total']),
        'audit_log_login_fail_count': int(audit['login_fail']),
        'audit_log_delete_count': int(audit['delete']),
        # Carry a marker so the renderer can stamp "Phase 1 mock" on the
        # KPI tiles until Phase 2 lands — keeps the founder honest about
        # what's wired vs not.
        'mock_kpis': True,
    }
    return summary


# ---------------------------------------------------------------------------
# Rendering — plain Python string templating (no Jinja2 dep). We keep the
# HTML inline so the cron has zero file-system dependencies at run-time.
# ---------------------------------------------------------------------------


def _format_inr(amount: int) -> str:
    """Indian rupee formatting with the lakh/crore comma style.

    `12,34,567` not `1,234,567`. We special-case zero and small values so
    the formatter doesn't print `0,00,000` style monstrosities.
    """
    n = int(amount)
    s = str(abs(n))
    if len(s) <= 3:
        out = s
    else:
        head, tail = s[:-3], s[-3:]
        # Group the head in pairs from the right.
        groups = []
        while len(head) > 2:
            groups.append(head[-2:])
            head = head[:-2]
        if head:
            groups.append(head)
        out = ','.join(reversed(groups)) + ',' + tail
    return f'-{out}' if n < 0 else out


def _absolute_dashboard_url() -> str:
    """Return the dashboard URL for the CTA button.

    Reads ``settings.HOSTNAME`` if set (it's an opt-in env var, already
    parsed in `core/settings/base.py`). Falls back to a relative path so
    the email never advertises a wrong absolute URL when ops haven't
    configured HOST yet.
    """
    host = getattr(settings, 'HOSTNAME', '') or ''
    host = host.rstrip('/')
    if not host:
        return DASHBOARD_PATH
    return f'{host}{DASHBOARD_PATH}'


def _render_kpi_tile(label_en: str, label_hi: str, value: str, accent: str) -> str:
    return f"""
      <td style="padding:8px;width:50%;vertical-align:top;">
        <div style="background:{BRAND_BG_SOFT};border:1px solid {BRAND_BORDER};
                    border-left:4px solid {accent};border-radius:6px;
                    padding:14px 16px;">
          <div style="font-size:12px;color:{BRAND_TEXT_SECONDARY};
                      text-transform:uppercase;letter-spacing:0.04em;">{label_en}</div>
          <div style="font-size:11px;color:{BRAND_TEXT_SECONDARY};margin-top:2px;">
            {label_hi}
          </div>
          <div style="font-size:28px;font-weight:700;color:{BRAND_TEXT_PRIMARY};
                      margin-top:8px;line-height:1.1;">{value}</div>
        </div>
      </td>
    """


def _render_top_trainers_table(top_trainers: List[Dict[str, Any]]) -> str:
    if not top_trainers:
        return (
            f'<p style="color:{BRAND_TEXT_SECONDARY};font-style:italic;">'
            f'No trainer activity for this day / कोई trainer activity नहीं।'
            f'</p>'
        )
    rows_html = []
    for idx, t in enumerate(top_trainers, start=1):
        rows_html.append(f"""
          <tr>
            <td style="padding:10px 12px;border-bottom:1px solid {BRAND_BORDER};
                       color:{BRAND_TEXT_SECONDARY};font-size:13px;">#{idx}</td>
            <td style="padding:10px 12px;border-bottom:1px solid {BRAND_BORDER};
                       color:{BRAND_TEXT_PRIMARY};font-size:14px;font-weight:600;">
              {t.get('name', '')}
            </td>
            <td style="padding:10px 12px;border-bottom:1px solid {BRAND_BORDER};
                       color:{BRAND_TEXT_SECONDARY};font-size:13px;">
              {t.get('state', '')}
            </td>
            <td style="padding:10px 12px;border-bottom:1px solid {BRAND_BORDER};
                       color:{BRAND_TEXT_PRIMARY};font-size:14px;text-align:right;">
              ₹{_format_inr(t.get('earnings_inr', 0))}
            </td>
          </tr>
        """)
    return f"""
      <table cellpadding="0" cellspacing="0" border="0"
             style="width:100%;border-collapse:collapse;
                    background:{BRAND_BG_SOFT};
                    border:1px solid {BRAND_BORDER};border-radius:6px;
                    overflow:hidden;">
        <thead>
          <tr>
            <th style="padding:10px 12px;text-align:left;background:#FFFFFF;
                       color:{BRAND_TEXT_SECONDARY};font-size:11px;
                       text-transform:uppercase;letter-spacing:0.04em;">#</th>
            <th style="padding:10px 12px;text-align:left;background:#FFFFFF;
                       color:{BRAND_TEXT_SECONDARY};font-size:11px;
                       text-transform:uppercase;letter-spacing:0.04em;">
              Trainer / प्रशिक्षक
            </th>
            <th style="padding:10px 12px;text-align:left;background:#FFFFFF;
                       color:{BRAND_TEXT_SECONDARY};font-size:11px;
                       text-transform:uppercase;letter-spacing:0.04em;">
              State / राज्य
            </th>
            <th style="padding:10px 12px;text-align:right;background:#FFFFFF;
                       color:{BRAND_TEXT_SECONDARY};font-size:11px;
                       text-transform:uppercase;letter-spacing:0.04em;">
              Earnings / कमाई
            </th>
          </tr>
        </thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    """


def render_email_html(summary: Dict[str, Any]) -> str:
    """Render the bilingual HTML body for `summary`.

    Layout:
      Indigo header band → date subtitle →
      4-tile KPI grid (Submissions / Revenue / Active trainers / Critical alerts) →
      Top 3 trainers table →
      Quality + audit signal strip →
      "View full dashboard" CTA →
      Bilingual footer with TrainPlex brand line.

    Defensively `_assert_no_founder_personal_number(...)` is run over the
    rendered HTML — see module docstring for rationale.
    """
    if not isinstance(summary, dict):
        raise TypeError('summary must be a dict')

    # Even though build_daily_summary is the canonical source, allow a
    # bare dict from a future caller / test by falling back to safe defaults.
    submissions = summary.get('submissions_count', 0)
    active_trainers = summary.get('active_trainers_count', 0)
    revenue = summary.get('revenue_inr', 0)
    payout = summary.get('payout_released_inr', 0)
    top_trainers = summary.get('top_3_trainers', []) or []
    critical_count = summary.get('quality_alerts_critical_count', 0)
    alerts_open = summary.get('quality_alerts_open_count', 0)
    audit_total = summary.get('audit_log_events_count', 0)
    audit_login_fail = summary.get('audit_log_login_fail_count', 0)
    audit_delete = summary.get('audit_log_delete_count', 0)
    report_date = summary.get('report_date', '')
    mock_kpis = summary.get('mock_kpis', False)

    cta_url = _absolute_dashboard_url()

    mock_strip = ''
    if mock_kpis:
        mock_strip = (
            f'<div style="font-size:11px;color:{BRAND_TEXT_SECONDARY};'
            f'background:#FEF3C7;border:1px solid #FCD34D;border-radius:4px;'
            f'padding:8px 12px;margin:0 0 16px 0;">'
            f'<strong>Phase 1 note / Phase 1 सूचना:</strong> '
            f'Submissions / revenue / payouts are mock values until Phase 2 '
            f'wiring (Step 8). Real signals: quality alerts + audit log.'
            f'</div>'
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>TrainPlex daily report — {report_date}</title>
</head>
<body style="margin:0;padding:0;background:#F3F4F6;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,
                         'Helvetica Neue',Arial,sans-serif;
             color:{BRAND_TEXT_PRIMARY};">
  <table cellpadding="0" cellspacing="0" border="0"
         style="width:100%;max-width:640px;margin:0 auto;
                background:#FFFFFF;border:1px solid {BRAND_BORDER};">
    <!-- Indigo header band -->
    <tr>
      <td style="background:{BRAND_INDIGO};color:#FFFFFF;
                 padding:24px 28px;">
        <div style="font-size:13px;letter-spacing:0.08em;
                    text-transform:uppercase;opacity:0.8;">
          TrainPlex Studio — Daily Founder Report
        </div>
        <div style="font-size:22px;font-weight:700;margin-top:4px;">
          Yesterday at a glance / कल का हाल
        </div>
        <div style="font-size:13px;margin-top:6px;opacity:0.85;">
          {report_date} (IST)
        </div>
      </td>
    </tr>

    <!-- Body -->
    <tr>
      <td style="padding:24px 20px;">

        {mock_strip}

        <h2 style="font-size:14px;color:{BRAND_TEXT_SECONDARY};
                   text-transform:uppercase;letter-spacing:0.06em;
                   margin:0 0 12px 0;">
          Headline KPIs / मुख्य आँकड़े
        </h2>

        <!-- 4-tile KPI grid (2x2) -->
        <table cellpadding="0" cellspacing="0" border="0"
               style="width:100%;border-collapse:separate;border-spacing:0;">
          <tr>
            {_render_kpi_tile('Submissions', 'जमा कार्य', str(submissions), BRAND_INDIGO)}
            {_render_kpi_tile('Revenue (INR)', 'कुल आमदनी', f'₹{_format_inr(revenue)}', BRAND_SUCCESS)}
          </tr>
          <tr>
            {_render_kpi_tile('Active trainers', 'सक्रिय प्रशिक्षक', str(active_trainers), BRAND_SAFFRON)}
            {_render_kpi_tile('Critical alerts', 'गंभीर alerts', str(critical_count), BRAND_CRITICAL)}
          </tr>
        </table>

        <p style="font-size:12px;color:{BRAND_TEXT_SECONDARY};margin:10px 8px 24px;">
          Payouts released yesterday / कल जारी payouts: <strong>₹{_format_inr(payout)}</strong>
          &nbsp;·&nbsp; Open quality alerts / खुले quality alerts:
          <strong>{alerts_open}</strong>
        </p>

        <h2 style="font-size:14px;color:{BRAND_TEXT_SECONDARY};
                   text-transform:uppercase;letter-spacing:0.06em;
                   margin:8px 0 12px 0;">
          Top 3 trainers / शीर्ष 3 प्रशिक्षक
        </h2>
        {_render_top_trainers_table(top_trainers)}

        <h2 style="font-size:14px;color:{BRAND_TEXT_SECONDARY};
                   text-transform:uppercase;letter-spacing:0.06em;
                   margin:24px 0 8px 0;">
          Security &amp; quality signals / सुरक्षा एवं quality signals
        </h2>
        <ul style="margin:0 0 16px 18px;padding:0;color:{BRAND_TEXT_PRIMARY};
                   font-size:13px;line-height:1.6;">
          <li>Audit events / Audit events: <strong>{audit_total}</strong></li>
          <li>Login failures / Login failures: <strong>{audit_login_fail}</strong></li>
          <li>Delete events / Delete events: <strong>{audit_delete}</strong></li>
        </ul>

        <!-- CTA -->
        <p style="text-align:center;margin:28px 0 4px;">
          <a href="{cta_url}"
             style="display:inline-block;background:{BRAND_INDIGO};
                    color:#FFFFFF;text-decoration:none;font-weight:600;
                    padding:12px 22px;border-radius:6px;font-size:14px;">
            View full dashboard
          </a>
        </p>
        <p style="text-align:center;font-size:12px;
                  color:{BRAND_TEXT_SECONDARY};margin:0 0 8px 0;">
          पूरा डैशबोर्ड देखें — {cta_url}
        </p>

      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="background:{BRAND_BG_SOFT};border-top:1px solid {BRAND_BORDER};
                 padding:18px 28px;font-size:11px;color:{BRAND_TEXT_SECONDARY};">
        <div>
          TrainPlex Studio · India · Data labeling at scale.
        </div>
        <div style="margin-top:4px;">
          Yeh automated daily report hai — reply karne ki zaroorat nahi.
          Daily delivery 8:00 AM IST.
        </div>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    # Defensive: never let the founder's personal mobile slip into a
    # rendered email body (subject + recipient are checked in send_*).
    _assert_no_founder_personal_number(html)
    return html


def render_email_text(summary: Dict[str, Any]) -> str:
    """Plain-text fallback for email clients that don't render HTML."""
    if not isinstance(summary, dict):
        raise TypeError('summary must be a dict')

    submissions = summary.get('submissions_count', 0)
    active = summary.get('active_trainers_count', 0)
    revenue = summary.get('revenue_inr', 0)
    payout = summary.get('payout_released_inr', 0)
    crit = summary.get('quality_alerts_critical_count', 0)
    alerts_open = summary.get('quality_alerts_open_count', 0)
    audit_total = summary.get('audit_log_events_count', 0)
    audit_fail = summary.get('audit_log_login_fail_count', 0)
    audit_del = summary.get('audit_log_delete_count', 0)
    report_date = summary.get('report_date', '')
    top = summary.get('top_3_trainers', []) or []

    lines = [
        f'TrainPlex Studio — Daily Founder Report ({report_date})',
        'Yesterday at a glance / कल का हाल',
        '',
        f'Submissions / जमा कार्य:        {submissions}',
        f'Revenue / कुल आमदनी:           Rs. {_format_inr(revenue)}',
        f'Active trainers / सक्रिय:       {active}',
        f'Payouts released / जारी payouts: Rs. {_format_inr(payout)}',
        f'Quality alerts open / खुले:     {alerts_open}',
        f'Critical alerts / गंभीर:        {crit}',
        f'Audit events / Audit events:    {audit_total}',
        f'Login failures / Login failures:{audit_fail}',
        f'Delete events / Delete events:  {audit_del}',
        '',
        'Top 3 trainers / शीर्ष 3 प्रशिक्षक:',
    ]
    if top:
        for idx, t in enumerate(top, start=1):
            lines.append(
                f'  #{idx} {t.get("name", "")} '
                f'({t.get("state", "")}) — Rs. '
                f'{_format_inr(t.get("earnings_inr", 0))}'
            )
    else:
        lines.append('  (no trainer activity / कोई trainer activity नहीं)')

    lines += [
        '',
        f'Full dashboard: {_absolute_dashboard_url()}',
        '',
        '— TrainPlex Studio (automated daily 8:00 AM IST)',
    ]
    body = '\n'.join(lines)
    _assert_no_founder_personal_number(body)
    return body


# ---------------------------------------------------------------------------
# Sending — wraps the configured Django email backend.
# ---------------------------------------------------------------------------


def _resolve_recipient(recipient_email: Optional[str]) -> str:
    """Return a non-empty recipient or raise.

    ``settings.TRAINPLEX_FOUNDER_EMAIL`` is the default, sourced from env at
    settings-load. We never hard-code an email here — see module docstring.
    """
    if recipient_email:
        return recipient_email.strip()
    fallback = getattr(settings, 'TRAINPLEX_FOUNDER_EMAIL', '') or ''
    if not fallback:
        raise ValueError(
            'No recipient_email passed and TRAINPLEX_FOUNDER_EMAIL is not '
            'set in settings — refusing to send a daily report to nowhere.'
        )
    return fallback.strip()


def send_daily_report(
    recipient_email: Optional[str],
    summary: Dict[str, Any],
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Wrap the configured email backend to deliver one daily-report email.

    Parameters
    ----------
    recipient_email : str | None
        Where to send. ``None`` → use ``settings.TRAINPLEX_FOUNDER_EMAIL``.
    summary : dict
        Output of `build_daily_summary(...)`.
    dry_run : bool, keyword-only
        If True, render the email but DO NOT call ``send()``. Useful for
        cron smoke tests + the management command's ``--dry-run`` flag.

    Returns
    -------
    dict
        ``{'sent': bool, 'recipient': str, 'subject': str, 'dry_run': bool,
           'preview_len': int, 'mode': str}``

    Notes
    -----
    * We use Django's ``EmailMultiAlternatives`` so the HTML body is paired
      with a plain-text fallback (better deliverability + safer for screen
      readers).
    * The backend itself is whatever ``settings.EMAIL_BACKEND`` resolves to.
      In dev that's ``dummy`` (no real send); in prod the founder configures
      SMTP / Sendgrid via env. We never override here — see "DO NOT" in the
      module docstring.
    * `mode` is ``mock`` when the dummy backend is in use (which mirrors
      Phase 1's WhatsApp wiring — log the intent, don't actually email,
      so cron smoke tests don't bombard inboxes).
    """
    recipient = _resolve_recipient(recipient_email)
    _assert_no_founder_personal_number(recipient)

    report_date = summary.get('report_date', 'today')
    subject = f'TrainPlex daily report — {report_date}'
    _assert_no_founder_personal_number(subject)

    html_body = render_email_html(summary)
    text_body = render_email_text(summary)

    backend = (getattr(settings, 'EMAIL_BACKEND', '') or '').lower()
    is_dummy_backend = 'dummy' in backend or 'console' in backend
    mode = 'mock' if is_dummy_backend else 'live'

    if dry_run:
        logger.info(
            'TrainPlex daily report DRY-RUN: subject=%r recipient=%r '
            'html_len=%d text_len=%d backend=%s '
            '(TODO Phase 2: register with django-q / celery beat at 08:00 IST)',
            subject, recipient, len(html_body), len(text_body), backend,
        )
        return {
            'sent': False,
            'recipient': recipient,
            'subject': subject,
            'dry_run': True,
            'preview_len': len(html_body),
            'mode': mode,
        }

    from_email = getattr(settings, 'FROM_EMAIL', 'TrainPlex <hello@trainplex.in>')
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[recipient],
    )
    message.attach_alternative(html_body, 'text/html')

    sent_count = message.send(fail_silently=False)
    logger.info(
        'TrainPlex daily report send attempted: subject=%r recipient=%r '
        'backend=%s mode=%s sent_count=%s',
        subject, recipient, backend, mode, sent_count,
    )
    return {
        'sent': bool(sent_count),
        'recipient': recipient,
        'subject': subject,
        'dry_run': False,
        'preview_len': len(html_body),
        'mode': mode,
    }


# Re-exports for convenience.
__all__ = [
    'BRAND_INDIGO',
    'BRAND_SAFFRON',
    'DASHBOARD_PATH',
    'build_daily_summary',
    'render_email_html',
    'render_email_text',
    'send_daily_report',
]

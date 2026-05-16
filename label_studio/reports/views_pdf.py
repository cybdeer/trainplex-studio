"""Reports PDF export endpoints — render real-data payloads to branded PDF.

WAVE-19 W1-PDF-VIEW (F-8): Parallel PDF view module for the 4 founder reports.
Routes are NOT wired here — Z2-URLS handles `urls.py` in Wave 2.

Backend selection
-----------------
1. weasyprint (HTML -> PDF, branded) if importable
2. reportlab  (Platypus text fallback) otherwise — installed at container
   boot by deploy/docker-entrypoint.d/app-init/90-install-pdf-deps.sh

Service signatures (verified against on-disk services 2026-05-16):
    build_founder_weekly_snapshot(week_start: Optional[date] = None)
    build_leaderboard(period: str = 'weekly', ...)
    compute_cohort_metrics(...)
    compute_project_roi(project_id: int)
"""
import io
from datetime import datetime

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from users.decorators import require_role

try:
    from weasyprint import HTML as _PDFEngine
    _BACKEND = "weasyprint"
except Exception:  # pragma: no cover - native deps usually absent
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    _PDFEngine = None
    _BACKEND = "reportlab"


FOUNDER_WEEKLY_HTML_TEMPLATE = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body { font-family: Arial, sans-serif; color: #1a1a5e; padding: 40px; }
  h1 { color: #1a1a5e; border-bottom: 3px solid #ff6b35; padding-bottom: 8px; }
  .kpi { display: inline-block; margin: 12px; padding: 16px; border: 1px solid #e2e8f0; }
  .kpi-value { font-size: 28px; font-weight: 700; }
  table { width: 100%%; border-collapse: collapse; margin-top: 24px; }
  th { background: #1a1a5e; color: white; padding: 8px; text-align: left; }
  td { padding: 6px; border-bottom: 1px solid #e2e8f0; }
  .footer { margin-top: 40px; font-size: 11px; color: #94a3b8; }
</style></head><body>
  <h1>TrainPlex — Founder Weekly Report</h1>
  <p>Generated: %(generated_at)s</p>
  <div class="kpi-row">
    <div class="kpi"><div>Submissions/week</div><div class="kpi-value">%(submissions_weekly)s</div></div>
    <div class="kpi"><div>Active trainers</div><div class="kpi-value">%(active_trainers)s</div></div>
    <div class="kpi"><div>Revenue (INR)</div><div class="kpi-value">₹%(revenue_inr)s</div></div>
  </div>
  <div class="footer">TrainPlex Studio · Made in Jaipur · Cybdeer Network Pvt Ltd</div>
</body></html>
"""


def render_pdf(html_str: str) -> bytes:
    """Render an HTML string to PDF bytes, using whichever backend is available."""
    if _BACKEND == "weasyprint":
        return _PDFEngine(string=html_str).write_pdf()
    # reportlab fallback — flatten HTML into a single paragraph (escaped),
    # so the response is a valid PDF even without WeasyPrint's HTML pipeline.
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf)
    styles = getSampleStyleSheet()
    safe = html_str.replace("<", "&lt;").replace(">", "&gt;")
    doc.build([Paragraph(safe, styles["Normal"])])
    return buf.getvalue()


def _extract_weekly_kpis(payload: dict) -> dict:
    """Pull the three KPI numbers out of the founder-weekly snapshot.

    The snapshot uses nested `top_kpis` with sub-dicts {value, ...}. We fall
    back to top-level keys (for older callers) and finally to 0 so the template
    never KeyErrors.
    """
    top = payload.get("top_kpis") or {}

    def _kv(key: str, default=0):
        node = top.get(key)
        if isinstance(node, dict):
            return node.get("value", default)
        if node is not None:
            return node
        return payload.get(key, default)

    return {
        "submissions_weekly": _kv("submissions_weekly", 0),
        "active_trainers": _kv("active_trainers", 0),
        "revenue_inr": _kv("revenue_inr", 0),
    }


class FounderWeeklyPDFView(APIView):
    """Admin-only PDF export of the founder weekly snapshot."""
    permission_classes = (IsAuthenticated,)

    @require_role(["admin"])
    def get(self, request):
        from reports.services.founder_weekly import build_founder_weekly_snapshot
        payload = build_founder_weekly_snapshot()
        kpis = _extract_weekly_kpis(payload)
        html = FOUNDER_WEEKLY_HTML_TEMPLATE % {
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "submissions_weekly": kpis["submissions_weekly"],
            "active_trainers": kpis["active_trainers"],
            "revenue_inr": kpis["revenue_inr"],
        }
        pdf = render_pdf(html)
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = (
            f'attachment; filename="trainplex-weekly-{datetime.now():%Y-%m-%d}.pdf"'
        )
        return resp


class LeaderboardPDFView(APIView):
    """Admin-only PDF export of the trainer leaderboard (weekly)."""
    permission_classes = (IsAuthenticated,)

    @require_role(["admin"])
    def get(self, request):
        from reports.services.leaderboard import build_leaderboard
        data = build_leaderboard(period="weekly")
        html = (
            "<html><body><h1>TrainPlex — Leaderboard (weekly)</h1>"
            "<pre>" + str(data) + "</pre></body></html>"
        )
        resp = HttpResponse(render_pdf(html), content_type="application/pdf")
        resp["Content-Disposition"] = (
            f'attachment; filename="trainplex-leaderboard-{datetime.now():%Y-%m-%d}.pdf"'
        )
        return resp


class CohortsPDFView(APIView):
    """Admin-only PDF export of cohort retention/productivity/earnings."""
    permission_classes = (IsAuthenticated,)

    @require_role(["admin"])
    def get(self, request):
        from reports.services.cohort_analyzer import compute_cohort_metrics
        data = compute_cohort_metrics()
        html = (
            "<html><body><h1>TrainPlex — Cohort Analysis</h1>"
            "<pre>" + str(data) + "</pre></body></html>"
        )
        resp = HttpResponse(render_pdf(html), content_type="application/pdf")
        resp["Content-Disposition"] = (
            f'attachment; filename="trainplex-cohorts-{datetime.now():%Y-%m-%d}.pdf"'
        )
        return resp


class ProjectROIPDFView(APIView):
    """Admin-only PDF export of a single project's ROI breakdown."""
    permission_classes = (IsAuthenticated,)

    @require_role(["admin"])
    def get(self, request, pk):
        from reports.services.project_roi import compute_project_roi
        data = compute_project_roi(project_id=pk) or {}
        html = (
            f"<html><body><h1>TrainPlex — Project ROI #{pk}</h1>"
            "<pre>" + str(data) + "</pre></body></html>"
        )
        resp = HttpResponse(render_pdf(html), content_type="application/pdf")
        resp["Content-Disposition"] = (
            f'attachment; filename="trainplex-project-{pk}-roi-{datetime.now():%Y-%m-%d}.pdf"'
        )
        return resp

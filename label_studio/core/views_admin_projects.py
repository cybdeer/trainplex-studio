"""Admin project wizard — POST /api/v1/admin/projects/wizard.

Creates Project from XML template + CSV tasks.

Wave 19 / W1-WIZARD-VIEW (2026-05-16)
------------------------------------
View only — URL wiring is delivered atomically by W2-URLS in Wave 2.
This module is mounted into the running app container via
docker-compose.override.yml but is **not** routed yet, so importing it
alone has no side effects on serving traffic.
"""
from pathlib import Path
import csv
import io

from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project
from tasks.models import Task
from users.decorators import require_role

# Inside the app container, the host-side ls_templates dir is bind-mounted
# at /label-studio/backend/data/ls_templates (see docker-compose.override.yml).
TEMPLATE_DIR = Path("/label-studio/backend/data/ls_templates")


class ProjectWizardAPI(APIView):
    """POST endpoint for the admin project-creation wizard."""

    permission_classes = (IsAuthenticated,)

    @require_role(["admin"])
    def post(self, request):
        title = (request.data.get("title") or "").strip()
        template_id = request.data.get("template_id", "")
        label_config = request.data.get("label_config", "")
        csv_data = request.data.get("csv_data", "")
        # assignees accepted but consumed by a later wave (W3 membership wiring).
        _ = request.data.get("assignees", [])

        if not title:
            return Response({"detail": "title required"}, status=400)

        # Resolve label_config from template_id when caller did not inline XML.
        if not label_config and template_id:
            xml_path = TEMPLATE_DIR / f"{template_id}.xml"
            if xml_path.exists():
                label_config = xml_path.read_text()
            else:
                return Response(
                    {"detail": f"template {template_id} not found"},
                    status=404,
                )

        org = request.user.active_organization

        with transaction.atomic():
            project = Project.objects.create(
                title=title,
                label_config=label_config,
                organization=org,
            )
            tasks_created = 0
            if csv_data:
                reader = csv.DictReader(io.StringIO(csv_data))
                for row in reader:
                    Task.objects.create(project=project, data=dict(row))
                    tasks_created += 1

        return Response(
            {
                "project_id": project.id,
                "project_code": f"RLHF-2026-{project.id:03d}",
                "tasks_created": tasks_created,
                "status": "ready",
            },
            status=201,
        )

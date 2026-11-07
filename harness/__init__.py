"""
Dialogue Engine - Harness Test Package.
Пакет автоматического тестирования сценария, графа диалогов и ассетов.
"""

from __future__ import annotations
from harness.models import (
    AuditIssue,
    AuditReport,
    IssueCategory,
    IssueSeverity,
    RouteEnding,
)
from harness.scenario_auditor import ScenarioAuditor
from core.serialization import ProjectSerializer
from core.models import ProjectData


def run_audit(project_or_path: str | ProjectData) -> AuditReport:
    """Универсальная функция запуска аудита по пути к .json файлу или объекту ProjectData."""
    if isinstance(project_or_path, str):
        project = ProjectSerializer.load_from_file(project_or_path)
        auditor = ScenarioAuditor(project, project_file_path=project_or_path)
    else:
        auditor = ScenarioAuditor(project_or_path)
    return auditor.run_full_audit()


__all__ = [
    "AuditIssue",
    "AuditReport",
    "IssueCategory",
    "IssueSeverity",
    "RouteEnding",
    "ScenarioAuditor",
    "run_audit",
]

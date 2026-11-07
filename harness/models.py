"""
Dialogue Engine - Harness Data Models.
Содержит структуры данных для отчётов автоматического аудита сценария и ассетов.
"""

from __future__ import annotations
import json
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IssueSeverity(str, Enum):
    CRITICAL = "CRITICAL"  # Блокирующие ошибки (вылет в Ren'Py, битые ссылки)
    ERROR = "ERROR"        # Ошибки логики (ненайденные ассеты, висячие выборы)
    WARNING = "WARNING"    # Предупреждения (недостижимые узлы, тупики)
    INFO = "INFO"          # Рекомендации (незарегистрированные персонажи, форматирование)


class IssueCategory(str, Enum):
    GRAPH_FLOW = "Сюжетный граф"
    CHOICES = "Выборы и развилки"
    CHARACTERS = "Персонажи и реплики"
    ASSETS = "Ассеты и медиа"
    LOGIC = "Логика и переменные"
    METRICS = "Метрики и баланс"


@dataclass
class AuditIssue:
    """Представление одной найденной проблемы или замечания в сценарии."""
    severity: IssueSeverity
    category: IssueCategory
    message: str
    node_id: Optional[str] = None
    node_title: str = ""
    suggestion: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "node_id": self.node_id,
            "node_title": self.node_title,
            "suggestion": self.suggestion,
            "details": dict(self.details),
        }


@dataclass
class RouteEnding:
    """Информация об одной из сюжетных концовок."""
    leaf_node_id: str
    leaf_title: str
    is_declared_ending: bool  # Имеет метку конца (Конец, Ending, # Конец)
    steps_count: int
    words_count: int
    sample_path: List[str]    # Названия узлов по маршруту


@dataclass
class AuditReport:
    """Комплексный отчёт по результатам автоматического тестирования сценария."""
    project_name: str = "Сценарий"
    total_nodes: int = 0
    total_connections: int = 0
    node_type_counts: Dict[str, int] = field(default_factory=dict)
    endings: List[RouteEnding] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    issues: List[AuditIssue] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.CRITICAL)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.INFO)

    @property
    def is_passed(self) -> bool:
        return (self.critical_count == 0 and self.error_count == 0)

    def summary(self) -> Dict[str, int]:
        return {
            "critical": self.critical_count,
            "error": self.error_count,
            "warning": self.warning_count,
            "info": self.info_count,
            "total_issues": len(self.issues),
            "endings_count": len(self.endings),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "is_passed": self.is_passed,
            "summary": self.summary(),
            "stats": self.stats,
            "node_type_counts": self.node_type_counts,
            "endings": [
                {
                    "leaf_id": e.leaf_node_id,
                    "title": e.leaf_title,
                    "is_ending": e.is_declared_ending,
                    "steps": e.steps_count,
                    "words": e.words_count,
                    "path_preview": " › ".join(e.sample_path[:4]) + ("..." if len(e.sample_path) > 4 else "")
                }
                for e in self.endings
            ],
            "issues": [i.to_dict() for i in self.issues],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_text(self) -> str:
        """Форматирует сводку в читаемый консольный текст с рамками и статусами."""
        status_icon = "✅ ПРОЙДЕН" if self.is_passed else "❌ НАЙДЕНЫ ОШИБКИ"
        lines = [
            "=" * 70,
            f" 🧪 АВТО-ТЕСТ СЦЕНАРИЯ: {self.project_name}",
            f" Статус: {status_icon} | Узлов: {self.total_nodes} | Связей: {self.total_connections}",
            "=" * 70,
            f" Критических: {self.critical_count} | Ошибок: {self.error_count} | Предупреждений: {self.warning_count} | Инфо: {self.info_count}",
            f" Найдено сюжетных концовок: {len(self.endings)}",
        ]

        if self.stats:
            lines.append("-" * 70)
            lines.append(" 📊 СТАТИСТИКА И МЕТРИКИ:")
            for k, v in self.stats.items():
                lines.append(f"   • {k}: {v}")

        if self.endings:
            lines.append("-" * 70)
            lines.append(" 🏁 СЮЖЕТНЫЕ КОНЦОВКИ И ФИНАЛЫ:")
            for idx, e in enumerate(self.endings, 1):
                end_mark = "🏆 [Финал]" if e.is_declared_ending else "⚠️ [Тупик]"
                route_str = " › ".join(e.sample_path[-3:])
                lines.append(f"   {idx}. {end_mark} '{e.leaf_title}' ({e.steps_count} шагов, ~{e.words_count} слов) — путь: ... › {route_str}")

        if self.issues:
            lines.append("-" * 70)
            lines.append(f" 🔍 НАЙДЕННЫЕ ЗАМЕЧАНИЯ ({len(self.issues)}):")
            for i, issue in enumerate(self.issues, 1):
                nid_str = f" [ID:{issue.node_id}]" if issue.node_id else ""
                title_str = f" '{issue.node_title}'" if issue.node_title else ""
                lines.append(f"   {i}. [{issue.severity.value}] [{issue.category.value}]{nid_str}{title_str}: {issue.message}")
                if issue.suggestion:
                    lines.append(f"      💡 Совет: {issue.suggestion}")
        else:
            lines.append("-" * 70)
            lines.append(" ✨ Идеально! Сюжетный граф не имеет ошибок и тупиков.")

        lines.append("=" * 70)
        return "\n".join(lines)

    def save_log(self, filepath: Optional[str] = None) -> str:
        """Сохраняет отчёт аудита с временной меткой в файл лога."""
        if not filepath:
            filepath = "audit.log"
        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        content = [
            f"# ====================================================================",
            f"# DIALOGUE ENGINE AUDIT LOG — {timestamp_str}",
            f"# Файл проекта: {self.project_name}",
            f"# ====================================================================",
            "",
            self.to_text(),
            ""
        ]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        return os.path.abspath(filepath)

    def to_markdown(self) -> str:
        """Форматирует подробный отчёт в формат Markdown."""
        badge = "🟢 **PASSED**" if self.is_passed else "🔴 **FAILED**"
        md = [
            f"# 🧪 Отчёт тестирования сценария: {self.project_name}",
            "",
            f"**Результат:** {badge}  ",
            f"**Узлов:** `{self.total_nodes}` | **Связей:** `{self.total_connections}` | **Концовок:** `{len(self.endings)}`  ",
            f"**Критических:** `{self.critical_count}` | **Ошибок:** `{self.error_count}` | **Предупреждений:** `{self.warning_count}` | **Инфо:** `{self.info_count}`",
            "",
            "## 📊 Метрики сюжета",
            "",
        ]
        for k, v in self.stats.items():
            md.append(f"- **{k}**: {v}")

        if self.endings:
            md.extend([
                "",
                "## 🏁 Сюжетные исходы и концовки",
                "",
                "| # | Тип | Название узла | Шагов | Слов | Маршрут |",
                "|---|---|---|---|---|---|",
            ])
            for idx, e in enumerate(self.endings, 1):
                kind = "🏆 Финал" if e.is_declared_ending else "⚠️ Обрыв/Тупик"
                path_str = " › ".join(e.sample_path[:3]) + "..."
                md.append(f"| {idx} | {kind} | `{e.leaf_title}` | {e.steps_count} | {e.words_count} | `{path_str}` |")

        if self.issues:
            md.extend([
                "",
                "## 🔍 Список замечаний",
                "",
                "| # | Важность | Категория | Узел | Описание | Рекомендация |",
                "|---|---|---|---|---|---|",
            ])
            for idx, issue in enumerate(self.issues, 1):
                node_ref = f"`{issue.node_title}` (`{issue.node_id}`)" if issue.node_id else "—"
                md.append(f"| {idx} | **{issue.severity.value}** | {issue.category.value} | {node_ref} | {issue.message} | {issue.suggestion or '—'} |")
        else:
            md.extend([
                "",
                "> 🌟 **Замечаний не обнаружено!** Сценарий полностью валиден.",
            ])

        return "\n".join(md)

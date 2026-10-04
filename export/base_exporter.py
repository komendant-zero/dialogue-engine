"""
Dialogue Engine - Base Exporter Interface.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from core.models import ConnectionData, NodeData, ProjectData


class BaseExporter(ABC):
    """Абстрактный класс экспортера сценария."""

    @abstractmethod
    def export(self, project: ProjectData, output_dir: str, **kwargs) -> Tuple[bool, str]:
        """Экспортирует проект в целевой каталог. Возвращает (успех, сообщение/ошибка)."""
        pass

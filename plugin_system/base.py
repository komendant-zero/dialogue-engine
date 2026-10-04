"""
Dialogue Engine - Plugin Base & Manifest.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PluginStatus(str, Enum):
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class PluginManifest:
    """Метаданные плагина."""
    name: str
    version: str = "1.0"
    author: str = ""
    description: str = ""
    min_engine_version: str = "2.0.0"
    supported_events: List[str] = field(default_factory=list)


class Plugin:
    """
    Базовый класс для всех плагинов Dialogue Engine.
    Плагины должны наследоваться от этого класса.
    """
    name: str = "BasePlugin"
    version: str = "1.0"
    author: str = ""
    description: str = ""
    min_engine_version: str = "2.0.0"

    def __init__(self, editor: Any):
        self.editor = editor
        self.status: PluginStatus = PluginStatus.LOADED
        self.last_error: Optional[str] = None
        self.error_count: int = 0

    def on_enable(self) -> None:
        """Вызывается при успешной загрузке и включении плагина."""
        pass

    def on_disable(self) -> None:
        """Вызывается при отключении плагина."""
        pass

    def on_event(self, event_type: str, data: Any = None) -> None:
        """
        Обработка событий редактора.
        
        Распространенные события:
        - 'setup_ui': data = toolbar Frame
        - 'node_added': data = Node
        - 'node_deleted': data = Node
        - 'draw_node': data = {'node': Node, 'canvas': Canvas}
        - 'draw_node_content': data = {'node': Node, 'canvas': Canvas, 'handled': bool}
        - 'draw_node_ports': data = {'node': Node, 'canvas': Canvas, 'handled': bool}
        - 'calculate_node_size': data = {'node': Node, 'base_h': int, 'display_content': str, 'height': int, 'handled': dict}
        - 'context_menu': data = {'target': Node, 'x': float, 'y': float, 'menu': Menu}
        - 'node_edit_dialog': data = {'node': Node, 'frame': Frame, 'dialog': Toplevel}
        - 'node_edit_save': data = {'node': Node}
        - 'renpy_export_init': data = {'file': file, 'nodes': list, 'connections': list, 'export_dir': str}
        - 'renpy_export_check': data = {'node': Node, 'skip': bool}
        - 'renpy_export_node': data = {'node': Node, 'file': file, 'connections': list, 'export_dir': str, 'handled': bool}
        """
        pass

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name=getattr(self, "name", self.__class__.__name__),
            version=getattr(self, "version", "1.0"),
            author=getattr(self, "author", ""),
            description=getattr(self, "description", ""),
            min_engine_version=getattr(self, "min_engine_version", "2.0.0")
        )

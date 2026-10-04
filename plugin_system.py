"""
Dialogue Engine - Plugin System Facade (Backward Compatibility).
Все компоненты модульной системы плагинов доступны из этого модуля.
"""

from plugin_system.base import Plugin, PluginManifest, PluginStatus
from plugin_system.manager import PluginManager
from plugin_system.events import *

__all__ = [
    "Plugin",
    "PluginManifest",
    "PluginStatus",
    "PluginManager",
]
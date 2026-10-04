"""
Dialogue Engine - Plugin System Package.
"""

from plugin_system.base import Plugin, PluginManifest, PluginStatus
from plugin_system.manager import PluginManager
from plugin_system.events import (
    EVENT_SETUP_UI,
    EVENT_CONTEXT_MENU,
    EVENT_AUTOSAVE_TICK,
    EVENT_PROJECT_LOADED,
    EVENT_PROJECT_SAVED,
    EVENT_NODE_ADDED,
    EVENT_NODE_DELETED,
    EVENT_NODE_EDIT_DIALOG,
    EVENT_NODE_EDIT_SAVE,
    EVENT_DRAW_NODE,
    EVENT_DRAW_NODE_CONTENT,
    EVENT_DRAW_NODE_PORTS,
    EVENT_CALCULATE_NODE_SIZE,
    EVENT_RENPY_EXPORT_INIT,
    EVENT_RENPY_EXPORT_CHECK,
    EVENT_RENPY_EXPORT_NODE,
)

__all__ = [
    "Plugin",
    "PluginManifest",
    "PluginStatus",
    "PluginManager",
    "EVENT_SETUP_UI",
    "EVENT_CONTEXT_MENU",
    "EVENT_AUTOSAVE_TICK",
    "EVENT_PROJECT_LOADED",
    "EVENT_PROJECT_SAVED",
    "EVENT_NODE_ADDED",
    "EVENT_NODE_DELETED",
    "EVENT_NODE_EDIT_DIALOG",
    "EVENT_NODE_EDIT_SAVE",
    "EVENT_DRAW_NODE",
    "EVENT_DRAW_NODE_CONTENT",
    "EVENT_DRAW_NODE_PORTS",
    "EVENT_CALCULATE_NODE_SIZE",
    "EVENT_RENPY_EXPORT_INIT",
    "EVENT_RENPY_EXPORT_CHECK",
    "EVENT_RENPY_EXPORT_NODE",
]

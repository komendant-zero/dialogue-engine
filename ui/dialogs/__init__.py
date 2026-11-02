"""
Dialogue Engine - Dialogs Package.
"""

from ui.dialogs.node_editor import NodeEditorDialog
from ui.dialogs.search_replace import SearchReplaceDialog
from ui.dialogs.hotkey_settings import HotkeySettingsDialog
from ui.dialogs.character_manager import CharacterManagerDialog
from ui.dialogs.update_dialog import StartupSplashDialog, ManualUpdateDialog
from ui.dialogs.cowork_dialog import CoworkServerManagerDialog

__all__ = [
    "NodeEditorDialog",
    "SearchReplaceDialog",
    "HotkeySettingsDialog",
    "CharacterManagerDialog",
    "StartupSplashDialog",
    "ManualUpdateDialog",
    "CoworkServerManagerDialog",
]

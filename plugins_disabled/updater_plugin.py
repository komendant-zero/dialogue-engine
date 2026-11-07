"""
Dialogue Engine - Auto-Updater & Reloader Plugin.
Обеспечивает интеграцию автообновления и горячей перезагрузки движка.
"""

import sys
import tkinter as tk
from plugin_system.base import Plugin
from ui.dialogs.update_dialog import ManualUpdateDialog


class AutoUpdaterPlugin(Plugin):
    name = "Auto-Updater & GitHub Sync"
    version = "2.0"
    author = "Dialogue Engine Team"
    description = "Автоматическое обновление движка через GitHub и безопасный перезапуск с сохранением"

    def on_event(self, event_type, data=None):
        if event_type == "setup_ui":
            if hasattr(self.editor, "dev_menu") and not hasattr(self.editor, "open_update_dialog"):
                self.editor.dev_menu.add_separator()
                self.editor.dev_menu.add_command(
                    label="🚀 Проверить обновления GitHub...",
                    command=self.trigger_update
                )

    def trigger_update(self):
        ManualUpdateDialog(self.editor)

"""
Dialogue Engine - MCP Plugin.
Отображает статус и инструкции для подключения AI-ассистентов через Model Context Protocol.
"""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import messagebox
from plugin_system.base import Plugin


class MCPPlugin(Plugin):
    name = "MCP AI Assistant Integration"
    version = "1.0"
    author = "Dialogue Engine Team"
    description = "Интеграция с Model Context Protocol для прямого управления сценарием из AI"

    def on_event(self, event_type: str, data: Any = None) -> None:
        if event_type == "setup_ui":
            if hasattr(self.editor, "dev_menu") and self.editor.dev_menu:
                self.editor.dev_menu.add_command(
                    label="🤖 Интеграция MCP AI...",
                    command=self.show_mcp_info
                )

    def show_mcp_info(self) -> None:
        proj = getattr(self.editor, "current_file", "D:/projects/Violant/game/violant.json") or "D:/projects/Violant/game/violant.json"
        server_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp_server.py")).replace("\\", "/")

        info = (
            "🤖 Поддержка Model Context Protocol (MCP) активна!\n\n"
            f"Скрипт сервера:\n{server_py}\n\n"
            f"Текущий проект:\n{proj}\n\n"
            "Сервер готов принимать команды от Antigravity, Claude Desktop, Cursor и др.\n"
            "Все изменения от AI синхронизируются на холсте автоматически в реальном времени!"
        )
        messagebox.showinfo("MCP AI Интеграция", info, parent=self.editor)

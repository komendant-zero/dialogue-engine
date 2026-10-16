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
            parent = getattr(self.editor, "toolbar_right", data)
            tk.Button(
                parent,
                text="🤖 MCP AI",
                command=self.show_mcp_info,
                bg="#2c3e50",
                activebackground="#34495e",
                fg="#1abc9c",
                activeforeground="#2ecc71",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                padx=8,
                pady=3,
                cursor="hand2"
            ).pack(side=tk.RIGHT, padx=3)

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

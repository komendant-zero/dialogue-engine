"""
Dialogue Engine - Model Context Protocol (MCP) Control Center Plugin v2.0
════════════════════════════════════════════════════════════════════════════
Полноценная панель управления интеграцией с ИИ через протокол MCP:
- Мониторинг и статус живого сокет-моста (127.0.0.1:48123)
- Живой журнал событий от нейросети в реальном времени
- Генератор готовых конфигураций (Antigravity, Claude Desktop, Cursor, VS Code)
- Интерактивный тест связи (Ping / отправка тестового импульса на холст)
- Полный справочник всех 18 доступных MCP-инструментов движка
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from plugin_system.base import Plugin

DEFAULT_LIVE_PORT = 48123


class MCPPlugin(Plugin):
    name = "Model Context Protocol (MCP) Control Center"
    version = "2.0"
    author = "Dialogue Engine Team"
    description = "Интерактивный центр управления и мониторинга AI-ассистентов по протоколу MCP"

    def __init__(self, editor: Any):
        super().__init__(editor)
        self.status_btn = None
        self.dialog_instance: Optional[MCPControlCenterDialog] = None

    def on_event(self, event_type: str, data: Any = None) -> None:
        if event_type == "setup_ui":
            self.setup_ui_elements(data)

    def setup_ui_elements(self, toolbar: Any) -> None:
        # 1. Бейдж-кнопка в правом тулбаре
        parent = getattr(self.editor, "toolbar_right", toolbar)
        if parent:
            self.status_btn = tk.Button(
                parent,
                text="🤖 MCP: 48123",
                bg="#1a365d",
                activebackground="#2b6cb0",
                fg="#63b3ed",
                activeforeground="#ffffff",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                padx=8,
                pady=2,
                cursor="hand2",
                command=self.open_control_center
            )
            self.status_btn.pack(side=tk.RIGHT, padx=4)

        # 2. Пункты в меню разработчика / проекта
        dev_menu = getattr(self.editor, "dev_menu", None)
        if dev_menu:
            dev_menu.add_separator()
            dev_menu.add_command(
                label="🤖 Центр управления MCP (AI Dashboard)...",
                command=self.open_control_center
            )
            dev_menu.add_command(
                label="⚡ Тест связи с AI (Ping / Impulse)",
                command=self.send_test_ping
            )
            dev_menu.add_command(
                label="📋 Скопировать конфигурацию MCP...",
                command=self.copy_quick_config
            )

        # 3. Горячая клавиша F8 для открытия панели
        try:
            self.editor.bind("<F8>", lambda e: self.open_control_center())
        except Exception:
            pass

    def open_control_center(self) -> None:
        if self.dialog_instance and self.dialog_instance.winfo_exists():
            self.dialog_instance.lift()
            self.dialog_instance.focus_force()
            return

        self.dialog_instance = MCPControlCenterDialog(self.editor, self)

    def is_socket_alive(self) -> bool:
        """Проверяет реальную доступность сокета 127.0.0.1:48123."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.15)
                res = s.connect_ex(("127.0.0.1", DEFAULT_LIVE_PORT))
                return res == 0
        except Exception:
            return False

    def send_test_ping(self) -> bool:
        """Отправляет тестовый проверочный импульс на сокет-сервер."""
        test_payload = {
            "action": "node_update",
            "node_id": None,
            "is_test": True
        }
        # Если есть выбранный узел, подсветим его
        selected = getattr(self.editor, "selected_nodes", [])
        if selected:
            test_payload["node_id"] = selected[0].id
        else:
            # Иначе берем первую попавшуюся ноду
            nodes = getattr(self.editor, "nodes", [])
            if nodes:
                test_payload["node_id"] = nodes[0].id

        if not test_payload["node_id"]:
            messagebox.showwarning("MCP Тест", "На холсте нет узлов для проверки импульса!", parent=self.editor)
            return False

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect(("127.0.0.1", DEFAULT_LIVE_PORT))
                s.sendall(json.dumps(test_payload).encode("utf-8") + b"\n")
                resp = s.recv(1024)
            if hasattr(self.editor, "status_bar"):
                self.editor.status_bar.config(text="⚡ MCP Тест: Импульс успешно отправлен на холст!")
            return True
        except Exception as e:
            messagebox.showerror("MCP Ошибка связи", f"Не удалось подключиться к порту {DEFAULT_LIVE_PORT}:\n{e}", parent=self.editor)
            return False

    def copy_quick_config(self) -> None:
        cfg = get_mcp_config(self.editor, "claude")
        self.editor.clipboard_clear()
        self.editor.clipboard_append(cfg)
        messagebox.showinfo("MCP Конфигурация", "Конфигурация для Claude Desktop / Antigravity успешно скопирована в буфер обмена!", parent=self.editor)


def get_mcp_config(editor: Any, target_format: str = "claude") -> str:
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mcp_script = os.path.join(script_dir, "mcp_server.py").replace("\\", "/")
    python_exe = sys.executable.replace("\\", "/")
    current_proj = getattr(editor, "current_file", "") or os.path.join(script_dir, "violant.json")
    current_proj = os.path.abspath(current_proj).replace("\\", "/")

    if target_format == "claude" or target_format == "antigravity":
        config_obj = {
            "mcpServers": {
                "dialogue-engine": {
                    "command": python_exe,
                    "args": [mcp_script, current_proj],
                    "env": {
                        "PYTHONIOENCODING": "utf-8"
                    }
                }
            }
        }
    elif target_format == "cursor":
        config_obj = {
            "name": "dialogue-engine",
            "command": f'"{python_exe}" "{mcp_script}" "{current_proj}"'
        }
    else:
        config_obj = {
            "dialogue-engine": {
                "command": python_exe,
                "args": [mcp_script, current_proj]
            }
        }

    return json.dumps(config_obj, ensure_ascii=False, indent=2)


class MCPControlCenterDialog(tk.Toplevel):
    """Интерактивное окно центра управления MCP."""

    def __init__(self, parent: Any, plugin: MCPPlugin):
        super().__init__(parent)
        self.editor = parent
        self.plugin = plugin

        self.title("Dialogue Engine — Model Context Protocol (MCP) Control Center")
        self.geometry("780x560")
        self.minsize(680, 480)
        self.configure(bg="#1e1e1e")
        self.transient(parent)

        self.setup_ui()
        self.refresh_status()

        # Привязываем коллбэк живого лога из AILiveSyncPlugin
        ai_sync = self.editor.plugin_manager.get_plugin("Real-Time AI Live Sync") if hasattr(self.editor, "plugin_manager") else None
        if ai_sync:
            ai_sync.on_log_callback = self.on_new_live_event
            self.load_history_from_sync(ai_sync)

    def setup_ui(self) -> None:
        # Верхняя плашка заголовка
        header = tk.Frame(self, bg="#252526", height=60, padx=16, pady=10)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        lbl_icon = tk.Label(header, text="🤖", font=("Segoe UI", 20), bg="#252526", fg="#0078d4")
        lbl_icon.pack(side=tk.LEFT, padx=(0, 12))

        title_frame = tk.Frame(header, bg="#252526")
        title_frame.pack(side=tk.LEFT, fill=tk.Y)

        lbl_title = tk.Label(title_frame, text="Model Context Protocol (MCP) Control Center", font=("Segoe UI", 12, "bold"), bg="#252526", fg="#ffffff")
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(title_frame, text="Прямой двусторонний мост между нейросетью и холстом диалогового редактора", font=("Segoe UI", 8), bg="#252526", fg="#9d9d9d")
        lbl_sub.pack(anchor="w")

        # Вкладки Notebook
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("MCP.TNotebook", background="#1e1e1e", borderwidth=0)
        style.configure("MCP.TNotebook.Tab", background="#2d2d2d", foreground="#cccccc", padding=[14, 6], font=("Segoe UI", 9, "bold"))
        style.map("MCP.TNotebook.Tab", background=[("selected", "#0078d4")], foreground=[("selected", "#ffffff")])

        self.notebook = ttk.Notebook(self, style="MCP.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # ─── Вкладка 1: Статус и Мост ─────────────────────────────────────────
        self.tab_status = tk.Frame(self.notebook, bg="#1e1e1e", padx=14, pady=14)
        self.notebook.add(self.tab_status, text="⚡ Статус и Мост")
        self.setup_tab_status()

        # ─── Вкладка 2: Живой журнал событий ──────────────────────────────────
        self.tab_logs = tk.Frame(self.notebook, bg="#1e1e1e", padx=14, pady=14)
        self.notebook.add(self.tab_logs, text="📜 Живой Журнал ИИ")
        self.setup_tab_logs()

        # ─── Вкладка 3: Конфигурации для клиентов ─────────────────────────────
        self.tab_configs = tk.Frame(self.notebook, bg="#1e1e1e", padx=14, pady=14)
        self.notebook.add(self.tab_configs, text="📋 Конфигурация Клиентов")
        self.setup_tab_configs()

        # ─── Вкладка 4: Справочник инструментов MCP ───────────────────────────
        self.tab_tools = tk.Frame(self.notebook, bg="#1e1e1e", padx=14, pady=14)
        self.notebook.add(self.tab_tools, text="🛠 Справочник Инструментов")
        self.setup_tab_tools()

    def setup_tab_status(self) -> None:
        # Карточка статуса
        card = tk.LabelFrame(self.tab_status, text=" Состояние Сокет-Моста ", bg="#252526", fg="#60cdff", font=("Segoe UI", 9, "bold"), padx=12, pady=12)
        card.pack(fill=tk.X, pady=(0, 12))

        status_row = tk.Frame(card, bg="#252526")
        status_row.pack(fill=tk.X, pady=4)

        tk.Label(status_row, text="Статус локального порта 48123:", bg="#252526", fg="#aaaaaa", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.lbl_socket_status = tk.Label(status_row, text="● Проверка...", bg="#252526", fg="#e67e22", font=("Segoe UI", 9, "bold"))
        self.lbl_socket_status.pack(side=tk.LEFT, padx=10)

        # Кнопки быстрых действий
        actions_row = tk.Frame(card, bg="#252526")
        actions_row.pack(fill=tk.X, pady=(10, 4))

        tk.Button(
            actions_row,
            text="⚡ Отправить тестовый импульс (Ping)",
            command=self.plugin.send_test_ping,
            bg="#27ae60",
            activebackground="#2ecc71",
            fg="white",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            actions_row,
            text="🔄 Перезапустить сокет-сервер",
            command=self.restart_bridge,
            bg="#34495e",
            activebackground="#4a6572",
            fg="white",
            relief="flat",
            font=("Segoe UI", 9),
            padx=10,
            pady=4,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            actions_row,
            text="🔍 Обновить статус",
            command=self.refresh_status,
            bg="#2d2d2d",
            activebackground="#3d3d3d",
            fg="#cccccc",
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            cursor="hand2"
        ).pack(side=tk.LEFT)

        # Информационная карточка путей
        info_card = tk.LabelFrame(self.tab_status, text=" Параметры Сервера и Окружения ", bg="#252526", fg="#60cdff", font=("Segoe UI", 9, "bold"), padx=12, pady=12)
        info_card.pack(fill=tk.BOTH, expand=True)

        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mcp_script = os.path.join(script_dir, "mcp_server.py")
        curr_file = getattr(self.editor, "current_file", "") or os.path.join(script_dir, "violant.json")

        self.add_info_row(info_card, "Файл MCP Сервера:", mcp_script)
        self.add_info_row(info_card, "Активный файл проекта:", curr_file)
        self.add_info_row(info_card, "Интерпретатор Python:", sys.executable)
        self.add_info_row(info_card, "Режим синхронизации:", "Реальное время (TCP socket 127.0.0.1:48123)")

    def add_info_row(self, parent: tk.Widget, label_text: str, value_text: str) -> None:
        f = tk.Frame(parent, bg="#252526")
        f.pack(fill=tk.X, pady=4)
        tk.Label(f, text=label_text, width=22, anchor="w", bg="#252526", fg="#888888", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        e = tk.Entry(f, bg="#1e1e1e", fg="#e0e0e0", relief="flat", font=("Consolas", 8), insertbackground="white")
        e.insert(0, value_text)
        e.config(state="readonly")
        e.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def refresh_status(self) -> None:
        alive = self.plugin.is_socket_alive()
        if alive:
            self.lbl_socket_status.config(text="● АКТИВЕН (127.0.0.1:48123)", fg="#2ecc71")
            if self.plugin.status_btn:
                self.plugin.status_btn.config(text="🟢 MCP: 48123", bg="#1b4d3e", fg="#58d68d")
        else:
            self.lbl_socket_status.config(text="○ НЕ ДОСТУПЕН (Порт закрыт)", fg="#e74c3c")
            if self.plugin.status_btn:
                self.plugin.status_btn.config(text="🔴 MCP: Offline", bg="#4a154b", fg="#e74c3c")

    def restart_bridge(self) -> None:
        ai_sync = self.editor.plugin_manager.get_plugin("Real-Time AI Live Sync") if hasattr(self.editor, "plugin_manager") else None
        if ai_sync and hasattr(ai_sync, "restart_server"):
            ai_sync.restart_server()
            time.sleep(0.1)
            self.refresh_status()
            messagebox.showinfo("Перезапуск", "Сокет-сервер Live-Sync перезапущен!", parent=self)
        else:
            messagebox.showwarning("Ошибка", "Модуль Real-Time AI Live Sync не найден среди плагинов.", parent=self)

    # ─── Журнал ИИ ─────────────────────────────────────────────────────────────
    def setup_tab_logs(self) -> None:
        top_bar = tk.Frame(self.tab_logs, bg="#1e1e1e")
        top_bar.pack(fill=tk.X, pady=(0, 8))

        tk.Label(top_bar, text="Журнал вызовов нейросети (создание, обновление, связи):", bg="#1e1e1e", fg="#aaaaaa", font=("Segoe UI", 8)).pack(side=tk.LEFT)

        tk.Button(
            top_bar,
            text="🗑 Очистить лог",
            command=self.clear_logs,
            bg="#2d2d2d",
            fg="#cccccc",
            relief="flat",
            font=("Segoe UI", 8),
            padx=8,
            pady=2,
            cursor="hand2"
        ).pack(side=tk.RIGHT)

        log_frame = tk.Frame(self.tab_logs, bg="#1e1e1e")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_log = tk.Text(log_frame, bg="#141414", fg="#58d68d", font=("Consolas", 9), relief="flat", wrap="word", padx=8, pady=8)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = tk.Scrollbar(log_frame, command=self.txt_log.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.config(yscrollcommand=scroll.set)

    def load_history_from_sync(self, ai_sync: Any) -> None:
        history = getattr(ai_sync, "event_log", [])
        for entry in history:
            self.txt_log.insert(tk.END, entry.get("text", "") + "\n")
        self.txt_log.see(tk.END)

    def on_new_live_event(self, entry: Dict[str, Any]) -> None:
        try:
            if self.txt_log and self.txt_log.winfo_exists():
                self.txt_log.insert(tk.END, entry.get("text", "") + "\n")
                self.txt_log.see(tk.END)
        except Exception:
            pass

    def clear_logs(self) -> None:
        self.txt_log.delete("1.0", tk.END)
        ai_sync = self.editor.plugin_manager.get_plugin("Real-Time AI Live Sync") if hasattr(self.editor, "plugin_manager") else None
        if ai_sync and hasattr(ai_sync, "event_log"):
            ai_sync.event_log.clear()

    # ─── Конфигурации для клиентов ─────────────────────────────────────────────
    def setup_tab_configs(self) -> None:
        tk.Label(
            self.tab_configs,
            text="Готовая конфигурация для подключения AI-ассистентов к этому проекту:",
            bg="#1e1e1e",
            fg="#cccccc",
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(0, 8))

        selector_frame = tk.Frame(self.tab_configs, bg="#1e1e1e")
        selector_frame.pack(fill=tk.X, pady=(0, 8))

        self.client_var = tk.StringVar(value="claude")

        rb_style = {"bg": "#1e1e1e", "fg": "white", "selectcolor": "#252526", "activebackground": "#1e1e1e", "activeforeground": "#ffffff", "font": ("Segoe UI", 9)}
        tk.Radiobutton(selector_frame, text="Claude Desktop / Antigravity", variable=self.client_var, value="claude", command=self.update_config_text, **rb_style).pack(side=tk.LEFT, padx=(0, 15))
        tk.Radiobutton(selector_frame, text="Cursor MCP", variable=self.client_var, value="cursor", command=self.update_config_text, **rb_style).pack(side=tk.LEFT, padx=(0, 15))
        tk.Radiobutton(selector_frame, text="Roo Code / Cline", variable=self.client_var, value="roo", command=self.update_config_text, **rb_style).pack(side=tk.LEFT)

        cfg_frame = tk.Frame(self.tab_configs, bg="#1e1e1e")
        cfg_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_config = tk.Text(cfg_frame, bg="#141414", fg="#60cdff", font=("Consolas", 9), relief="flat", padx=10, pady=10)
        self.txt_config.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(self.tab_configs, bg="#1e1e1e", pady=8)
        btn_row.pack(fill=tk.X)

        self.btn_copy = tk.Button(
            btn_row,
            text="📋 Скопировать конфигурацию в буфер обмена",
            command=self.copy_config,
            bg="#0078d4",
            activebackground="#1084d9",
            fg="white",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=5,
            cursor="hand2"
        )
        self.btn_copy.pack(side=tk.LEFT)

        self.update_config_text()

    def update_config_text(self) -> None:
        cfg = get_mcp_config(self.editor, self.client_var.get())
        self.txt_config.delete("1.0", tk.END)
        self.txt_config.insert("1.0", cfg)

    def copy_config(self) -> None:
        cfg = self.txt_config.get("1.0", tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(cfg)
        self.btn_copy.config(text="✅ Скопировано!", bg="#27ae60")
        self.after(2000, lambda: self.btn_copy.config(text="📋 Скопировать конфигурацию в буфер обмена", bg="#0078d4"))

    # ─── Справочник Инструментов ───────────────────────────────────────────────
    def setup_tab_tools(self) -> None:
        tk.Label(
            self.tab_tools,
            text="18 доступных инструментов Model Context Protocol в mcp_server.py:",
            bg="#1e1e1e",
            fg="#cccccc",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(0, 6))

        tools_list = [
            ("de_load_project", "Загрузить / перезагрузить JSON файл сценария"),
            ("de_save_project", "Сохранить граф на диск с созданием .bak бэкапа"),
            ("de_reload_server", "Перезапустить сервер и обновить кэш графа"),
            ("de_get_stats", "Сводная статистика: узлы, связи, персонажи, тупики"),
            ("de_get_characters", "Список персонажей, цвета реплик и статистика диалогов"),
            ("de_find_leaf_endpoints", "Поиск тупиковых реплик (где обрывается сюжет)"),
            ("de_get_node", "Детальная информация по конкретному узлу графа"),
            ("de_search_nodes", "Поиск узлов по тексту, персонажу или типу"),
            ("de_trace_branch", "Трассировка сюжетной ветки от узла вперед"),
            ("de_add_story_node", "Добавить реплику персонажа или нарратив (#Сцена)"),
            ("de_add_choice_node", "Создать узел ветвящегося выбора игрока"),
            ("de_add_condition_node", "Создать логическое условие (True / False ветки)"),
            ("de_add_music_node", "Добавить узел музыки, звукового эффекта или голоса"),
            ("de_bulk_add_nodes", "Массовое создание цепочки узлов за один вызов"),
            ("de_update_node", "Изменить текст, персонажа, координаты или данные ноды"),
            ("de_move_node", "Переместить узел на холсте (абсолютно или со смещением)"),
            ("de_duplicate_node", "Создать независимую копию существующего узла"),
            ("de_delete_node", "Удалить узел и все привязанные к нему связи"),
            ("de_connect_nodes", "Соединить выход одного узла со входом другого"),
            ("de_disconnect_nodes", "Разорвать связь между двумя узлами"),
            ("de_validate_graph", "Комплексная диагностика графа сценария на ошибки"),
            ("de_export_renpy", "Экспортировать весь сценарий в код Ren'Py (.rpy)")
        ]

        frame_scroll = tk.Frame(self.tab_tools, bg="#1e1e1e")
        frame_scroll.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(frame_scroll, bg="#1e1e1e", highlightthickness=0)
        scrollbar = tk.Scrollbar(frame_scroll, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#1e1e1e")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for name, desc in tools_list:
            row = tk.Frame(scrollable_frame, bg="#252526", padx=8, pady=5)
            row.pack(fill=tk.X, pady=2, padx=4)
            tk.Label(row, text=name, bg="#252526", fg="#f39c12", font=("Consolas", 9, "bold"), width=24, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=desc, bg="#252526", fg="#cccccc", font=("Segoe UI", 9), anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

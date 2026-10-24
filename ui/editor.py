"""
Dialogue Engine - Main Editor Window Controller.
"""

from __future__ import annotations
import math
import os
import re
import sys
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
from typing import Any, Callable

# Таблица сопоставления латинских букв клавиш с кириллическими keysyms Tkinter
CYRILLIC_KEY_MAP: dict[str, tuple[str, str]] = {
    "a": ("Cyrillic_ef", "Cyrillic_EF"),              # Ф
    "b": ("Cyrillic_i", "Cyrillic_I"),                # И
    "c": ("Cyrillic_es", "Cyrillic_ES"),              # С
    "d": ("Cyrillic_ve", "Cyrillic_VE"),              # В
    "e": ("Cyrillic_u", "Cyrillic_U"),                # У
    "f": ("Cyrillic_a", "Cyrillic_A"),                # А
    "g": ("Cyrillic_pe", "Cyrillic_PE"),              # П
    "h": ("Cyrillic_er", "Cyrillic_ER"),              # Р
    "i": ("Cyrillic_sha", "Cyrillic_SHA"),            # Ш
    "j": ("Cyrillic_o", "Cyrillic_O"),                # О
    "k": ("Cyrillic_el", "Cyrillic_EL"),              # Л
    "l": ("Cyrillic_de", "Cyrillic_DE"),              # Д
    "m": ("Cyrillic_softsign", "Cyrillic_SOFTSIGN"),  # Ь
    "n": ("Cyrillic_te", "Cyrillic_TE"),              # Т
    "o": ("Cyrillic_shcha", "Cyrillic_SHCHA"),        # Щ
    "p": ("Cyrillic_ze", "Cyrillic_ZE"),              # З
    "q": ("Cyrillic_shorti", "Cyrillic_SHORTI"),      # Й
    "r": ("Cyrillic_ka", "Cyrillic_KA"),              # К
    "s": ("Cyrillic_yeru", "Cyrillic_YERU"),          # Ы
    "t": ("Cyrillic_ie", "Cyrillic_IE"),              # Е
    "u": ("Cyrillic_ghe", "Cyrillic_GHE"),            # Г
    "v": ("Cyrillic_em", "Cyrillic_EM"),              # М
    "w": ("Cyrillic_tse", "Cyrillic_TSE"),            # Ц
    "x": ("Cyrillic_che", "Cyrillic_CHE"),            # Ч
    "y": ("Cyrillic_en", "Cyrillic_EN"),              # Н
    "z": ("Cyrillic_ya", "Cyrillic_YA"),              # Я
}

from core.autosave import AutosaveManager
from core.characters import CharacterManager
from core.history import HistoryManager
from core.hotkeys import HotkeyManager
from core.models import ConnectionData, NodeData, ProjectData
from core.serialization import ProjectSerializer, SerializationError
from plugin_system.manager import PluginManager
from ui.canvas import EditorCanvas
from ui.dialogs.character_manager import CharacterManagerDialog
from ui.dialogs.hotkey_settings import HotkeySettingsDialog
from ui.dialogs.node_editor import NodeEditorDialog
from ui.dialogs.search_replace import SearchReplaceDialog
from ui.node_view import Node
from ui.theme import (
    BTN_ACTION_STYLE,
    BTN_NORMAL_STYLE,
    COLORS,
    MENU_CFG_STYLE,
    NODE_COLOR_PRESETS,
    darken_color,
)


class ScenarioEditor(tk.Tk):
    """Главное окно визуального редактора сценариев Dialogue Engine."""

    def __init__(self, initial_file: str | None = None):
        super().__init__()
        self.current_file: str | None = None
        self.title("Scenario Editor - Новый проект")
        self.geometry("1100x750")
        self.configure(bg=COLORS["bg"])

        # Core Components
        self.nodes: list[Node] = []
        self.connections: list[dict[str, Any]] = []
        self.history_manager = HistoryManager(max_depth=50)
        self.autosave_manager = AutosaveManager()
        self.plugin_manager = PluginManager(self)
        self.hotkey_manager = HotkeyManager()
        self.character_manager = CharacterManager()

        # State Variables
        self.selected_nodes: list[Node] = []
        self.selected_connection: dict[str, Any] | None = None
        self.clipboard: dict[str, Any] = {}
        self.is_dirty = False

        # Interaction & Drag Data
        self.drag_data: dict[str, Any] = {"x": 0, "y": 0, "item": None, "moved": False}
        self.conn_drag: dict[str, Any] = {"active": False, "start_node": None, "start_idx": 0, "line_id": None}
        self.marquee_start: tuple[float, float] | None = None
        self.marquee_id: int | None = None
        self.pressed_keys: dict[str, bool] = {}
        self._hotkey_actions: dict[tuple[bool, bool, int | str], Any] = {}
        self._in_bind: bool = False
        self._last_hotkey_time: float = 0.0

        # Physics & Panning
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.friction = 0.9
        self.keyboard_accel = 0.18
        self.max_speed = 22.0
        self.scroll_remainder_x = 0.0
        self.scroll_remainder_y = 0.0
        self.mouse_last_x = 0
        self.mouse_last_y = 0
        self.is_panning = False

        # Zoom
        self.zoom_level = 1.0
        self.min_zoom = 0.4
        self.max_zoom = 2.0

        # UI Initialization
        self.setup_ui()
        self.setup_hotkeys()

        # Load Plugins
        self.plugin_manager.load_plugins_from_folder("plugins")
        self.plugin_manager.notify("setup_ui", self.toolbar)

        # Canvas positioning
        self.canvas.xview_moveto(0.5)
        self.canvas.yview_moveto(0.5)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.physics_loop()
        self.autosave_loop()

        # Initial load or crash recovery check
        if initial_file:
            self.after(100, lambda: self.load_project(initial_file))
        else:
            self.after(200, self._check_crash_recovery)

    def _check_crash_recovery(self) -> None:
        """Проверяет наличие несохраненной сессии после сбоя."""
        recovery = self.autosave_manager.check_recovery(self.current_file)
        if recovery:
            autosave_path, _ = recovery
            resp = messagebox.askyesno(
                "Восстановление проекта",
                "Обнаружена несохраненная копия после предыдущей сессии.\nХотите восстановить проект из автосохранения?",
                parent=self
            )
            if resp:
                try:
                    project = ProjectSerializer.load_from_file(autosave_path)
                    self._load_project_data(project)
                    self.set_dirty(True)
                    messagebox.showinfo("Восстановление", "Проект успешно восстановлен из автосохранения!", parent=self)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось восстановить автосохранение: {e}", parent=self)

    def autosave_loop(self) -> None:
        """Периодический таймер фонового автосохранения."""
        if self.is_dirty and (self.nodes or self.connections):
            try:
                project = self._export_to_project_data()
                self.autosave_manager.save_snapshot(project, self.current_file)
                self.plugin_manager.notify("autosave_tick", {"project": project})
            except Exception:
                pass
        self.after(self.autosave_manager.interval_seconds * 1000, self.autosave_loop)

    def on_close(self) -> None:
        if self.is_dirty:
            res = messagebox.askyesnocancel("Выход", "В проекте есть несохраненные изменения. Сохранить перед выходом?")
            if res is True:
                self.save_project()
                self.autosave_manager.clear_autosave(self.current_file)
                self.destroy()
            elif res is False:
                self.autosave_manager.clear_autosave(self.current_file)
                self.destroy()
        else:
            self.autosave_manager.clear_autosave(self.current_file)
            self.destroy()

    def set_dirty(self, state: bool = True) -> None:
        self.is_dirty = state
        fname = os.path.basename(self.current_file) if self.current_file else "Новый проект"
        title_suffix = " * (Изменено)" if state else ""
        self.title(f"Scenario Editor - {fname}{title_suffix}")

    def setup_ui(self) -> None:
        self.toolbar = tk.Frame(self, bg=COLORS["bg"], height=42)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        self.toolbar_left = tk.Frame(self.toolbar, bg=COLORS["bg"])
        self.toolbar_left.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=3)

        self.toolbar_right = tk.Frame(self.toolbar, bg=COLORS["bg"])
        self.toolbar_right.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=3)

        # Панель навигации (Breadcrumbs)
        self.nav_bar = tk.Frame(self, bg="#282828", height=26)
        self.nav_bar.pack(side=tk.TOP, fill=tk.X)
        self.lbl_path = tk.Label(self.nav_bar, text="Root", bg="#282828", fg="#4a90e2", font=("Segoe UI", 9, "bold"))
        self.lbl_path.pack(side=tk.LEFT, padx=10)

        # Левые кнопки создания нод
        tk.Button(self.toolbar_left, text="📝 Сюжет", command=lambda: self.add_node("story"), **BTN_ACTION_STYLE).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar_left, text="🔀 Выбор", command=lambda: self.add_node("choice"), **BTN_ACTION_STYLE).pack(side=tk.LEFT, padx=3)

        # Меню Компоненты
        self.plugin_menu_btn = tk.Menubutton(self.toolbar_left, text="🧩 Компоненты ▾", **BTN_ACTION_STYLE)
        self.plugin_menu_btn.pack(side=tk.LEFT, padx=3)
        self.plugin_menu = tk.Menu(self.plugin_menu_btn, **MENU_CFG_STYLE)
        self.plugin_menu_btn["menu"] = self.plugin_menu

        # Кнопка Персонажи (База героев)
        tk.Button(self.toolbar_left, text="👥 Персонажи", command=self.open_character_manager, **BTN_ACTION_STYLE).pack(side=tk.LEFT, padx=3)

        tk.Label(self.toolbar_left, text="|", bg=COLORS["bg"], fg="#555555").pack(side=tk.LEFT, padx=5)

        # Меню Проект
        self.project_menu_btn = tk.Menubutton(self.toolbar_left, text="📁 Проект ▾", **BTN_NORMAL_STYLE)
        self.project_menu_btn.pack(side=tk.LEFT, padx=3)
        self.project_menu = tk.Menu(self.project_menu_btn, **MENU_CFG_STYLE)
        self.project_menu_btn["menu"] = self.project_menu

        self.project_menu.add_command(label="💾 Сохранить (Ctrl+S)", command=self.save_project)
        self.project_menu.add_command(label="📂 Загрузить (Ctrl+O)", command=self.load_project)
        self.project_menu.add_separator()
        self.project_menu.add_command(label="👥 База персонажей... (Ctrl+Shift+C)", command=self.open_character_manager)
        self.project_menu.add_command(label="⌨️ Горячие клавиши...", command=self.open_hotkey_settings)
        self.project_menu.add_separator()
        self.project_menu.add_command(label="⚠️ Очистить холст", command=self.clear_all)

        # Поиск
        tk.Button(self.toolbar_left, text="🔍 Поиск", command=self.open_search_replace, **BTN_NORMAL_STYLE).pack(side=tk.LEFT, padx=3)

        # Правое меню инструментов
        self.dev_menu_btn = tk.Menubutton(self.toolbar_right, text="⚙️ Меню ▾", **BTN_NORMAL_STYLE)
        self.dev_menu_btn.pack(side=tk.RIGHT, padx=3)
        self.dev_menu = tk.Menu(self.dev_menu_btn, **MENU_CFG_STYLE)
        self.dev_menu_btn["menu"] = self.dev_menu
        self.dev_menu.add_command(label="⌨️ Настройки горячих клавиш...", command=self.open_hotkey_settings)

        # Кнопка настроек хоткеев на тулбаре
        tk.Button(self.toolbar_right, text="⌨️ Хоткеи", command=self.open_hotkey_settings, **BTN_NORMAL_STYLE).pack(side=tk.RIGHT, padx=3)

        # Масштабирование (Zoom)
        self.zoom_frame = tk.Frame(self.toolbar_right, bg=COLORS["bg"])
        self.zoom_frame.pack(side=tk.RIGHT, padx=4)
        tk.Button(self.zoom_frame, text="−", command=self.zoom_out, **BTN_NORMAL_STYLE, width=2).pack(side=tk.LEFT, padx=1)
        self.lbl_zoom = tk.Label(self.zoom_frame, text="100%", bg=COLORS["bg"], fg="#aaaaaa", font=("Segoe UI", 8), width=5)
        self.lbl_zoom.pack(side=tk.LEFT, padx=1)
        tk.Button(self.zoom_frame, text="+", command=self.zoom_in, **BTN_NORMAL_STYLE, width=2).pack(side=tk.LEFT, padx=1)

        # Холст
        self.canvas = EditorCanvas(self, editor=self)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Привязка событий мыши к холсту
        self.canvas.bind("<ButtonPress-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)
        self.canvas.bind("<ButtonRelease-2>", self.stop_pan)

    def bind(self, sequence: str | None = None, func: Any = None, add: str | None = None) -> Any:
        res = super().bind(sequence, func, add)
        if sequence and func and not getattr(self, "_in_bind", False):
            self._register_layout_hotkey(sequence, func, add)
        return res

    def _register_layout_hotkey(self, sequence: str, func: Any, add: str | None = None) -> None:
        if not hasattr(self, "_hotkey_actions"):
            return
        m = re.match(r"^<Control-(?:(Shift)-)?(?:Key-)?([a-zA-Z])>$", sequence, re.IGNORECASE)
        if m:
            has_shift = bool(m.group(1))
            letter = m.group(2).lower()
            vk = ord(letter.upper())
            self._hotkey_actions[(True, has_shift, vk)] = func
            self._hotkey_actions[(True, has_shift, letter)] = func
            self._hotkey_actions[(True, has_shift, letter.upper())] = func

            self._in_bind = True
            try:
                if not has_shift:
                    super().bind(f"<Control-{letter.upper()}>", func, add)
                if letter in CYRILLIC_KEY_MAP:
                    for cyr in CYRILLIC_KEY_MAP[letter]:
                        self._hotkey_actions[(True, has_shift, cyr)] = func
                        patt = f"<Control-Shift-{cyr}>" if has_shift else f"<Control-{cyr}>"
                        try:
                            super().bind(patt, func, add)
                        except Exception:
                            pass
            finally:
                self._in_bind = False
        elif sequence in ("<Delete>", "<Control-0>", "<Control-plus>", "<Control-equal>", "<Control-minus>"):
            if sequence == "<Delete>":
                self._hotkey_actions[(False, False, 46)] = func
                self._hotkey_actions[(False, False, "Delete")] = func
            elif sequence == "<Control-0>":
                self._hotkey_actions[(True, False, 48)] = func
                self._hotkey_actions[(True, False, 96)] = func
            elif sequence in ("<Control-plus>", "<Control-equal>"):
                self._hotkey_actions[(True, False, 187)] = func
                self._hotkey_actions[(True, False, 107)] = func
            elif sequence == "<Control-minus>":
                self._hotkey_actions[(True, False, 189)] = func
                self._hotkey_actions[(True, False, 109)] = func

    def setup_hotkeys(self) -> None:
        self.bind("<KeyPress>", self.on_key_press)
        self.bind("<KeyRelease>", self.on_key_release)

        # Регистрация действий в HotkeyManager
        self.hotkey_manager.register_action("add_story", lambda e=None: self.add_node_at_cursor("story"))
        self.hotkey_manager.register_action("add_choice", lambda e=None: self.add_node_at_cursor("choice"))
        self.hotkey_manager.register_action("add_condition", lambda e=None: self.add_node_at_cursor("condition"))
        self.hotkey_manager.register_action("add_music", lambda e=None: self.add_node_at_cursor("music"))
        self.hotkey_manager.register_action("add_pause", lambda e=None: self.add_node_at_cursor("pause"))
        self.hotkey_manager.register_action("save_project", lambda e=None: self.save_project())
        self.hotkey_manager.register_action("load_project", lambda e=None: self.load_project())
        self.hotkey_manager.register_action("search", lambda e=None: self.open_search_replace())
        self.hotkey_manager.register_action("characters", lambda e=None: self.open_character_manager())
        self.hotkey_manager.register_action("undo", self.undo)
        self.hotkey_manager.register_action("redo", self.redo)
        self.hotkey_manager.register_action("copy", self.copy)
        self.hotkey_manager.register_action("paste", self.paste)
        self.hotkey_manager.register_action("duplicate", self.duplicate)
        self.hotkey_manager.register_action("select_all", self.select_all)
        self.hotkey_manager.register_action("delete", self.delete_selected)
        self.hotkey_manager.register_action("auto_layout", self.trigger_auto_layout)
        self.hotkey_manager.register_action("zoom_in", lambda e=None: self.zoom_in())
        self.hotkey_manager.register_action("zoom_out", lambda e=None: self.zoom_out())
        self.hotkey_manager.register_action("zoom_reset", lambda e=None: self.zoom_reset())

        self.hotkey_manager.compile()

        # Базовые биндинги
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-y>", self.redo)
        self.bind("<Control-Shift-z>", self.redo)
        self.bind("<Control-c>", self.copy)
        self.bind("<Control-v>", self.paste)
        self.bind("<Control-d>", self.duplicate)
        self.bind("<Control-a>", self.select_all)
        self.bind("<Control-l>", lambda e: self.trigger_auto_layout())
        self.bind("<Control-L>", lambda e: self.trigger_auto_layout())
        self.bind("<Delete>", self.delete_selected)
        self.bind("<Control-s>", lambda e: self.save_project())
        self.bind("<Control-S>", lambda e: self.save_project())
        self.bind("<Control-o>", lambda e: self.load_project())
        self.bind("<Control-O>", lambda e: self.load_project())
        self.bind("<Control-f>", lambda e: self.open_search_replace())
        self.bind("<Control-F>", lambda e: self.open_search_replace())
        self.bind("<Control-Shift-c>", lambda e: self.open_character_manager())
        self.bind("<Control-Shift-C>", lambda e: self.open_character_manager())
        self.bind("<Control-plus>", lambda e: self.zoom_in())
        self.bind("<Control-equal>", lambda e: self.zoom_in())
        self.bind("<Control-minus>", lambda e: self.zoom_out())
        self.bind("<Control-0>", lambda e: self.zoom_reset())

        self._setup_cyrillic_widget_bindings()
        self.update_menu_accelerators()

    def add_node_at_cursor(self, ntype: str) -> Node:
        """Создаёт новую ноду в позиции курсора мыши на холсте (или по центру экрана)."""
        try:
            root_x = self.canvas.winfo_pointerx()
            root_y = self.canvas.winfo_pointery()
            c_root_x = self.canvas.winfo_rootx()
            c_root_y = self.canvas.winfo_rooty()
            c_w = self.canvas.winfo_width()
            c_h = self.canvas.winfo_height()

            mx = root_x - c_root_x
            my = root_y - c_root_y
            if 0 <= mx <= c_w and 0 <= my <= c_h:
                x = self.canvas.canvasx(mx) - 90
                y = self.canvas.canvasy(my) - 40
            else:
                x = self.canvas.canvasx(self.winfo_width() / 2) - 90
                y = self.canvas.canvasy(self.winfo_height() / 2) - 50
        except Exception:
            x = self.canvas.canvasx(self.winfo_width() / 2) - 90
            y = self.canvas.canvasy(self.winfo_height() / 2) - 50

        node = self.add_node(ntype, x=x, y=y)
        self.selected_nodes = [node]
        self.redraw()
        return node

    def trigger_auto_layout(self, event: Any = None) -> None:
        """Вызывает автоматическую расстановку нод через плагин Auto Layout."""
        plugin = self.plugin_manager.get_plugin("Auto Layout")
        if plugin and hasattr(plugin, "run_auto_layout"):
            plugin.run_auto_layout()

    def open_hotkey_settings(self) -> None:
        """Открывает диалог настройки горячих клавиш."""
        HotkeySettingsDialog(self, self)

    def reload_hotkeys(self) -> None:
        """Перекомпилирует хоткеи и обновляет подсказки в интерфейсе."""
        self.hotkey_manager.compile()
        self.update_menu_accelerators()

    def update_menu_accelerators(self) -> None:
        """Обновляет надписи горячих клавиш в меню."""
        save_key = self.hotkey_manager.hotkeys.get("save_project", "Ctrl+S")
        load_key = self.hotkey_manager.hotkeys.get("load_project", "Ctrl+O")
        try:
            self.project_menu.entryconfigure(0, label=f"💾 Сохранить ({save_key})")
            self.project_menu.entryconfigure(1, label=f"📂 Загрузить ({load_key})")
        except Exception:
            pass

    def _setup_cyrillic_widget_bindings(self) -> None:
        """Позволяет использовать стандартные хоткеи (Ctrl+C, Ctrl+V, Ctrl+A, Ctrl+X, Ctrl+Z, Ctrl+Y)
        в полях ввода Entry и Text даже при включенной русской раскладке клавиатуры."""
        def handle_entry_ctrl(event: Any) -> str | None:
            if not (event.state & 4):
                return None
            kc = event.keycode
            w = event.widget
            if kc == 65:  # Ctrl+A
                w.select_range(0, tk.END)
                w.icursor(tk.END)
                return "break"
            elif kc == 67:  # Ctrl+C
                w.event_generate("<<Copy>>")
                return "break"
            elif kc == 86:  # Ctrl+V
                w.event_generate("<<Paste>>")
                return "break"
            elif kc == 88:  # Ctrl+X
                w.event_generate("<<Cut>>")
                return "break"
            return None

        def handle_text_ctrl(event: Any) -> str | None:
            if not (event.state & 4):
                return None
            kc = event.keycode
            w = event.widget
            if kc == 65:  # Ctrl+A
                w.tag_add("sel", "1.0", "end")
                return "break"
            elif kc == 67:  # Ctrl+C
                w.event_generate("<<Copy>>")
                return "break"
            elif kc == 86:  # Ctrl+V
                w.event_generate("<<Paste>>")
                return "break"
            elif kc == 88:  # Ctrl+X
                w.event_generate("<<Cut>>")
                return "break"
            elif kc == 90:  # Ctrl+Z
                try:
                    w.edit_undo()
                except Exception:
                    pass
                return "break"
            elif kc == 89:  # Ctrl+Y
                try:
                    w.edit_redo()
                except Exception:
                    pass
                return "break"
            return None

        self.bind_class("Entry", "<Control-KeyPress>", handle_entry_ctrl)
        self.bind_class("Text", "<Control-KeyPress>", handle_text_ctrl)

        # Отключаем встроенный в Tkinter перехват клавиши Alt для меню Windows (tk::WinMenuKey).
        # В Tkinter на Windows нажатие Alt_L / Alt_R по умолчанию вызывает tk::WinMenuKey,
        # что отправляет WM_SYSCOMMAND (SC_KEYMENU) и переводит окно в модальный режим навигации по меню.
        # Из-за этого при переключении раскладки по Alt+Shift поле ввода теряет фокус,
        # и раскладка в поле ввода не переключается сразу, проглатывая первый символ.
        for seq in ("<Alt_L>", "<Alt_R>", "<KeyRelease-Alt_L>", "<KeyRelease-Alt_R>"):
            try:
                self.unbind_class("all", seq)
            except Exception:
                pass

        # Гарантируем, что поля ввода не блокируются при нажатии Alt
        for cls in ("Entry", "Text", "TEntry", "TCombobox"):
            self.bind_class(cls, "<Alt-KeyPress>", lambda e: None)
            self.bind_class(cls, "<Alt-KeyRelease>", lambda e: None)

    def on_key_press(self, event: Any) -> str | None:
        # Если фокус находится в поле ввода текста (Entry, Text, Combobox),
        # не перехватываем горячие клавиши редактора и холста, чтобы не ломать набор текста
        # и переключение раскладок.
        focus_w = self.focus_get()
        target_w = getattr(event, "widget", None)
        active_w = focus_w or target_w
        if active_w:
            w_cls = getattr(active_w, "winfo_class", lambda: "")()
            if isinstance(active_w, (tk.Entry, tk.Text)) or w_cls in ("Entry", "Text", "TEntry", "TCombobox"):
                return None

        self.pressed_keys[event.keysym] = True

        # 1. Проверяем динамический HotkeyManager (пользовательские хоткеи и хоткеи создания нод)
        if hasattr(self, "hotkey_manager"):
            now = time.monotonic()
            if now - self._last_hotkey_time > 0.05:
                if self.hotkey_manager.dispatch(event):
                    self._last_hotkey_time = now
                    return "break"

        # 2. Фолбэк на зарегистрированные действия _hotkey_actions (плагины и пр.)
        is_ctrl = bool(event.state & 4)
        is_shift = bool(event.state & 1)
        is_alt = bool(event.state & 8) or bool(event.state & 0x20000)

        action = None
        if is_ctrl:
            # 1. Поиск по виртуальному коду клавиши (Windows keycode)
            action = self._hotkey_actions.get((True, is_shift, event.keycode))
            if not action and not is_shift:
                action = self._hotkey_actions.get((True, False, event.keycode))
            # 2. Поиск по keysym (Tkinter keysym / Linux X11)
            if not action:
                action = self._hotkey_actions.get((True, is_shift, event.keysym))
            if not action and not is_shift:
                action = self._hotkey_actions.get((True, False, event.keysym))
        elif event.keysym == "Delete" or event.keycode == 46:
            action = self._hotkey_actions.get((False, False, 46)) or self._hotkey_actions.get((False, False, "Delete"))

        if action:
            now = time.monotonic()
            if now - self._last_hotkey_time > 0.05:
                self._last_hotkey_time = now
                try:
                    action(event)
                except TypeError:
                    action()
            return "break"
        return None

    def on_key_release(self, event: Any) -> None:
        self.pressed_keys[event.keysym] = False

    def physics_loop(self) -> None:
        target_vx = 0.0
        target_vy = 0.0

        if not self.is_panning:
            mult = 2.5 if (self.pressed_keys.get("Shift_L") or self.pressed_keys.get("Shift_R")) else 1.0
            spd = self.max_speed * mult

            if self.pressed_keys.get("Left"): target_vx = -spd
            if self.pressed_keys.get("Right"): target_vx = spd
            if self.pressed_keys.get("Up"): target_vy = -spd
            if self.pressed_keys.get("Down"): target_vy = spd

            accel = getattr(self, "keyboard_accel", 0.18)
            self.velocity_x += (target_vx - self.velocity_x) * accel
            self.velocity_y += (target_vy - self.velocity_y) * accel

        if target_vx == 0 and not self.is_panning:
            self.velocity_x *= self.friction
        if target_vy == 0 and not self.is_panning:
            self.velocity_y *= self.friction

        if abs(self.velocity_x) < 0.01: self.velocity_x = 0.0
        if abs(self.velocity_y) < 0.01: self.velocity_y = 0.0

        if self.velocity_x != 0 or self.velocity_y != 0:
            total_move_x = self.velocity_x + self.scroll_remainder_x
            total_move_y = self.velocity_y + self.scroll_remainder_y

            int_move_x = int(total_move_x)
            int_move_y = int(total_move_y)

            self.scroll_remainder_x = total_move_x - int_move_x
            self.scroll_remainder_y = total_move_y - int_move_y

            if int_move_x != 0:
                self.canvas.xview_scroll(int_move_x, "units")
            if int_move_y != 0:
                self.canvas.yview_scroll(int_move_y, "units")
            if int_move_x != 0 or int_move_y != 0:
                self.canvas.update_grid()

        self.after(16, self.physics_loop)

    def _get_current_snapshot(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": n.id, "x": n.x, "y": n.y, "title": n.title,
                    "content": n.content, "type": n.node_type, "mode": n.mode,
                    "custom_data": dict(n.custom_data)
                } for n in self.nodes
            ],
            "connections": list(self.connections)
        }

    def save_state(self, clear_redo: bool = True) -> None:
        state = self._get_current_snapshot()
        self.history_manager.push_state(state, clear_redo=clear_redo)
        self.set_dirty(True)

    def restore_state(self, state: dict[str, Any]) -> None:
        self._reset_canvas()
        for nd in state.get("nodes", []):
            node = Node(
                self, nd["x"], nd["y"], nd["title"], nd["content"],
                nd["type"], dict(nd.get("custom_data", {})), nd.get("mode", "standard"),
                node_id=nd.get("id")
            )
            node.calculate_size()
            self.nodes.append(node)

        for c in state.get("connections", []):
            self.connections.append({
                "from": c["from"],
                "out_idx": c["out_idx"],
                "to": c["to"]
            })
        self.redraw()

    def undo(self, event: Any = None) -> None:
        current_state = self._get_current_snapshot()
        prev_state = self.history_manager.undo(current_state)
        if prev_state:
            self.restore_state(prev_state)
            self.selected_nodes = []

    def redo(self, event: Any = None) -> None:
        current_state = self._get_current_snapshot()
        next_state = self.history_manager.redo(current_state)
        if next_state:
            self.restore_state(next_state)
            self.selected_nodes = []

    def copy(self, event: Any = None) -> None:
        if not self.selected_nodes:
            return
        self.clipboard = {
            "nodes": [
                {
                    "id": n.id, "x": n.x, "y": n.y, "title": n.title,
                    "content": n.content, "type": n.node_type, "mode": n.mode,
                    "custom_data": dict(n.custom_data)
                } for n in self.selected_nodes
            ],
            "connections": []
        }
        sel_ids = {n.id for n in self.selected_nodes}
        for c in self.connections:
            if c["from"] in sel_ids and c["to"] in sel_ids:
                self.clipboard["connections"].append(c)

    def paste(self, event: Any = None) -> None:
        if not self.clipboard or not self.clipboard.get("nodes"):
            return
        self.save_state()
        offset_x, offset_y = 50, 50
        id_map = {}
        new_selection = []

        for nd in self.clipboard["nodes"]:
            node = Node(
                self, nd["x"] + offset_x, nd["y"] + offset_y, nd["title"],
                nd["content"], nd["type"], dict(nd.get("custom_data", {})), nd.get("mode", "standard")
            )
            self.nodes.append(node)
            id_map[nd["id"]] = node.id
            new_selection.append(node)

        for c in self.clipboard["connections"]:
            self.connections.append({
                "from": id_map[c["from"]],
                "out_idx": c["out_idx"],
                "to": id_map[c["to"]]
            })
        self.selected_nodes = new_selection
        self.redraw()

    def duplicate(self, event: Any = None) -> None:
        self.copy()
        self.paste()

    def select_all(self, event: Any = None) -> None:
        self.selected_nodes = list(self.nodes)
        self.redraw()

    def delete_selected(self, event: Any = None) -> None:
        if not self.selected_nodes and not self.selected_connection:
            return
        self.save_state()
        if self.selected_connection:
            if self.selected_connection in self.connections:
                self.connections.remove(self.selected_connection)
            self.selected_connection = None

        if self.selected_nodes:
            sel_ids = {n.id for n in self.selected_nodes}
            self.nodes = [n for n in self.nodes if n not in self.selected_nodes]
            self.connections = [c for c in self.connections if c["from"] not in sel_ids and c["to"] not in sel_ids]
            self.selected_nodes = []
        self.redraw()

    def add_node(
        self,
        ntype: str,
        x: float | None = None,
        y: float | None = None,
        title: str | None = None,
        content: str | None = None,
        custom_data: dict[str, Any] | None = None,
        mode: str = "standard",
        save_history: bool = True,
        node_id: str | None = None
    ) -> Node:
        if save_history:
            self.save_state()

        if x is None:
            x = self.canvas.canvasx(self.winfo_width() / 2) - 90
            y = self.canvas.canvasy(self.winfo_height() / 2) - 50


        if title is None:
            if ntype == "story":
                last_story = next(
                    (n for n in reversed(self.nodes) if n.node_type == "story" and n.title and not n.title.startswith("#") and n.title != "Сцена"),
                    None
                )
                title = last_story.title if last_story else "Персонаж"
            elif ntype == "choice":
                title = "Выбор"
            elif ntype == "music":
                title = "Музыка"
            elif ntype == "condition":
                title = "Условие"
            else:
                title = ntype.capitalize()

        if content is None:
            content = "Текст..." if ntype == "story" else ("Вар 1\nВар 2" if ntype == "choice" else "Нет файла")

        node = Node(self, x, y, title, content, ntype, custom_data, mode, node_id=node_id)
        node.width = max(80, int(180 * self.zoom_level))
        font_size = max(6, int(9 * self.zoom_level))
        if node.font_content:
            node.font_content.configure(size=font_size)
        node.calculate_size()
        node.is_new = save_history
        self.nodes.append(node)
        self.redraw()
        self.plugin_manager.notify("node_added", node)
        self.set_dirty(True)
        return node

    def redraw(self) -> None:
        self.canvas.redraw_all()

    def focus_on_node(self, node: Node) -> None:
        self.canvas.center_on_node(node)

    def on_click(self, event: Any) -> None:
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.drag_data["moved"] = False

        items = self.canvas.find_overlapping(x - 5, y - 5, x + 5, y + 5)
        for item in items:
            tags = self.canvas.gettags(item)
            if "output" in tags:
                tag_info = tags[2].split("_")
                self.conn_drag.update({
                    "active": True,
                    "start_node": self.find_node_by_id(tag_info[2]),
                    "start_idx": int(tag_info[3])
                })
                self.conn_drag["line_id"] = self.canvas.create_line(x, y, x, y, fill=COLORS["line_active"], width=2, dash=(2, 2))
                return

        for item in items:
            tags = self.canvas.gettags(item)
            if "conn" in tags and len(tags) > 1 and tags[1].startswith("conn_"):
                parts = tags[1].split("_")
                from_id = parts[1]
                out_idx = int(parts[2])
                to_id = parts[3]
                for conn in self.connections:
                    if conn["from"] == from_id and conn["out_idx"] == out_idx and conn["to"] == to_id:
                        self.selected_connection = conn
                        self.selected_nodes = []
                        self.redraw()
                        return

        for node in reversed(self.nodes):
            if node.is_inside(x, y):
                self.selected_connection = None
                if event.state & 0x0001:  # Shift held
                    if node in self.selected_nodes:
                        self.selected_nodes.remove(node)
                    else:
                        self.selected_nodes.append(node)
                else:
                    if node not in self.selected_nodes:
                        self.selected_nodes = [node]

                self.drag_data.update({"item": node, "x": x, "y": y})
                sel_ids = {n.id for n in self.selected_nodes}
                node_map = {n.id: n for n in self.nodes}
                conn_pairs = [
                    (c, node_map.get(c["from"]), node_map.get(c["to"]))
                    for c in self.connections
                    if (c["from"] in sel_ids or c["to"] in sel_ids)
                    and node_map.get(c["from"]) and node_map.get(c["to"])
                ]
                self.drag_data["conn_pairs"] = conn_pairs
                self.save_state()
                self.redraw()
                return

        if not (event.state & 0x0001):
            self.selected_nodes = []
            self.selected_connection = None

        self.marquee_start = (x, y)
        self.marquee_id = self.canvas.create_rectangle(x, y, x, y, outline=COLORS["marquee"], dash=(2, 2), tags="marquee")
        self.redraw()

    def on_drag(self, event: Any) -> None:
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if self.conn_drag["active"]:
            start = self.conn_drag["start_node"].get_output_pos(self.conn_drag["start_idx"])
            self.canvas.coords(self.conn_drag["line_id"], start[0], start[1], x, y)
        elif self.marquee_start:
            self.canvas.coords(self.marquee_id, self.marquee_start[0], self.marquee_start[1], x, y)
        elif self.drag_data.get("item"):
            dx = x - self.drag_data["x"]
            dy = y - self.drag_data["y"]
            if dx == 0 and dy == 0:
                return

            if not self.drag_data.get("moved", False):
                self.drag_data["moved"] = True
                for node in self.selected_nodes:
                    self.canvas.tag_raise(node.id)

            for node in self.selected_nodes:
                node.x += dx
                node.y += dy
                for out in getattr(node, "outputs", []):
                    out["x"] += dx
                    out["y"] += dy
                self.canvas.move(node.id, dx, dy)

            conn_pairs = self.drag_data.get("conn_pairs")
            if conn_pairs is None:
                sel_ids = {n.id for n in self.selected_nodes}
                node_map = {n.id: n for n in self.nodes}
                conn_pairs = [
                    (c, node_map.get(c["from"]), node_map.get(c["to"]))
                    for c in self.connections
                    if (c["from"] in sel_ids or c["to"] in sel_ids)
                    and node_map.get(c["from"]) and node_map.get(c["to"])
                ]
                self.drag_data["conn_pairs"] = conn_pairs

            for c, fn, tn in conn_pairs:
                self.canvas.update_connection(c, from_node=fn, to_node=tn)

            self.drag_data.update({"x": x, "y": y})

    def on_release(self, event: Any) -> None:
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if self.conn_drag["active"]:
            self.save_state()
            self.canvas.delete(self.conn_drag["line_id"])
            target = None
            items = self.canvas.find_overlapping(x - 10, y - 10, x + 10, y + 10)
            for item in items:
                tags = self.canvas.gettags(item)
                if "input" in tags:
                    target = self.find_node_by_id(tags[2].split("_")[2])
                    break
            if not target:
                for node in self.nodes:
                    if node.is_inside(x, y) and node != self.conn_drag["start_node"]:
                        target = node
                        break

            if target:
                # Удаляем существующую связь с этого же выхода
                self.connections = [
                    c for c in self.connections
                    if not (c["from"] == self.conn_drag["start_node"].id and c["out_idx"] == self.conn_drag["start_idx"])
                ]
                self.connections.append({
                    "from": self.conn_drag["start_node"].id,
                    "out_idx": self.conn_drag["start_idx"],
                    "to": target.id
                })
                self.redraw()
            else:
                self.history_manager.pop_last_undo()
            self.conn_drag["active"] = False

        elif self.marquee_start:
            x1, y1 = self.marquee_start
            x2, y2 = x, y
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            for node in self.nodes:
                if (x1 <= node.x <= x2 or x1 <= node.x + node.width <= x2) and \
                   (y1 <= node.y <= y2 or y1 <= node.y + node.height <= y2):
                    if node not in self.selected_nodes:
                        self.selected_nodes.append(node)
            self.canvas.delete(self.marquee_id)
            self.marquee_start = None
            self.marquee_id = None
            self.redraw()

        elif self.drag_data.get("item"):
            if not self.drag_data.get("moved", False):
                self.history_manager.pop_last_undo()
            else:
                self.set_dirty(True)

        self.drag_data["item"] = None
        self.drag_data["conn_pairs"] = None

    def on_double_click(self, event: Any) -> None:
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for node in reversed(self.nodes):
            if node.is_inside(x, y):
                self.edit_node(node)
                return

    def on_right_click(self, event: Any) -> None:
        menu = tk.Menu(self, tearoff=0, bg=COLORS["bg"], fg="white")
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        port_hit = False
        port_action = None
        port_node = None
        port_index = 0

        def dist(x1: float, y1: float, x2: float, y2: float) -> float:
            return math.hypot(x2 - x1, y2 - y1)

        for node in self.nodes:
            ix, iy = node.get_input_pos()
            if dist(x, y, ix, iy) <= 10:
                port_hit = True
                port_node = node
                port_action = "input"
                break

            for out in node.outputs:
                if dist(x, y, out["x"], out["y"]) <= 10:
                    port_hit = True
                    port_node = node
                    port_action = "output"
                    port_index = out["id"]
                    break
            if port_hit:
                break

        if port_hit and port_node:
            if port_action == "input":
                menu.add_command(label="Удалить входящие связи", command=lambda: self.disconnect_input(port_node))
            elif port_action == "output":
                menu.add_command(label="Удалить эту связь", command=lambda: self.disconnect_output(port_node, port_index))
            menu.tk_popup(event.x_root, event.y_root)
            return

        target = next((n for n in reversed(self.nodes) if n.is_inside(x, y)), None)
        if target:
            menu.add_command(label="Редактировать", command=lambda: self.edit_node(target))
            menu.add_separator()

            color_menu = tk.Menu(menu, tearoff=0, bg="#252526", fg="white", activebackground="#094771")
            selected_targets = self.selected_nodes if (target in self.selected_nodes and len(self.selected_nodes) > 1) else [target]

            for name, bg_col, head_col in NODE_COLOR_PRESETS:
                color_menu.add_command(
                    label=name,
                    command=lambda b=bg_col, h=head_col, tgts=selected_targets: self.set_nodes_color(tgts, b, h)
                )
            color_menu.add_separator()
            color_menu.add_command(
                label="🎨 Выбрать свой цвет...",
                command=lambda tgts=selected_targets: self.pick_custom_color_for_nodes(tgts)
            )
            color_menu.add_command(
                label="🔄 Сбросить к стандартному",
                command=lambda tgts=selected_targets: self.reset_nodes_color(tgts)
            )
            menu.add_cascade(label="🎨 Цвет блока", menu=color_menu)
            menu.add_separator()

            menu.add_command(label="Удалить все входящие", command=lambda: self.disconnect_input(target))
            menu.add_command(label="Удалить все исходящие", command=lambda: self.disconnect_output(target, -1))
            menu.add_separator()
            if len(self.selected_nodes) > 1 and target in self.selected_nodes:
                menu.add_command(label="Удалить выделенные блоки", command=self.delete_selected)
            else:
                menu.add_command(label="Удалить блок", command=lambda: self.delete_node(target))

        self.plugin_manager.notify("context_menu", {"target": target, "x": x, "y": y, "menu": menu})
        menu.tk_popup(event.x_root, event.y_root)

    def disconnect_input(self, node: Node) -> None:
        if any(c["to"] == node.id for c in self.connections):
            self.save_state()
            self.connections = [c for c in self.connections if c["to"] != node.id]
            self.redraw()

    def disconnect_output(self, node: Node, out_idx: int) -> None:
        needs_update = False
        if out_idx == -1:
            needs_update = any(c["from"] == node.id for c in self.connections)
        else:
            needs_update = any(c["from"] == node.id and c["out_idx"] == out_idx for c in self.connections)

        if needs_update:
            self.save_state()
            if out_idx == -1:
                self.connections = [c for c in self.connections if c["from"] != node.id]
            else:
                self.connections = [c for c in self.connections if not (c["from"] == node.id and c["out_idx"] == out_idx)]
            self.redraw()

    def edit_node(self, node: Node) -> None:
        self.save_state()
        NodeEditorDialog(parent=self, node=node, editor=self)

    def open_search_replace(self) -> None:
        SearchReplaceDialog(parent=self, editor=self)

    def open_character_manager(self) -> None:
        CharacterManagerDialog(parent=self, editor=self, on_change=self.on_characters_changed)

    def on_characters_changed(self) -> None:
        self.set_dirty(True)
        self.redraw()

    def delete_node(self, node: Node) -> None:
        self.save_state()
        if node in self.nodes:
            self.nodes.remove(node)
            self.connections = [c for c in self.connections if c["from"] != node.id and c["to"] != node.id]
            if node in self.selected_nodes:
                self.selected_nodes.remove(node)
            self.redraw()
            self.plugin_manager.notify("node_deleted", node)

    def set_nodes_color(self, nodes: list[Node], bg_color: str, header_color: str) -> None:
        if not nodes:
            return
        self.save_state()
        for node in nodes:
            node.custom_data["bg_color"] = bg_color
            node.custom_data["header_color"] = header_color
        self.redraw()
        self.set_dirty(True)

    def pick_custom_color_for_nodes(self, nodes: list[Node]) -> None:
        if not nodes:
            return
        default_bg = COLORS.get(f"node_{nodes[0].node_type}", COLORS["node_story"])
        current_bg = nodes[0].custom_data.get("bg_color", default_bg)
        color = colorchooser.askcolor(color=current_bg, title="Выберите цвет блоков", parent=self)
        if color and color[1]:
            bg_col = color[1]
            head_col = darken_color(bg_col, 0.75)
            self.set_nodes_color(nodes, bg_col, head_col)

    def reset_nodes_color(self, nodes: list[Node]) -> None:
        if not nodes:
            return
        self.save_state()
        for node in nodes:
            node.custom_data.pop("bg_color", None)
            node.custom_data.pop("header_color", None)
            node.custom_data.pop("text_color", None)
            node.custom_data.pop("header_text_color", None)
        self.redraw()
        self.set_dirty(True)

    def find_node_by_id(self, nid: str) -> Node | None:
        for n in self.nodes:
            if n.id == nid:
                return n
        return None

    def _reset_canvas(self) -> None:
        self.nodes = []
        self.connections = []
        self.selected_nodes = []
        self.selected_connection = None
        self.redraw()

    def clear_all(self) -> None:
        if self.nodes or self.connections:
            res = messagebox.askyesno(
                "Очистить холст",
                "Вы уверены, что хотите удалить ВСЕ ноды и связи?\nЭто действие можно будет отменить через Ctrl+Z.",
                parent=self
            )
            if not res:
                return
        self.save_state()
        self._reset_canvas()
        self.set_dirty(True)

    def start_pan(self, event: Any) -> None:
        self.is_panning = True
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.mouse_last_x = event.x
        self.mouse_last_y = event.y

    def do_pan(self, event: Any) -> None:
        dx = self.mouse_last_x - event.x
        dy = self.mouse_last_y - event.y
        self.canvas.xview_scroll(int(dx), "units")
        self.canvas.yview_scroll(int(dy), "units")
        self.velocity_x = dx
        self.velocity_y = dy
        self.mouse_last_x = event.x
        self.mouse_last_y = event.y
        self.canvas.update_grid()

    def stop_pan(self, event: Any) -> None:
        self.is_panning = False
        self.canvas.update_grid()

    def _export_to_project_data(self) -> ProjectData:
        node_datas = [n.to_node_data() for n in self.nodes]
        conn_datas = [ConnectionData.from_dict(c) for c in self.connections]
        return ProjectData(
            nodes=node_datas,
            connections=conn_datas,
            characters=self.character_manager.to_list()
        )

    def _load_project_data(self, project: ProjectData) -> None:
        self._reset_canvas()
        self.history_manager.clear()
        self.character_manager.load_from_characters(getattr(project, "characters", []))
        if not self.character_manager.list() and project.nodes:
            self.character_manager.scan_from_nodes(project.nodes)

        for n_data in project.nodes:
            node = Node.from_node_data(self, n_data)
            node.is_new = False
            node.width = max(80, int((n_data.width or 180) * self.zoom_level))
            font_size = max(6, int(9 * self.zoom_level))
            if node.font_content:
                node.font_content.configure(size=font_size)
            node.calculate_size()
            self.nodes.append(node)

        for c in project.connections:
            self.connections.append({
                "from": c.from_node,
                "out_idx": c.out_idx,
                "to": c.to_node
            })

        self.redraw()
        self.plugin_manager.notify("project_loaded", {"project": project})

    def save_project(self) -> bool:
        if not self.current_file:
            f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        else:
            f = self.current_file

        if f:
            try:
                project = self._export_to_project_data()
                ProjectSerializer.save_to_file(project, f)
                self.current_file = f
                self.set_dirty(False)
                self.autosave_manager.clear_autosave(f)
                self.plugin_manager.notify("project_saved", {"file": f, "project": project})
                return True
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить проект:\n{e}", parent=self)
        return False

    def load_project(self, file_path: str | None = None) -> bool:
        f = file_path or filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if f:
            if self.is_dirty:
                resp = messagebox.askyesnocancel(
                    "Несохранённые изменения",
                    "В текущем проекте есть несохранённые изменения.\nСохранить их перед открытием?",
                    parent=self
                )
                if resp is None:
                    return False
                if resp:
                    self.save_project()

            try:
                project = ProjectSerializer.load_from_file(f)
                self._load_project_data(project)
                self.current_file = f
                self.set_dirty(False)
                return True
            except Exception as e:
                messagebox.showerror("Ошибка загрузки", f"Не удалось загрузить проект:\n{e}", parent=self)
        return False

    def zoom_in(self, event: Any = None) -> None:
        self.apply_zoom(1.15, event)

    def zoom_out(self, event: Any = None) -> None:
        self.apply_zoom(1 / 1.15, event)

    def zoom_reset(self, event: Any = None) -> None:
        if self.zoom_level == 1.0:
            return
        self.apply_zoom(1.0 / self.zoom_level, event, target_zoom=1.0)

    def on_mousewheel(self, event: Any) -> None:
        if event.state & 0x0004:  # Ctrl -> Zoom
            if event.delta > 0:
                self.zoom_in(event)
            elif event.delta < 0:
                self.zoom_out(event)
        elif event.state & 0x0001:  # Shift -> Горизонтальный скролл
            delta = -int(event.delta / 2) if event.delta else 0
            self.canvas.xview_scroll(delta, "units")
            self.canvas.update_grid()
        else:  # Обычный скролл -> Вертикальный скролл
            delta = -int(event.delta / 2) if event.delta else 0
            self.canvas.yview_scroll(delta, "units")
            self.canvas.update_grid()

    def apply_zoom(self, factor: float, event: Any = None, target_zoom: float | None = None) -> None:
        new_zoom = target_zoom if target_zoom is not None else round(self.zoom_level * factor, 3)
        if new_zoom < self.min_zoom or new_zoom > self.max_zoom:
            return

        actual_factor = new_zoom / self.zoom_level
        self.zoom_level = new_zoom

        if event and hasattr(event, "x") and hasattr(event, "y"):
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
        else:
            cx = self.canvas.canvasx(self.canvas.winfo_width() / 2)
            cy = self.canvas.canvasy(self.canvas.winfo_height() / 2)

        for node in self.nodes:
            node.x = cx + (node.x - cx) * actual_factor
            node.y = cy + (node.y - cy) * actual_factor
            node.width = max(80, int(180 * self.zoom_level))
            font_size = max(6, int(9 * self.zoom_level))
            if node.font_content:
                node.font_content.configure(size=font_size)
            node.calculate_size()

        if hasattr(self, "lbl_zoom"):
            self.lbl_zoom.config(text=f"{int(self.zoom_level * 100)}%")
        self.redraw()

"""
Dialogue Engine - File System Explorer Plugin (Windows 11 Style)
═══════════════════════════════════════════════════════════════
Полнофункциональный проводник медиафайлов в стиле Windows 11 Fluent UI:
- Превью миниатюр изображений (PNG, JPG, WEBP, GIF, BMP)
- Карточки аудиофайлов (MP3, OGG, WAV) с бейджами форматов и размером
- Два режима отображения: Крупные плитки (⊞ Grid) и Детальный список (☰ List)
- Перетаскивание (Drag & Drop) на холст с визуальным курсором-призраком
- Быстрая фильтрация/поиск файлов на лету
- Открытие в проводнике Windows по клику
- Двойной клик для мгновенного добавления в центр холста
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from plugin_system import Plugin

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "fs_settings.json")

# Цветовая палитра Windows 11 Dark Mode (Fluent UI)
THEME = {
    "sidebar_bg": "#181818",
    "toolbar_bg": "#202020",
    "border": "#2d2d2d",
    "card_bg": "#252526",
    "card_hover": "#323233",
    "card_selected": "#094771",
    "card_border": "#333333",
    "card_border_hover": "#0078d4",
    "thumb_bg": "#121212",
    "accent": "#0078d4",
    "accent_hover": "#1084d9",
    "text_primary": "#ffffff",
    "text_secondary": "#9d9d9d",
    "text_dim": "#707070",
    "badge_bg": "#2d2d30",
    "badge_text": "#60cdff",
    "audio_accent": "#d16969",
    "music_accent": "#4ec9b0",
    "voice_accent": "#ce9178",
}


def format_file_size(size_bytes: int) -> str:
    """Форматирует размер файла в удобочитаемый вид (КБ, МБ)."""
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} КБ"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} МБ"


class FileSystemPlugin(Plugin):
    name = "Файловая Система (Drag & Drop)"
    version = "2.0"

    def on_enable(self) -> None:
        self.settings: Dict[str, Any] = {
            "backgrounds": "",
            "sprites": "",
            "music": "",
            "sounds": "",
            "voice": "",
            "view_mode": "grid",  # "grid" или "list"
            "is_collapsed": False,
            "sidebar_width": 290,
        }
        self.load_settings()

        self.current_category = "backgrounds"
        self.drag_data: Dict[str, Any] = {"item": None, "cat": None, "path": None}
        self.cached_files: Set[str] = set()
        self.thumb_cache: Dict[str, ImageTk.PhotoImage] = {}
        self.info_cache: Dict[str, str] = {}
        self._image_refs: List[Any] = []  # Защита от сборщика мусора Tkinter
        self._drag_ghost: Optional[tk.Toplevel] = None
        self._search_query: str = ""
        self._all_file_entries: List[Dict[str, Any]] = []

    def load_settings(self) -> None:
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.settings.update(json.load(f))
            except Exception:
                pass

    def save_settings(self) -> None:
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[FS Plugin] Failed to save settings: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    #  UI ИНИЦИАЛИЗАЦИЯ
    # ══════════════════════════════════════════════════════════════════════════

    def on_event(self, event_type: str, data: Any = None) -> None:
        if event_type == "setup_ui":
            self.setup_explorer_panel()

    def setup_explorer_panel(self) -> None:
        """Создает стильную боковую панель проводника Windows 11."""
        self.editor.canvas.pack_forget()

        self.width = int(self.settings.get("sidebar_width", 290))
        self.sidebar = tk.Frame(
            self.editor,
            width=self.width,
            bg=THEME["sidebar_bg"],
            highlightbackground=THEME["border"],
            highlightthickness=1,
        )
        self.sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Возвращаем холст
        self.editor.canvas.pack(fill=tk.BOTH, expand=True)

        # ── 1. Верхняя командная строка (Windows 11 Toolbar) ───────────────────
        cmd_bar = tk.Frame(self.sidebar, bg=THEME["toolbar_bg"], height=38)
        cmd_bar.pack(fill=tk.X)
        cmd_bar.pack_propagate(False)

        # Заголовок с иконкой
        title_lbl = tk.Label(
            cmd_bar,
            text="📁 Проводник",
            bg=THEME["toolbar_bg"],
            fg=THEME["text_primary"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
        )
        title_lbl.pack(side=tk.LEFT, fill=tk.Y)

        # Кнопка сворачивания
        self.btn_toggle_collapse = tk.Button(
            cmd_bar,
            text="▶",
            command=self.toggle_collapse,
            bg=THEME["toolbar_bg"],
            fg=THEME["text_secondary"],
            activebackground=THEME["card_hover"],
            activeforeground=THEME["text_primary"],
            relief="flat",
            bd=0,
            padx=8,
            cursor="hand2",
            font=("Segoe UI", 8),
        )
        self.btn_toggle_collapse.pack(side=tk.RIGHT, fill=tk.Y)

        # Кнопка настроек путей
        btn_settings = tk.Button(
            cmd_bar,
            text="⚙",
            command=self.open_settings,
            bg=THEME["toolbar_bg"],
            fg=THEME["text_secondary"],
            activebackground=THEME["card_hover"],
            activeforeground=THEME["text_primary"],
            relief="flat",
            bd=0,
            padx=6,
            cursor="hand2",
            font=("Segoe UI", 10),
        )
        btn_settings.pack(side=tk.RIGHT, fill=tk.Y)

        # Кнопка открыть текущую папку в проводнике Windows
        btn_open_folder = tk.Button(
            cmd_bar,
            text="📂",
            command=self.open_current_in_explorer,
            bg=THEME["toolbar_bg"],
            fg=THEME["text_secondary"],
            activebackground=THEME["card_hover"],
            activeforeground=THEME["text_primary"],
            relief="flat",
            bd=0,
            padx=6,
            cursor="hand2",
            font=("Segoe UI", 9),
        )
        btn_open_folder.pack(side=tk.RIGHT, fill=tk.Y)

        # Переключатель видов (Плитки ⊞ / Список ☰)
        self.btn_view_list = tk.Button(
            cmd_bar,
            text="☰",
            command=lambda: self.set_view_mode("list"),
            bg=THEME["toolbar_bg"],
            fg=THEME["text_secondary"],
            activebackground=THEME["card_hover"],
            activeforeground=THEME["text_primary"],
            relief="flat",
            bd=0,
            padx=6,
            cursor="hand2",
            font=("Segoe UI", 9),
        )
        self.btn_view_list.pack(side=tk.RIGHT, fill=tk.Y)

        self.btn_view_grid = tk.Button(
            cmd_bar,
            text="⊞",
            command=lambda: self.set_view_mode("grid"),
            bg=THEME["toolbar_bg"],
            fg=THEME["text_secondary"],
            activebackground=THEME["card_hover"],
            activeforeground=THEME["text_primary"],
            relief="flat",
            bd=0,
            padx=6,
            cursor="hand2",
            font=("Segoe UI", 9),
        )
        self.btn_view_grid.pack(side=tk.RIGHT, fill=tk.Y)

        # ── 2. Поле живого поиска (Search Box) ──────────────────────────────────
        search_box = tk.Frame(self.sidebar, bg=THEME["sidebar_bg"], padx=8, pady=6)
        search_box.pack(fill=tk.X)

        search_inner = tk.Frame(search_box, bg=THEME["card_bg"], highlightbackground=THEME["border"], highlightthickness=1)
        search_inner.pack(fill=tk.X)

        tk.Label(search_inner, text="🔍", bg=THEME["card_bg"], fg=THEME["text_dim"], font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(6, 2))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.on_search_change())
        self.search_entry = tk.Entry(
            search_inner,
            textvariable=self.search_var,
            bg=THEME["card_bg"],
            fg=THEME["text_primary"],
            insertbackground="white",
            relief="flat",
            font=("Segoe UI", 8),
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)

        btn_clear = tk.Button(
            search_inner,
            text="✕",
            command=lambda: self.search_var.set(""),
            bg=THEME["card_bg"],
            fg=THEME["text_dim"],
            activebackground=THEME["card_bg"],
            activeforeground=THEME["text_primary"],
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 7),
        )
        btn_clear.pack(side=tk.RIGHT, padx=4)

        # ── 3. Вкладки категорий (Pills Tabs) ──────────────────────────────────
        tabs_frame = tk.Frame(self.sidebar, bg=THEME["sidebar_bg"], padx=6, pady=2)
        tabs_frame.pack(fill=tk.X)

        self.cat_var = tk.StringVar(value=self.current_category)
        cats = [
            ("🖼️ Фоны", "backgrounds"),
            ("🧍 Спрайты", "sprites"),
            ("🎵 Музыка", "music"),
            ("🔊 Звуки", "sounds"),
            ("🗣️ Озвучка", "voice"),
        ]

        self.cat_buttons: Dict[str, tk.Button] = {}
        for text, val in cats:
            btn = tk.Button(
                tabs_frame,
                text=text,
                command=lambda v=val: self.set_category(v),
                bg=THEME["card_bg"],
                fg=THEME["text_secondary"],
                activebackground=THEME["accent_hover"],
                activeforeground="white",
                relief="flat",
                bd=0,
                padx=6,
                pady=3,
                cursor="hand2",
                font=("Segoe UI", 8),
            )
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
            self.cat_buttons[val] = btn

        # ── 4. Основная прокручиваемая область карточек ────────────────────────
        container = tk.Frame(self.sidebar, bg=THEME["sidebar_bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.scroll_canvas = tk.Canvas(container, bg=THEME["sidebar_bg"], highlightthickness=0)
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.scroll_canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.cards_frame = tk.Frame(self.scroll_canvas, bg=THEME["sidebar_bg"])
        self.window_id = self.scroll_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")

        self.cards_frame.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")),
        )
        self.scroll_canvas.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.itemconfig(self.window_id, width=e.width),
        )

        # Колесико мыши для плавной прокрутки
        self.scroll_canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.cards_frame.bind("<MouseWheel>", self.on_mousewheel)

        # ── 5. Информационный футер (Status Bar) ───────────────────────────────
        self.status_lbl = tk.Label(
            self.sidebar,
            text="💡 Перетащите на холст или кликните дважды",
            bg=THEME["toolbar_bg"],
            fg=THEME["text_dim"],
            font=("Segoe UI", 7),
            pady=3,
        )
        self.status_lbl.pack(fill=tk.X, side=tk.BOTTOM)

        # Обновляем визуальное состояние
        self.update_view_mode_buttons()
        self.update_buttons_visual()
        self.refresh_list()
        self.editor.after(1000, self.auto_refresh)

    # ══════════════════════════════════════════════════════════════════════════
    #  УПРАВЛЕНИЕ РЕЖИМАМИ И КАТЕГОРИЯМИ
    # ══════════════════════════════════════════════════════════════════════════

    def toggle_collapse(self) -> None:
        """Сворачивает панель в узкую полоску для максимального обзора холста."""
        is_col = not self.settings.get("is_collapsed", False)
        self.settings["is_collapsed"] = is_col
        if is_col:
            self.sidebar.configure(width=34)
            self.btn_toggle_collapse.configure(text="◀")
        else:
            self.sidebar.configure(width=self.width)
            self.btn_toggle_collapse.configure(text="▶")
        self.save_settings()

    def set_view_mode(self, mode: str) -> None:
        self.settings["view_mode"] = mode
        self.update_view_mode_buttons()
        self.save_settings()
        self.render_file_items()

    def update_view_mode_buttons(self) -> None:
        mode = self.settings.get("view_mode", "grid")
        if mode == "grid":
            self.btn_view_grid.config(bg=THEME["accent"], fg="white")
            self.btn_view_list.config(bg=THEME["toolbar_bg"], fg=THEME["text_secondary"])
        else:
            self.btn_view_grid.config(bg=THEME["toolbar_bg"], fg=THEME["text_secondary"])
            self.btn_view_list.config(bg=THEME["accent"], fg="white")

    def set_category(self, cat: str) -> None:
        self.cat_var.set(cat)
        self.current_category = cat
        self.update_buttons_visual()
        self.refresh_list()

    def update_buttons_visual(self) -> None:
        curr = self.cat_var.get()
        for val, btn in self.cat_buttons.items():
            if val == curr:
                btn.config(bg=THEME["accent"], fg="white", font=("Segoe UI", 8, "bold"))
            else:
                btn.config(bg=THEME["card_bg"], fg=THEME["text_secondary"], font=("Segoe UI", 8))

    def on_mousewheel(self, event: Any) -> None:
        delta = int(-1 * (event.delta / 120))
        self.scroll_canvas.yview_scroll(delta * 2, "units")

    def on_search_change(self) -> None:
        self._search_query = self.search_var.get().strip().lower()
        self.render_file_items()

    def open_current_in_explorer(self) -> None:
        """Открывает текущую папку в стандартном Проводнике Windows 11."""
        cat = self.cat_var.get()
        path = self.settings.get(cat, "")
        if path and os.path.exists(path):
            os.startfile(os.path.normpath(path))
        else:
            self.open_settings()

    # ══════════════════════════════════════════════════════════════════════════
    #  ЗАГРУЗКА И ГЕНЕРАЦИЯ МИНИАТЮР
    # ══════════════════════════════════════════════════════════════════════════

    def get_image_thumbnail(self, full_path: str, target_size: Tuple[int, int]) -> Optional[Any]:
        """Генерирует и кэширует миниатюру изображения с сохранением пропорций."""
        cache_key = f"{full_path}_{target_size[0]}x{target_size[1]}"
        if cache_key in self.thumb_cache:
            return self.thumb_cache[cache_key]

        if not HAS_PIL:
            return None

        try:
            with Image.open(full_path) as img:
                w, h = img.size
                self.info_cache[full_path] = f"{w}×{h}"
                img = img.convert("RGBA")
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.thumb_cache[cache_key] = photo
                self._image_refs.append(photo)
                return photo
        except Exception:
            return None

    def refresh_list(self) -> None:
        """Считывает файлы из папки текущей категории."""
        cat = self.cat_var.get()
        path = self.settings.get(cat, "")

        self._all_file_entries.clear()

        if not path or not os.path.exists(path):
            self.render_empty_message("Папка не задана или не найдена.\nНажмите ⚙ чтобы выбрать путь.")
            self.cached_files = set()
            return

        try:
            raw_files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            self.cached_files = set(raw_files)

            allowed = []
            if cat in ["backgrounds", "sprites"]:
                allowed = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]
            elif cat in ["music", "sounds", "voice"]:
                allowed = [".mp3", ".ogg", ".wav"]

            for filename in raw_files:
                ext = os.path.splitext(filename)[1].lower()
                if not allowed or ext in allowed:
                    full_p = os.path.join(path, filename)
                    try:
                        sz = os.path.getsize(full_p)
                    except Exception:
                        sz = 0
                    self._all_file_entries.append({
                        "name": filename,
                        "path": full_p,
                        "ext": ext,
                        "size": sz,
                        "size_str": format_file_size(sz),
                    })

            self.render_file_items()
        except Exception as exc:
            self.render_empty_message(f"Ошибка чтения: {exc}")
            self.cached_files = set()

    def auto_refresh(self) -> None:
        try:
            cat = self.cat_var.get()
            path = self.settings.get(cat, "")
            if path and os.path.exists(path):
                current = set(f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)))
                if current != self.cached_files:
                    self.refresh_list()
        except Exception:
            pass
        if hasattr(self, "editor") and hasattr(self.editor, "after"):
            self.editor.after(1500, self.auto_refresh)

    # ══════════════════════════════════════════════════════════════════════════
    #  ОТРИСОВКА КАРТОЧЕК (WINDOWS 11 STYLE)
    # ══════════════════════════════════════════════════════════════════════════

    def render_empty_message(self, text: str) -> None:
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        lbl = tk.Label(
            self.cards_frame,
            text=text,
            bg=THEME["sidebar_bg"],
            fg=THEME["text_dim"],
            font=("Segoe UI", 9),
            justify="center",
            pady=40,
        )
        lbl.pack(fill=tk.BOTH, expand=True)

    def render_file_items(self) -> None:
        """Перерисовывает карточки файлов с учётом режима сетки/списка и поиска."""
        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        query = self._search_query
        filtered = [
            item for item in self._all_file_entries
            if not query or query in item["name"].lower()
        ]

        # Обновляем статусную строку
        self.status_lbl.configure(text=f"Файлов: {len(filtered)} из {len(self._all_file_entries)}")

        if not filtered:
            msg = "Файлов не найдено" if query else "Папка пуста"
            self.render_empty_message(msg)
            return

        mode = self.settings.get("view_mode", "grid")
        if mode == "grid":
            self._render_grid(filtered)
        else:
            self._render_list(filtered)

    def _render_grid(self, files: List[Dict[str, Any]]) -> None:
        """Отображение крупными плитками (Grid) в 2 колонки как в Windows 11."""
        cols = 2
        for idx, item in enumerate(files):
            r = idx // cols
            c = idx % cols

            card = tk.Frame(
                self.cards_frame,
                bg=THEME["card_bg"],
                highlightbackground=THEME["card_border"],
                highlightthickness=1,
                cursor="hand2",
            )
            card.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
            self.cards_frame.grid_columnconfigure(c, weight=1, uniform="col")

            # ── Область превью ────────────────────────────────────────────────
            thumb_box = tk.Frame(card, bg=THEME["thumb_bg"], height=70)
            thumb_box.pack(fill=tk.X, padx=2, pady=(2, 0))
            thumb_box.pack_propagate(False)

            is_img = item["ext"] in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]
            thumb_img = self.get_image_thumbnail(item["path"], (110, 68)) if is_img else None

            if thumb_img:
                preview_lbl = tk.Label(thumb_box, image=thumb_img, bg=THEME["thumb_bg"])
                preview_lbl.pack(expand=True)
            else:
                # Бейдж для аудио или заглушки
                icon_text = "🎵" if item["ext"] in [".mp3", ".ogg", ".wav"] else "📄"
                accent_col = THEME["music_accent"] if item["ext"] in [".mp3", ".ogg", ".wav"] else THEME["badge_text"]
                preview_lbl = tk.Label(
                    thumb_box,
                    text=f"{icon_text}\n{item['ext'].upper().lstrip('.')}",
                    bg=THEME["thumb_bg"],
                    fg=accent_col,
                    font=("Segoe UI", 9, "bold"),
                )
                preview_lbl.pack(expand=True)

            # ── Текстовая информация ──────────────────────────────────────────
            info_box = tk.Frame(card, bg=THEME["card_bg"], padx=4, pady=3)
            info_box.pack(fill=tk.X)

            # Имя файла с усечением
            name_lbl = tk.Label(
                info_box,
                text=item["name"],
                bg=THEME["card_bg"],
                fg=THEME["text_primary"],
                font=("Segoe UI", 8),
                anchor="w",
                justify="left",
            )
            name_lbl.pack(fill=tk.X)

            # Доп. инфо: разрешение / размер
            dim_text = self.info_cache.get(item["path"], "")
            sub_text = f"{dim_text} • {item['size_str']}" if dim_text else item["size_str"]
            sub_lbl = tk.Label(
                info_box,
                text=sub_text,
                bg=THEME["card_bg"],
                fg=THEME["text_dim"],
                font=("Segoe UI", 7),
                anchor="w",
            )
            sub_lbl.pack(fill=tk.X)

            # Привязываем события мыши
            self._bind_card_events(card, item, [preview_lbl, name_lbl, sub_lbl, thumb_box, info_box])

    def _render_list(self, files: List[Dict[str, Any]]) -> None:
        """Отображение компактным списком (Details List)."""
        for item in files:
            row = tk.Frame(
                self.cards_frame,
                bg=THEME["card_bg"],
                highlightbackground=THEME["card_border"],
                highlightthickness=1,
                cursor="hand2",
                pady=2,
            )
            row.pack(fill=tk.X, padx=3, pady=2)

            is_img = item["ext"] in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]
            thumb_img = self.get_image_thumbnail(item["path"], (36, 26)) if is_img else None

            if thumb_img:
                icon_lbl = tk.Label(row, image=thumb_img, bg=THEME["card_bg"], width=38)
            else:
                icon_lbl = tk.Label(
                    row,
                    text="🎵" if item["ext"] in [".mp3", ".ogg", ".wav"] else "📄",
                    bg=THEME["card_bg"],
                    fg=THEME["music_accent"],
                    font=("Segoe UI", 9),
                    width=4,
                )
            icon_lbl.pack(side=tk.LEFT, padx=3)

            name_lbl = tk.Label(
                row,
                text=item["name"],
                bg=THEME["card_bg"],
                fg=THEME["text_primary"],
                font=("Segoe UI", 8),
                anchor="w",
            )
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

            size_lbl = tk.Label(
                row,
                text=item["size_str"],
                bg=THEME["card_bg"],
                fg=THEME["text_dim"],
                font=("Segoe UI", 7),
                padx=6,
            )
            size_lbl.pack(side=tk.RIGHT)

            self._bind_card_events(row, item, [icon_lbl, name_lbl, size_lbl])

    # ══════════════════════════════════════════════════════════════════════════
    #  ИНТЕРАКТИВНОСТЬ: HOVER, DRAG & DROP, CONTEXT MENU
    # ══════════════════════════════════════════════════════════════════════════

    def _bind_card_events(self, card: tk.Widget, item: Dict[str, Any], children: List[tk.Widget]) -> None:
        """Привязывает hover-подсветку, drag & drop и контекстное меню ко всей карточке."""
        all_widgets = [card] + children

        def on_enter(e: Any) -> None:
            card.configure(bg=THEME["card_hover"], highlightbackground=THEME["card_border_hover"])
            for w in children:
                try:
                    if w.cget("bg") == THEME["card_bg"]:
                        w.configure(bg=THEME["card_hover"])
                except Exception:
                    pass

        def on_leave(e: Any) -> None:
            card.configure(bg=THEME["card_bg"], highlightbackground=THEME["card_border"])
            for w in children:
                try:
                    if w.cget("bg") == THEME["card_hover"]:
                        w.configure(bg=THEME["card_bg"])
                except Exception:
                    pass

        for w in all_widgets:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<ButtonPress-1>", lambda e, it=item: self.on_drag_start(e, it))
            w.bind("<B1-Motion>", self.on_drag_motion)
            w.bind("<ButtonRelease-1>", self.on_drag_release)
            w.bind("<Double-Button-1>", lambda e, it=item: self.on_double_click_card(it))
            w.bind("<Button-3>", lambda e, it=item: self.show_context_menu(e, it))

    def on_drag_start(self, event: Any, item: Dict[str, Any]) -> None:
        self.drag_data["item"] = item["name"]
        self.drag_data["cat"] = self.cat_var.get()
        self.drag_data["path"] = item["path"]

        # Создаем полупрозрачный курсор-призрак Windows 11
        self._show_drag_ghost(item["name"], event.x_root, event.y_root)

    def on_drag_motion(self, event: Any) -> None:
        if self._drag_ghost and self._drag_ghost.winfo_exists():
            self._drag_ghost.geometry(f"+{event.x_root + 14}+{event.y_root + 14}")

    def on_drag_release(self, event: Any) -> None:
        self._hide_drag_ghost()

        if not self.drag_data.get("item"):
            return

        x, y = event.x_root, event.y_root
        canvas = self.editor.canvas

        try:
            cx = canvas.winfo_rootx()
            cy = canvas.winfo_rooty()
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()

            # Если мышь отпустили над холстом редактора
            if cx <= x <= cx + cw and cy <= y <= cy + ch:
                canvas_x = canvas.canvasx(x - cx)
                canvas_y = canvas.canvasy(y - cy)
                self.create_node_from_file(
                    self.drag_data["item"], self.drag_data["cat"], canvas_x, canvas_y
                )
        except Exception as e:
            print(f"[FS Plugin] Drop error: {e}")

        self.drag_data["item"] = None

    def on_double_click_card(self, item: Dict[str, Any]) -> None:
        """При двойном клике создаёт узел в центре текущего экрана холста."""
        canvas = self.editor.canvas
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        center_x = canvas.canvasx(cw / 2)
        center_y = canvas.canvasy(ch / 2)
        self.create_node_from_file(item["name"], self.cat_var.get(), center_x, center_y)

    def _show_drag_ghost(self, text: str, x: int, y: int) -> None:
        try:
            self._hide_drag_ghost()
            ghost = tk.Toplevel(self.editor)
            ghost.overrideredirect(True)
            ghost.attributes("-alpha", 0.88)
            ghost.config(bg=THEME["accent"])

            lbl = tk.Label(
                ghost,
                text=f" 📦 {text} ",
                bg=THEME["accent"],
                fg="white",
                font=("Segoe UI", 9, "bold"),
            )
            lbl.pack(padx=4, pady=2)
            ghost.geometry(f"+{x + 14}+{y + 14}")
            ghost.lift()
            self._drag_ghost = ghost
        except Exception:
            pass

    def _hide_drag_ghost(self) -> None:
        if self._drag_ghost and self._drag_ghost.winfo_exists():
            try:
                self._drag_ghost.destroy()
            except Exception:
                pass
            self._drag_ghost = None

    def show_context_menu(self, event: Any, item: Dict[str, Any]) -> None:
        """Всплывающее меню правой кнопки мыши."""
        menu = tk.Menu(self.editor, tearoff=0, bg="#2b2b2b", fg="white", activebackground=THEME["accent"])
        menu.add_command(
            label="➕ Вставить на холст",
            command=lambda: self.on_double_click_card(item),
        )
        menu.add_command(
            label="📂 Показать в Проводнике Windows",
            command=lambda: subprocess.run(["explorer", "/select,", os.path.normpath(item["path"])]),
        )
        menu.add_separator()
        menu.add_command(
            label="📋 Копировать имя файла",
            command=lambda: self._copy_to_clipboard(item["name"]),
        )
        menu.add_command(
            label="📋 Копировать полный путь",
            command=lambda: self._copy_to_clipboard(item["path"]),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_to_clipboard(self, text: str) -> None:
        self.editor.clipboard_clear()
        self.editor.clipboard_append(text)

    # ══════════════════════════════════════════════════════════════════════════
    #  СОЗДАНИЕ УЗЛОВ СЦЕНАРИЯ
    # ══════════════════════════════════════════════════════════════════════════

    def create_node_from_file(self, filename: str, category: str, x: float, y: float) -> None:
        """Создает соответствующий узел на холсте при сбросе файла."""
        base_path = self.settings.get(category, "")
        full_path = os.path.join(base_path, filename).replace("\\", "/")
        name_no_ext = os.path.splitext(filename)[0]

        if category in ["music", "sounds", "voice"]:
            if category == "music":
                mode = "bg"
                icon = "🔁"
                header_col = "#0d4528"
                bg_col = "#196f3d"
            elif category == "sounds":
                mode = "sfx"
                icon = "🔊"
                header_col = "#5b2c6f"
                bg_col = "#7d3c98"
            else:
                mode = "voice"
                icon = "🗣️"
                header_col = "#6e2c00"
                bg_col = "#a04000"

            content = f"{icon} {mode.upper()}\n📂: {filename}"
            custom_data = {
                "music_mode": mode,
                "music_file": full_path,
                "bg_color": bg_col,
                "header_color": header_col,
            }
            node = self.editor.add_node("music", x=x, y=y, title=filename, content=content, custom_data=custom_data)
            self.editor.selected_nodes = [node]
            self.editor.redraw()

        elif category in ["backgrounds", "sprites"]:
            mode = "background" if category == "backgrounds" else "sprite"
            data_dict = {
                "image_path": full_path,
                "mode": mode,
                "position": "center",
                "transition": "none",
            }
            content = json.dumps(data_dict, ensure_ascii=False)
            node = self.editor.add_node("media", x=x, y=y, title=name_no_ext, content=content)
            self.editor.selected_nodes = [node]
            self.editor.redraw()

    # ══════════════════════════════════════════════════════════════════════════
    #  ДИАЛОГ НАСТРОЕК ПУТЕЙ (WINDOWS 11 MODAL)
    # ══════════════════════════════════════════════════════════════════════════

    def open_settings(self) -> None:
        win = tk.Toplevel(self.editor)
        win.title("Настройка путей к медиафайлам")
        win.geometry("540x310")
        win.configure(bg=THEME["sidebar_bg"])
        win.transient(self.editor)
        win.grab_set()

        header = tk.Frame(win, bg=THEME["toolbar_bg"], pady=10, padx=15)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="📁 Папки проекта",
            bg=THEME["toolbar_bg"],
            fg=THEME["text_primary"],
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Укажите директории вашего проекта с фонами, спрайтами и звуками.",
            bg=THEME["toolbar_bg"],
            fg=THEME["text_dim"],
            font=("Segoe UI", 8),
        ).pack(anchor="w")

        body = tk.Frame(win, bg=THEME["sidebar_bg"], padx=15, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        cats = [
            ("Фоны (Backgrounds):", "backgrounds"),
            ("Спрайты (Sprites):", "sprites"),
            ("Музыка (Music):", "music"),
            ("Звуки (Sounds):", "sounds"),
            ("Озвучка (Voice):", "voice"),
        ]

        path_vars = {}
        for i, (label, key) in enumerate(cats):
            tk.Label(body, text=label, bg=THEME["sidebar_bg"], fg=THEME["text_secondary"], font=("Segoe UI", 8)).grid(
                row=i, column=0, padx=5, pady=4, sticky="e"
            )
            var = tk.StringVar(value=self.settings.get(key, ""))
            path_vars[key] = var
            entry = tk.Entry(
                body,
                textvariable=var,
                width=38,
                bg=THEME["card_bg"],
                fg=THEME["text_primary"],
                relief="flat",
                font=("Segoe UI", 8),
            )
            entry.grid(row=i, column=1, padx=5, pady=4, sticky="we")

            def browse(k=key, v=var):
                d = filedialog.askdirectory(initialdir=v.get() if os.path.exists(v.get()) else ".")
                if d:
                    v.set(d)

            tk.Button(
                body,
                text="Обзор...",
                command=browse,
                bg=THEME["card_bg"],
                fg=THEME["text_primary"],
                activebackground=THEME["card_hover"],
                relief="flat",
                font=("Segoe UI", 8),
                padx=8,
            ).grid(row=i, column=2, padx=5, pady=4)

        def save():
            for k, v in path_vars.items():
                self.settings[k] = v.get().replace("\\", "/")
            self.save_settings()
            self.refresh_list()
            win.destroy()

        btn_save = tk.Button(
            win,
            text="Сохранить пути",
            command=save,
            bg=THEME["accent"],
            fg="white",
            activebackground=THEME["accent_hover"],
            activeforeground="white",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            pady=6,
            cursor="hand2",
        )
        btn_save.pack(fill=tk.X, padx=15, pady=(0, 15))

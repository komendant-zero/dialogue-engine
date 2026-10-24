"""
Dialogue Engine - Node Editor Modal Dialog.
"""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk
from typing import Any, Callable, Optional

from core.sprites import SpriteResolver
from ui.theme import COLORS, NODE_COLOR_PRESETS, darken_color

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class NodeEditorDialog:
    """Модальное окно редактирования свойств и содержимого узла."""

    def __init__(self, parent: tk.Widget, node: Any, editor: Any, on_save: Optional[Callable[[], None]] = None):
        self.parent = parent
        self.node = node
        self.editor = editor
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Редактор блока")
        self.dialog.geometry("620x760")
        self.dialog.configure(bg=COLORS["bg"])
        self.dialog.transient(parent)
        self.dialog.attributes("-topmost", True)
        self._node_sprite_photo = None

        self._build_ui()

    def _build_ui(self) -> None:
        is_story = (self.node.node_type == "story")

        top_container = tk.Frame(self.dialog, bg=COLORS["bg"])
        top_container.pack(fill=tk.X, padx=10, pady=(5, 0))

        left_controls = tk.Frame(top_container, bg=COLORS["bg"])
        left_controls.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        title_lbl_text = "👤 Имя персонажа (# или пусто — слова автора/мысли):" if is_story else "🏷️ Заголовок блока (# — скрыть):"
        tk.Label(left_controls, text=title_lbl_text, bg=COLORS["bg"], fg="white").pack(anchor="w", pady=(0, 2))

        title_frame = tk.Frame(left_controls, bg=COLORS["bg"])
        title_frame.pack(fill=tk.X)

        # Превью спрайта персонажа (если Story)
        if is_story:
            self.sprite_preview_frame = tk.Frame(top_container, bg="#252526", bd=1, relief="solid", width=105, height=135)
            self.sprite_preview_frame.pack(side=tk.RIGHT, padx=(10, 0), pady=(0, 2))
            self.sprite_preview_frame.pack_propagate(False)

            tk.Label(self.sprite_preview_frame, text="🧍 Спрайт", bg="#252526", fg="#aaaaaa", font=("Segoe UI", 7, "bold")).pack(pady=(2, 0))
            self.canvas_sprite_preview = tk.Canvas(self.sprite_preview_frame, width=95, height=105, bg="#1e1e1e", bd=0, highlightthickness=0)
            self.canvas_sprite_preview.pack(pady=1)
            self.lbl_sprite_name = tk.Label(self.sprite_preview_frame, text="—", bg="#252526", fg="#2ecc71", font=("Segoe UI", 7))
            self.lbl_sprite_name.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 2))

        # Список существующих персонажей в проекте
        char_mgr = getattr(self.editor, "character_manager", None)
        registered_chars = set(char_mgr.names()) if char_mgr else set()
        node_chars = {
            n.title.strip() for n in self.editor.nodes
            if n.node_type == "story" and n.title.strip() and not n.title.strip().startswith("#") and n.title.strip() not in ("Сцена", "Персонаж")
        }
        existing_chars = sorted(list(registered_chars | node_chars))

        if is_story:
            self.e_title = ttk.Combobox(title_frame, values=existing_chars, font=("Segoe UI", 9))
            self.e_title.set(self.node.title)
            self.e_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.e_title.bind("<<ComboboxSelected>>", self._on_character_selected)
            self.e_title.bind("<KeyRelease>", self._on_character_typed)
        else:
            self.e_title = tk.Entry(title_frame, bg="#333", fg="white", insertbackground="white", font=("Segoe UI", 9))
            self.e_title.insert(0, self.node.title)
            self.e_title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if is_story:
            def set_narrator():
                if isinstance(self.e_title, ttk.Combobox):
                    self.e_title.set("#")
                else:
                    self.e_title.delete(0, tk.END)
                    self.e_title.insert(0, "#")
                self.node.custom_data.pop("emotion", None)
                self.node.custom_data.pop("sprite_path", None)
                self._update_emotion_bar()
                self._render_sprite_preview()
                self._auto_save()

            tk.Button(
                title_frame, text="👥 Герои...", command=self._open_char_manager,
                bg="#2c3e50", fg="white", relief="flat", font=("Segoe UI", 8), padx=6
            ).pack(side=tk.RIGHT, padx=(5, 0))

            tk.Button(
                title_frame, text="💭 Слова автора (#)", command=set_narrator,
                bg="#333333", fg="#aaaaaa", relief="flat", font=("Segoe UI", 8), padx=6
            ).pack(side=tk.RIGHT, padx=(5, 0))

            # Панель выбора эмоций персонажа
            self.emotion_frame = tk.Frame(left_controls, bg=COLORS["bg"])
            self.emotion_frame.pack(fill=tk.X, pady=(4, 0))
            self._update_emotion_bar()
            self._render_sprite_preview()

        # Оформление блока
        color_frame = tk.LabelFrame(self.dialog, text="🎨 Оформление блока", bg=COLORS["bg"], fg="white", padx=8, pady=8)
        color_frame.pack(fill=tk.X, padx=10, pady=5)

        default_bg = COLORS.get(f"node_{self.node.node_type}", COLORS["node_story"])
        default_head = COLORS.get(f"header_{self.node.node_type}", COLORS["header_story"])

        self.preview_box = tk.Frame(
            color_frame,
            bg=self.node.custom_data.get("bg_color", default_bg),
            relief="solid", bd=1, height=45
        )
        self.preview_box.pack(fill=tk.X, pady=(0, 6))
        self.preview_box.pack_propagate(False)

        self.preview_head = tk.Frame(self.preview_box, bg=self.node.custom_data.get("header_color", default_head), height=20)
        self.preview_head.pack(fill=tk.X, side=tk.TOP)
        self.preview_head.pack_propagate(False)

        self.lbl_head_title = tk.Label(
            self.preview_head,
            text=self.node.title or "Заголовок",
            bg=self.node.custom_data.get("header_color", default_head),
            fg=self.node.custom_data.get("header_text_color", "white"),
            font=("Segoe UI", 8, "bold"), anchor="w", padx=5
        )
        self.lbl_head_title.pack(fill=tk.BOTH, expand=True)

        self.lbl_body_preview = tk.Label(
            self.preview_box,
            text="Образец текста блока",
            bg=self.node.custom_data.get("bg_color", default_bg),
            fg=self.node.custom_data.get("text_color", COLORS["text"]),
            font=("Segoe UI", 8), anchor="w", padx=5
        )
        self.lbl_body_preview.pack(fill=tk.BOTH, expand=True)

        # Палитра быстрых пресетов
        palette_frame = tk.Frame(color_frame, bg=COLORS["bg"])
        palette_frame.pack(fill=tk.X, pady=4)

        for _, bg_c, head_c in NODE_COLOR_PRESETS:
            tk.Button(
                palette_frame,
                bg=bg_c,
                activebackground=head_c,
                width=2,
                height=1,
                relief="flat",
                cursor="hand2",
                command=lambda b=bg_c, h=head_c: self._apply_preset(b, h)
            ).pack(side=tk.LEFT, padx=2)

        # Кнопки детального выбора цвета
        btn_grid = tk.Frame(color_frame, bg=COLORS["bg"])
        btn_grid.pack(fill=tk.X, pady=(4, 0))
        btn_style = {"bg": "#333333", "fg": "white", "relief": "flat", "font": ("Segoe UI", 8), "padx": 6, "pady": 2, "cursor": "hand2"}

        tk.Button(btn_grid, text="Фон...", command=self._pick_bg, **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_grid, text="Шапка...", command=self._pick_header_bg, **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_grid, text="Текст заголовка...", command=self._pick_header_txt, **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_grid, text="Текст...", command=self._pick_text_color, **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_grid, text="🔄 Сброс", command=self._reset_colors, **btn_style).pack(side=tk.RIGHT, padx=2)

        # Контент
        tk.Label(self.dialog, text="Текст / Контент:", bg=COLORS["bg"], fg="white").pack(pady=5)
        self.t_content = tk.Text(self.dialog, height=8, bg="#333", fg="white", insertbackground="white")
        self.t_content.insert("1.0", self.node.content)
        self.t_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Функционал выделения слов
        hl_frame = tk.LabelFrame(self.dialog, text="Выделение слов цветом", bg=COLORS["bg"], fg="white", padx=5, pady=5)
        hl_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(
            hl_frame, text="Окрасить фрагмент", command=self._highlight_selected_word, bg="#2d4a57", fg="white"
        ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        tk.Button(
            hl_frame, text="Сбросить выделение", command=self._clear_highlights, bg="#a93226", fg="white"
        ).pack(side=tk.RIGHT, padx=5, expand=True, fill=tk.X)

        # Фрейм для плагинов
        self.plugin_frame = tk.Frame(self.dialog, bg=COLORS["bg"])
        self.plugin_frame.pack(fill=tk.X, padx=10, pady=10)

        if hasattr(self.editor, "plugin_manager"):
            self.editor.plugin_manager.notify("node_edit_dialog", {
                "node": self.node,
                "frame": self.plugin_frame,
                "dialog": self.dialog
            })

        self.e_title.bind("<KeyRelease>", self._auto_save)
        self.t_content.bind("<KeyRelease>", self._auto_save)

        # Фокус на поле ввода для немедленной готовности к набору текста
        if hasattr(self, "e_title"):
            self.e_title.focus_set()
        elif hasattr(self, "t_content"):
            self.t_content.focus_set()

        tk.Button(
            self.dialog, text="Сохранить и Закрыть", command=self._save_and_close,
            bg=COLORS["header_story"], fg="white"
        ).pack(pady=10)

    def _open_char_manager(self) -> None:
        from ui.dialogs.character_manager import CharacterManagerDialog
        CharacterManagerDialog(self.dialog, self.editor, on_change=self._refresh_characters_list)

    def _refresh_characters_list(self) -> None:
        char_mgr = getattr(self.editor, "character_manager", None)
        registered_chars = set(char_mgr.names()) if char_mgr else set()
        node_chars = {
            n.title.strip() for n in self.editor.nodes
            if n.node_type == "story" and n.title.strip() and not n.title.strip().startswith("#") and n.title.strip() not in ("Сцена", "Персонаж")
        }
        all_chars = sorted(list(registered_chars | node_chars))
        if hasattr(self, "e_title") and isinstance(self.e_title, ttk.Combobox):
            self.e_title["values"] = all_chars
        self._update_emotion_bar()
        self._render_sprite_preview()
        self._update_preview()

    def _on_character_selected(self, event: Any = None) -> None:
        name = self.e_title.get().strip()
        char_mgr = getattr(self.editor, "character_manager", None)
        if char_mgr:
            char = char_mgr.get(name)
            if char:
                if char.color and char.color.lower() != "#ffffff":
                    self.node.custom_data["header_text_color"] = char.color
                if char.header_color:
                    self.node.custom_data["header_color"] = char.header_color
                if char.bg_color:
                    self.node.custom_data["bg_color"] = char.bg_color
        self._update_emotion_bar()
        self._render_sprite_preview()
        self._auto_save()

    def _on_character_typed(self, event: Any = None) -> None:
        self._update_emotion_bar()
        self._render_sprite_preview()
        self._auto_save()

    def _update_emotion_bar(self) -> None:
        if not hasattr(self, "emotion_frame"):
            return

        for child in self.emotion_frame.winfo_children():
            child.destroy()

        if self.node.node_type != "story":
            return

        name = self.e_title.get().strip() if hasattr(self, "e_title") else ""
        if not name or name.startswith("#"):
            return

        char_mgr = getattr(self.editor, "character_manager", None)
        char = char_mgr.get(name) if char_mgr else None

        # Проверяем реальные файлы спрайтов на диске через Auto-Sprite Resolver
        disk_sprites = SpriteResolver.find_all_character_sprites(name, editor=self.editor)
        disk_labels = [label for label, _ in disk_sprites]

        if disk_labels:
            emotions = disk_labels
        elif char and char.emotions:
            emotions = char.emotions
        else:
            emotions = ["обычный", "радость", "грусть", "злость"]

        curr_emo = self.node.custom_data.get("emotion", "")
        resolved_sprite = SpriteResolver.resolve_sprite(name, curr_emo, editor=self.editor)
        if resolved_sprite:
            self.node.custom_data["sprite_path"] = resolved_sprite

        tk.Label(
            self.emotion_frame, text="🎭 Эмоция:", bg=COLORS["bg"], fg="#888888", font=("Segoe UI", 8)
        ).pack(side=tk.LEFT, padx=(0, 4))

        # Кнопка сброса эмоции
        tk.Button(
            self.emotion_frame,
            text="—",
            command=lambda: self._set_node_emotion(""),
            bg="#3a3a3a" if not curr_emo else "#252526",
            fg="white" if not curr_emo else "#888888",
            relief="flat",
            font=("Segoe UI", 7),
            padx=4,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=1)

        # Отображаем до 7 быстрых кнопок эмоций/поз
        for emo in emotions[:7]:
            is_active = (curr_emo == emo)
            btn = tk.Button(
                self.emotion_frame,
                text=emo,
                command=lambda e=emo: self._set_node_emotion(e),
                bg=COLORS["header_story"] if is_active else "#2d3748",
                fg="white" if is_active else "#cccccc",
                activebackground=COLORS["header_story"],
                relief="flat",
                font=("Segoe UI", 7, "bold" if is_active else "normal"),
                padx=5,
                pady=1,
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=2)

        # Индикатор привязанного файла спрайта
        if resolved_sprite:
            filename = os.path.basename(resolved_sprite)
            lbl_spr = tk.Label(
                self.emotion_frame,
                text=f"🧍 {filename}",
                bg=COLORS["bg"],
                fg="#2ecc71",
                font=("Segoe UI", 7)
            )
            lbl_spr.pack(side=tk.LEFT, padx=(6, 2))

    def _set_node_emotion(self, emotion: str) -> None:
        name = self.e_title.get().strip() if hasattr(self, "e_title") else ""
        if emotion:
            self.node.custom_data["emotion"] = emotion
            spr = SpriteResolver.resolve_sprite(name, emotion, editor=self.editor)
            if spr:
                self.node.custom_data["sprite_path"] = spr
        else:
            self.node.custom_data.pop("emotion", None)
            self.node.custom_data.pop("sprite_path", None)
        self._update_emotion_bar()
        self._render_sprite_preview()
        self._auto_save()

    def _render_sprite_preview(self) -> None:
        if not hasattr(self, "canvas_sprite_preview"):
            return
        self.canvas_sprite_preview.delete("all")

        name = self.e_title.get().strip() if hasattr(self, "e_title") else ""
        if not name or name.startswith("#"):
            if hasattr(self, "lbl_sprite_name"):
                self.lbl_sprite_name.config(text="—")
            return

        emo = self.node.custom_data.get("emotion", "")
        spr_path = self.node.custom_data.get("sprite_path")
        if not spr_path:
            spr_path = SpriteResolver.resolve_sprite(name, emo, editor=self.editor)

        if spr_path and os.path.exists(spr_path) and HAS_PIL:
            try:
                fname = os.path.basename(spr_path)
                if hasattr(self, "lbl_sprite_name"):
                    self.lbl_sprite_name.config(text=fname[:14])
                with Image.open(spr_path) as im:
                    w_im, h_im = im.size
                    scale = min(95.0 / w_im, 105.0 / h_im)
                    new_w = max(1, int(w_im * scale))
                    new_h = max(1, int(h_im * scale))
                    resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    self._node_sprite_photo = ImageTk.PhotoImage(resized)
                    self.canvas_sprite_preview.create_image(
                        47, 52, image=self._node_sprite_photo
                    )
                    return
            except Exception:
                pass

        if hasattr(self, "lbl_sprite_name"):
            self.lbl_sprite_name.config(text="Без спрайта")
        self.canvas_sprite_preview.create_text(
            47, 52, text="👤", fill="#555555", font=("Segoe UI", 24)
        )

    def _update_preview(self) -> None:
        default_bg = COLORS.get(f"node_{self.node.node_type}", COLORS["node_story"])
        default_head = COLORS.get(f"header_{self.node.node_type}", COLORS["header_story"])

        bg_col = self.node.custom_data.get("bg_color", default_bg)
        head_col = self.node.custom_data.get("header_color", default_head)
        txt_col = self.node.custom_data.get("text_color", COLORS["text"])
        head_txt_col = self.node.custom_data.get("header_text_color", "white")

        emo = self.node.custom_data.get("emotion")
        title_text = self.e_title.get() or "Заголовок"
        if emo and self.node.node_type == "story" and not title_text.startswith("#"):
            title_text = f"{title_text} ({emo})"
        self.preview_box.config(bg=bg_col)
        self.preview_head.config(bg=head_col)
        self.lbl_head_title.config(text=title_text, bg=head_col, fg=head_txt_col)
        self.lbl_body_preview.config(bg=bg_col, fg=txt_col)

    def _apply_preset(self, b: str, h: str) -> None:
        self.node.custom_data["bg_color"] = b
        self.node.custom_data["header_color"] = h
        self._update_preview()
        if hasattr(self.editor, "redraw"):
            self.editor.redraw()

    def _pick_bg(self) -> None:
        default_bg = COLORS.get(f"node_{self.node.node_type}", COLORS["node_story"])
        cur = self.node.custom_data.get("bg_color", default_bg)
        col = colorchooser.askcolor(color=cur, title="Цвет фона блока", parent=self.dialog)
        if col and col[1]:
            self.node.custom_data["bg_color"] = col[1]
            self.node.custom_data["header_color"] = darken_color(col[1], 0.75)
            self._update_preview()
            if hasattr(self.editor, "redraw"):
                self.editor.redraw()

    def _pick_header_bg(self) -> None:
        default_head = COLORS.get(f"header_{self.node.node_type}", COLORS["header_story"])
        cur = self.node.custom_data.get("header_color", default_head)
        col = colorchooser.askcolor(color=cur, title="Цвет шапки блока", parent=self.dialog)
        if col and col[1]:
            self.node.custom_data["header_color"] = col[1]
            self._update_preview()
            if hasattr(self.editor, "redraw"):
                self.editor.redraw()

    def _pick_header_txt(self) -> None:
        cur = self.node.custom_data.get("header_text_color", "white")
        col = colorchooser.askcolor(color=cur, title="Цвет текста заголовка", parent=self.dialog)
        if col and col[1]:
            self.node.custom_data["header_text_color"] = col[1]
            self._update_preview()
            if hasattr(self.editor, "redraw"):
                self.editor.redraw()

    def _pick_text_color(self) -> None:
        cur = self.node.custom_data.get("text_color", COLORS["text"])
        col = colorchooser.askcolor(color=cur, title="Цвет основного текста", parent=self.dialog)
        if col and col[1]:
            self.node.custom_data["text_color"] = col[1]
            self._update_preview()
            if hasattr(self.editor, "redraw"):
                self.editor.redraw()

    def _reset_colors(self) -> None:
        self.node.custom_data.pop("bg_color", None)
        self.node.custom_data.pop("header_color", None)
        self.node.custom_data.pop("text_color", None)
        self.node.custom_data.pop("header_text_color", None)
        self._update_preview()
        if hasattr(self.editor, "redraw"):
            self.editor.redraw()

    def _highlight_selected_word(self) -> None:
        try:
            sel_start = self.t_content.index(tk.SEL_FIRST)
            sel_end = self.t_content.index(tk.SEL_LAST)
            fragment = self.t_content.get(sel_start, sel_end)
            if not fragment:
                return

            color = colorchooser.askcolor(title=f"Цвет для '{fragment}'", parent=self.dialog)
            if color and color[1]:
                if "highlights" not in self.node.custom_data:
                    self.node.custom_data["highlights"] = {}
                self.node.custom_data["highlights"][fragment] = color[1]
                if hasattr(self.editor, "redraw"):
                    self.editor.redraw()
        except tk.TclError:
            messagebox.showwarning("Внимание", "Сначала выделите фрагмент в тексте мышкой!", parent=self.dialog)

    def _clear_highlights(self) -> None:
        if "highlights" in self.node.custom_data:
            self.node.custom_data["highlights"] = {}
            if hasattr(self.editor, "redraw"):
                self.editor.redraw()

    def _auto_save(self, event: Any = None) -> None:
        self.node.title = self.e_title.get()
        self.node.content = self.t_content.get("1.0", tk.END).strip()
        self.node.calculate_size()
        self._update_preview()
        if hasattr(self.editor, "redraw"):
            self.editor.redraw()

    def _save_and_close(self) -> None:
        self.node.title = self.e_title.get()
        self.node.content = self.t_content.get("1.0", tk.END).strip()

        if hasattr(self.editor, "plugin_manager"):
            self.editor.plugin_manager.notify("node_edit_save", {"node": self.node})

        self.node.calculate_size()
        if hasattr(self.editor, "redraw"):
            self.editor.redraw()
        if self.on_save:
            self.on_save()

        self.dialog.destroy()

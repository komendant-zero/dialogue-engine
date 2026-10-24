"""
Dialogue Engine - Character Manager Modal Dialog.
Минималистичное и наглядное окно управления базой персонажей, палитрой цветов,
аватарами, пресетами эмоций и пакетным переименованием реплик.
"""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from core.characters import DEFAULT_CHARACTER_PALETTE, DEFAULT_EMOTIONS, CharacterManager
from core.models import CharacterData
from core.sprites import SpriteResolver
from ui.theme import BTN_ACTION_STYLE, BTN_NORMAL_STYLE, COLORS, darken_color

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class CharacterManagerDialog:
    """Модальное окно менеджера персонажей."""

    def __init__(
        self,
        parent: tk.Widget,
        editor: Any,
        on_change: Optional[Callable[[], None]] = None
    ):
        self.parent = parent
        self.editor = editor
        self.on_change = on_change

        # Менеджер персонажей редактора
        self.manager: CharacterManager = getattr(editor, "character_manager", None)
        if self.manager is None:
            self.manager = CharacterManager()
            self.editor.character_manager = self.manager

        # Авто-сканирование при первом открытии, если база пуста, но в сценарии уже есть персонажи
        if not self.manager.list() and hasattr(self.editor, "nodes"):
            self.manager.scan_from_nodes(self.editor.nodes)

        self._selected_character: Optional[CharacterData] = None
        self._avatar_photo: Optional[Any] = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("👥 База персонажей (Character Manager)")
        self.dialog.geometry("780x640")
        self.dialog.minsize(680, 520)
        self.dialog.configure(bg=COLORS["bg"])
        self.dialog.transient(parent)
        self.dialog.attributes("-topmost", True)

        self._build_ui()
        self._refresh_character_list()

        # Выбираем первого персонажа, если есть
        if self.manager.list():
            self._select_character_by_name(self.manager.list()[0].name)

    def _build_ui(self) -> None:
        # ── 1. Верхняя панель заголовка ──
        header_frame = tk.Frame(self.dialog, bg="#252526", height=50)
        header_frame.pack(side=tk.TOP, fill=tk.X)
        header_frame.pack_propagate(False)

        lbl_title = tk.Label(
            header_frame,
            text="👥 База персонажей истории",
            bg="#252526",
            fg="white",
            font=("Segoe UI", 12, "bold")
        )
        lbl_title.pack(side=tk.LEFT, padx=15, pady=4)

        lbl_sub = tk.Label(
            header_frame,
            text="Цвета реплик, пресеты эмоций, аватары и автоподстановка",
            bg="#252526",
            fg="#888888",
            font=("Segoe UI", 9)
        )
        lbl_sub.pack(side=tk.LEFT, padx=5, pady=6)

        # ── 2. Основная рабочая область (2 колонки) ──
        main_paned = tk.PanedWindow(self.dialog, orient=tk.HORIZONTAL, bg=COLORS["bg"], bd=0, sashwidth=4)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Левая колонка: Список персонажей и действия со списком
        left_frame = tk.Frame(main_paned, bg="#252526", width=260)
        main_paned.add(left_frame, minsize=220)

        list_header = tk.Frame(left_frame, bg="#252526")
        list_header.pack(fill=tk.X, padx=10, pady=(10, 5))

        tk.Label(
            list_header,
            text="Герои сценария",
            bg="#252526",
            fg="white",
            font=("Segoe UI", 10, "bold")
        ).pack(side=tk.LEFT)

        self.lbl_count = tk.Label(
            list_header,
            text="0 героев",
            bg="#252526",
            fg="#888888",
            font=("Segoe UI", 8)
        )
        self.lbl_count.pack(side=tk.RIGHT)

        # Список персонажей
        list_container = tk.Frame(left_frame, bg="#252526")
        list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.char_listbox = tk.Listbox(
            list_container,
            bg="#1e1e1e",
            fg="white",
            selectbackground="#094771",
            selectforeground="white",
            highlightthickness=0,
            bd=1,
            relief="solid",
            font=("Segoe UI", 10),
            activestyle="none"
        )
        scrollbar = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.char_listbox.yview)
        self.char_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.char_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.char_listbox.bind("<<ListboxSelected>>", self._on_list_select)

        # Кнопки под списком
        btn_list_frame = tk.Frame(left_frame, bg="#252526")
        btn_list_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(
            btn_list_frame,
            text="➕ Добавить",
            command=self._add_new_character,
            bg="#2ecc71",
            fg="white",
            activebackground="#27ae60",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=4,
            cursor="hand2"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        tk.Button(
            btn_list_frame,
            text="🗑️ Удалить",
            command=self._delete_character,
            bg="#3a3a3a",
            fg="#e74c3c",
            activebackground="#502a2a",
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=(2, 0))

        # Кнопка сканирования сценария
        tk.Button(
            left_frame,
            text="🔍 Сканировать из сценария",
            command=self._scan_from_scenario,
            bg="#2d4a57",
            fg="white",
            activebackground="#34596b",
            relief="flat",
            font=("Segoe UI", 9),
            pady=4,
            cursor="hand2"
        ).pack(fill=tk.X, padx=10, pady=(2, 10))

        # Правая колонка: Карточка персонажа и настройки
        self.right_frame = tk.Frame(main_paned, bg="#1e1e1e")
        main_paned.add(self.right_frame, minsize=400)

        self._build_character_editor_panel()

        # ── 3. Нижняя панель состояния и закрытия ──
        bottom_frame = tk.Frame(self.dialog, bg=COLORS["bg"])
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))

        self.lbl_status = tk.Label(
            bottom_frame,
            text="Готово к работе",
            bg=COLORS["bg"],
            fg="#aaaaaa",
            font=("Segoe UI", 8)
        )
        self.lbl_status.pack(side=tk.LEFT, padx=5)

        tk.Button(
            bottom_frame,
            text="✓ Сохранить и Закрыть",
            command=self._close_dialog,
            bg=COLORS["header_story"],
            fg="white",
            activebackground="#3a70b2",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=5,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=5)

    def _build_character_editor_panel(self) -> None:
        """Создает форму редактирования выбранного персонажа."""
        # Заглушка, когда никто не выбран
        self.empty_card = tk.Frame(self.right_frame, bg="#1e1e1e")
        tk.Label(
            self.empty_card,
            text="👤 Персонаж не выбран\n\nВыберите персонажа из списка слева\nили нажмите «➕ Добавить», чтобы создать нового.",
            bg="#1e1e1e",
            fg="#777777",
            font=("Segoe UI", 10),
            justify=tk.CENTER
        ).pack(expand=True, pady=100)
        self.empty_card.pack(fill=tk.BOTH, expand=True)

        # Контейнер формы
        self.edit_card = tk.Frame(self.right_frame, bg="#1e1e1e")

        # 1. Профиль персонажа: Аватар + Имя + Роль
        profile_box = tk.Frame(self.edit_card, bg="#252526", bd=1, relief="solid")
        profile_box.pack(fill=tk.X, pady=(0, 10), padx=5)

        # Левая часть профиля: Аватар
        avatar_col = tk.Frame(profile_box, bg="#252526", padx=10, pady=10)
        avatar_col.pack(side=tk.LEFT)

        self.avatar_canvas = tk.Canvas(avatar_col, width=64, height=64, bg="#1e1e1e", highlightthickness=1, highlightbackground="#3a3a3a")
        self.avatar_canvas.pack(side=tk.TOP)

        avatar_btn_row = tk.Frame(avatar_col, bg="#252526")
        avatar_btn_row.pack(side=tk.TOP, pady=(4, 0))

        tk.Button(
            avatar_btn_row, text="Аватар...", command=self._pick_avatar,
            bg="#333", fg="white", relief="flat", font=("Segoe UI", 7), padx=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=1)

        tk.Button(
            avatar_btn_row, text="✕", command=self._clear_avatar,
            bg="#333", fg="#e74c3c", relief="flat", font=("Segoe UI", 7), padx=4, cursor="hand2"
        ).pack(side=tk.LEFT, padx=1)

        # Правая часть профиля: Поля ввода имени и описания
        meta_col = tk.Frame(profile_box, bg="#252526", padx=5, pady=8)
        meta_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(meta_col, text="Имя персонажа:", bg="#252526", fg="#cccccc", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.e_name = tk.Entry(meta_col, bg="#333333", fg="white", insertbackground="white", font=("Segoe UI", 10, "bold"), bd=1, relief="solid")
        self.e_name.pack(fill=tk.X, pady=(2, 4))
        self.e_name.bind("<KeyRelease>", self._on_field_changed)

        tk.Label(meta_col, text="Заметки / роль (опционально):", bg="#252526", fg="#888888", font=("Segoe UI", 8)).pack(anchor="w")
        self.e_desc = tk.Entry(meta_col, bg="#333333", fg="#dddddd", insertbackground="white", font=("Segoe UI", 9), bd=1, relief="solid")
        self.e_desc.pack(fill=tk.X, pady=(2, 0))
        self.e_desc.bind("<KeyRelease>", self._on_field_changed)

        # 2. Блок Палитры Цветов
        color_frame = tk.LabelFrame(
            self.edit_card,
            text="🎨 Палитра и цвет реплики",
            bg="#1e1e1e",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=8
        )
        color_frame.pack(fill=tk.X, pady=5, padx=5)

        # Верхняя строка выбора цвета
        color_top_row = tk.Frame(color_frame, bg="#1e1e1e")
        color_top_row.pack(fill=tk.X, pady=(0, 6))

        self.color_swatch = tk.Frame(color_top_row, width=28, height=28, bg="#ffffff", relief="solid", bd=1)
        self.color_swatch.pack(side=tk.LEFT, padx=(0, 8))
        self.color_swatch.pack_propagate(False)

        self.lbl_color_hex = tk.Label(
            color_top_row, text="#FFFFFF", bg="#1e1e1e", fg="white", font=("Consolas", 10, "bold")
        )
        self.lbl_color_hex.pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            color_top_row,
            text="🎨 Выбрать цвет...",
            command=self._pick_color,
            bg="#2c3e50",
            fg="white",
            relief="flat",
            font=("Segoe UI", 8),
            padx=8,
            cursor="hand2"
        ).pack(side=tk.LEFT)

        # Быстрые пресеты палитры
        palette_lbl = tk.Label(
            color_frame,
            text="Быстрые пресеты оттенков:",
            bg="#1e1e1e",
            fg="#888888",
            font=("Segoe UI", 8)
        )
        palette_lbl.pack(anchor="w", pady=(2, 4))

        palette_row = tk.Frame(color_frame, bg="#1e1e1e")
        palette_row.pack(fill=tk.X)

        for name, hex_val in DEFAULT_CHARACTER_PALETTE[:9]:
            btn = tk.Button(
                palette_row,
                bg=hex_val,
                activebackground=hex_val,
                width=2,
                height=1,
                relief="flat",
                bd=1,
                cursor="hand2",
                command=lambda val=hex_val: self._apply_color_preset(val)
            )
            btn.pack(side=tk.LEFT, padx=2)

        # 3. Блок Пресетов Эмоций
        emotions_frame = tk.LabelFrame(
            self.edit_card,
            text="🎭 Пресеты эмоций персонажа",
            bg="#1e1e1e",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=8
        )
        emotions_frame.pack(fill=tk.X, pady=5, padx=5)

        tk.Label(
            emotions_frame,
            text="Список эмоций для быстрой вставки (через запятую):",
            bg="#1e1e1e",
            fg="#aaaaaa",
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        emo_input_row = tk.Frame(emotions_frame, bg="#1e1e1e")
        emo_input_row.pack(fill=tk.X, pady=(2, 6))

        self.e_emotions = tk.Entry(
            emo_input_row, bg="#333333", fg="white", insertbackground="white", font=("Segoe UI", 9), bd=1, relief="solid"
        )
        self.e_emotions.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.e_emotions.bind("<KeyRelease>", self._on_field_changed)

        tk.Button(
            emo_input_row,
            text="📁 Из спрайтов",
            command=self._sync_emotions_from_sprites,
            bg="#2d4a57",
            fg="white",
            relief="flat",
            font=("Segoe UI", 8),
            padx=6,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=(4, 0))

        tk.Button(
            emo_input_row,
            text="+ Стандартные",
            command=self._set_default_emotions,
            bg="#333333",
            fg="#dddddd",
            relief="flat",
            font=("Segoe UI", 8),
            padx=6,
            cursor="hand2"
        ).pack(side=tk.RIGHT)

        # Чипы предпросмотра эмоций
        self.emo_chips_frame = tk.Frame(emotions_frame, bg="#1e1e1e")
        self.emo_chips_frame.pack(fill=tk.X)

        # 4. Блок Пакетных Действий над Сценарием
        actions_frame = tk.LabelFrame(
            self.edit_card,
            text="⚡ Пакетные действия со сценарием",
            bg="#1e1e1e",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=8
        )
        actions_frame.pack(fill=tk.X, pady=5, padx=5)

        tk.Button(
            actions_frame,
            text="🔁 Заменить имя во всем сценарии (Batch Rename)",
            command=self._do_batch_rename,
            bg="#2d4a57",
            fg="white",
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=3,
            cursor="hand2"
        ).pack(fill=tk.X, pady=2)

        tk.Button(
            actions_frame,
            text="🎨 Окрасить все реплики персонажа на холсте",
            command=self._apply_color_to_canvas_nodes,
            bg="#34495e",
            fg="white",
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=3,
            cursor="hand2"
        ).pack(fill=tk.X, pady=2)

    # ── Логика работы со списком ──

    def _refresh_character_list(self) -> None:
        """Перерисовывает список персонажей слева."""
        self.char_listbox.delete(0, tk.END)
        chars = self.manager.list()
        nodes = getattr(self.editor, "nodes", [])

        for ch in chars:
            count = self.manager.count_repliques(ch.name, nodes)
            rep_str = f"({count} репл.)" if count else ""
            self.char_listbox.insert(tk.END, f"●  {ch.name}  {rep_str}")

        count_str = f"{len(chars)} героев" if len(chars) != 1 else "1 герой"
        self.lbl_count.config(text=count_str)

    def _on_list_select(self, event: Any = None) -> None:
        sel = self.char_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        chars = self.manager.list()
        if 0 <= idx < len(chars):
            self._select_character(chars[idx])

    def _select_character_by_name(self, name: str) -> None:
        chars = self.manager.list()
        for idx, ch in enumerate(chars):
            if ch.name.strip().lower() == name.strip().lower():
                self.char_listbox.selection_clear(0, tk.END)
                self.char_listbox.selection_set(idx)
                self.char_listbox.activate(idx)
                self._select_character(ch)
                break

    def _select_character(self, character: CharacterData) -> None:
        self._selected_character = character

        # Переключаем отображение карточки
        self.empty_card.pack_forget()
        self.edit_card.pack(fill=tk.BOTH, expand=True)

        # Заполняем поля
        self.e_name.delete(0, tk.END)
        self.e_name.insert(0, character.name)

        self.e_desc.delete(0, tk.END)
        self.e_desc.insert(0, character.description or "")

        self._update_color_display(character.color or "#ffffff")

        self.e_emotions.delete(0, tk.END)
        if character.emotions:
            self.e_emotions.insert(0, ", ".join(character.emotions))

        self._refresh_emotion_chips()
        self._render_avatar_preview()

    def _update_color_display(self, hex_val: str) -> None:
        self.color_swatch.config(bg=hex_val)
        self.lbl_color_hex.config(text=hex_val.upper())

    def _render_avatar_preview(self) -> None:
        """Отрисовывает аватар или круг с первой буквой имени."""
        self.avatar_canvas.delete("all")
        if not self._selected_character:
            return

        avatar_path = self._selected_character.avatar_path
        color = self._selected_character.color or "#0080ff"
        initial = (self._selected_character.name[:1] or "?").upper()

        if avatar_path and os.path.exists(avatar_path) and HAS_PIL:
            try:
                img = Image.open(avatar_path)
                img = img.resize((62, 62), Image.Resampling.LANCZOS)
                self._avatar_photo = ImageTk.PhotoImage(img)
                self.avatar_canvas.create_image(32, 32, image=self._avatar_photo)
                return
            except Exception:
                pass

        # Отрисовка стилизованного круга-монограммы
        self.avatar_canvas.create_oval(4, 4, 60, 60, fill=darken_color(color, 0.4), outline=color, width=2)
        self.avatar_canvas.create_text(
            32, 32, text=initial, fill=color, font=("Segoe UI", 16, "bold")
        )

    def _refresh_emotion_chips(self) -> None:
        """Обновляет кликабельные теги эмоций под полем ввода."""
        for child in self.emo_chips_frame.winfo_children():
            child.destroy()

        if not self._selected_character or not self._selected_character.emotions:
            return

        for emo in self._selected_character.emotions[:6]:
            lbl = tk.Label(
                self.emo_chips_frame,
                text=f"#{emo}",
                bg="#2a2a2a",
                fg="#bbbbbb",
                font=("Segoe UI", 8),
                padx=5,
                pady=1
            )
            lbl.pack(side=tk.LEFT, padx=2, pady=2)

    # ── Действия с текущим персонажем ──

    def _on_field_changed(self, event: Any = None) -> None:
        if not self._selected_character:
            return

        new_name = self.e_name.get().strip()
        new_desc = self.e_desc.get().strip()
        raw_emos = [e.strip() for e in self.e_emotions.get().split(",") if e.strip()]

        if new_name:
            old_name = self._selected_character.name
            self._selected_character.name = new_name
            self._selected_character.description = new_desc
            self._selected_character.emotions = raw_emos
            self.manager.update(old_name, self._selected_character)

            self._refresh_character_list()
            self._render_avatar_preview()
            self._refresh_emotion_chips()
            self._notify_editor()

    def _apply_color_preset(self, hex_val: str) -> None:
        if not self._selected_character:
            return
        self._selected_character.color = hex_val
        self._selected_character.header_text_color = hex_val
        self._update_color_display(hex_val)
        self._render_avatar_preview()
        self._notify_editor()
        self._set_status(f"Цвет установлен: {hex_val}")

    def _pick_color(self) -> None:
        if not self._selected_character:
            return
        cur_color = self._selected_character.color or "#ffffff"
        chosen = colorchooser.askcolor(color=cur_color, title="Выбор цвета персонажа", parent=self.dialog)
        if chosen and chosen[1]:
            self._apply_color_preset(chosen[1])

    def _pick_avatar(self) -> None:
        if not self._selected_character:
            return
        filetypes = [("Изображения", "*.png;*.jpg;*.jpeg;*.webp;*.gif"), ("Все файлы", "*.*")]
        path = filedialog.askopenfilename(title="Выберите аватар или спрайт героя", filetypes=filetypes, parent=self.dialog)
        if path:
            self._selected_character.avatar_path = path
            self._render_avatar_preview()
            self._notify_editor()
            self._set_status("Аватар успешно установлен")

    def _clear_avatar(self) -> None:
        if not self._selected_character:
            return
        self._selected_character.avatar_path = ""
        self._render_avatar_preview()
        self._notify_editor()
        self._set_status("Аватар сброшен")

    def _sync_emotions_from_sprites(self) -> None:
        if not self._selected_character:
            return
        sprites = SpriteResolver.find_all_character_sprites(self._selected_character.name, editor=self.editor)
        if not sprites:
            messagebox.showinfo("Спрайты", f"В папке спрайтов не найдено файлов для «{self._selected_character.name}».", parent=self.dialog)
            return

        labels = [lbl for lbl, _ in sprites]
        self._selected_character.emotions = labels
        self.e_emotions.delete(0, tk.END)
        self.e_emotions.insert(0, ", ".join(labels))
        self._refresh_emotion_chips()
        self._notify_editor()
        self._set_status(f"✓ Загружено {len(labels)} поз/эмоций из файлов спрайтов")

    def _set_default_emotions(self) -> None:
        if not self._selected_character:
            return
        self._selected_character.emotions = list(DEFAULT_EMOTIONS)
        self.e_emotions.delete(0, tk.END)
        self.e_emotions.insert(0, ", ".join(DEFAULT_EMOTIONS))
        self._refresh_emotion_chips()
        self._notify_editor()
        self._set_status("Добавлены стандартные эмоции новелл")

    # ── Глобальные действия: Добавить, Удалить, Сканировать, Переименовать ──

    def _add_new_character(self) -> None:
        base_name = "Новый персонаж"
        name = base_name
        idx = 2
        while self.manager.get(name) is not None:
            name = f"{base_name} {idx}"
            idx += 1

        # Выбираем случайный или циклический приятный цвет
        palette_idx = len(self.manager.list()) % len(DEFAULT_CHARACTER_PALETTE)
        preset_color = DEFAULT_CHARACTER_PALETTE[palette_idx][1]

        new_char = CharacterData(
            name=name,
            color=preset_color,
            emotions=list(DEFAULT_EMOTIONS)
        )
        self.manager.add(new_char)
        self._refresh_character_list()
        self._select_character_by_name(name)
        self.e_name.focus_set()
        self.e_name.select_range(0, tk.END)
        self._notify_editor()
        self._set_status(f"Создан герой «{name}»")

    def _delete_character(self) -> None:
        if not self._selected_character:
            return

        name = self._selected_character.name
        count = self.manager.count_repliques(name, getattr(self.editor, "nodes", []))
        warning = f"Удалить персонажа «{name}» из базы?"
        if count > 0:
            warning += f"\n\nВнимание: в сценарии найдено {count} реплик этого персонажа (сами блоки удалены не будут)."

        if messagebox.askyesno("Удаление персонажа", warning, parent=self.dialog):
            self.manager.delete(name)
            self._selected_character = None
            self._refresh_character_list()
            chars = self.manager.list()
            if chars:
                self._select_character(chars[0])
            else:
                self.edit_card.pack_forget()
                self.empty_card.pack(fill=tk.BOTH, expand=True)
            self._notify_editor()
            self._set_status(f"Персонаж «{name}» удален")

    def _scan_from_scenario(self) -> None:
        nodes = getattr(self.editor, "nodes", [])
        if not nodes:
            messagebox.showinfo("Сканирование", "В текущем сценарии пока нет блоков.", parent=self.dialog)
            return

        added = self.manager.scan_from_nodes(nodes)
        self._refresh_character_list()
        if added:
            self._select_character(added[0])
            msg = f"Найдено и добавлено новых героев: {len(added)} ({', '.join(c.name for c in added)})"
            self._set_status(msg)
            messagebox.showinfo("Сканирование завершено", msg, parent=self.dialog)
        else:
            self._set_status("Все персонажи из сценария уже присутствуют в базе")
            messagebox.showinfo("Сканирование завершено", "Новых персонажей в репликах не обнаружено. Все персонажи уже в базе!", parent=self.dialog)

    def _do_batch_rename(self) -> None:
        if not self._selected_character:
            return

        old_name = self._selected_character.name
        current_input = self.e_name.get().strip()
        nodes = getattr(self.editor, "nodes", [])
        count = self.manager.count_repliques(old_name, nodes)

        if count == 0:
            messagebox.showinfo("Пакетное переименование", f"В сценарии не найдено реплик с именем «{old_name}».", parent=self.dialog)
            return

        # Запрашиваем подтверждение
        confirm = messagebox.askyesno(
            "Пакетное переименование",
            f"Заменить имя «{old_name}» на «{current_input}» во всех {count} репликах сценария?",
            parent=self.dialog
        )
        if confirm:
            updated = self.manager.batch_rename(old_name, current_input, nodes)
            if hasattr(self.editor, "redraw"):
                self.editor.redraw()
            if hasattr(self.editor, "set_dirty"):
                self.editor.set_dirty(True)
            self._refresh_character_list()
            self._select_character_by_name(current_input)
            self._set_status(f"✓ Успешно обновлено {updated} блоков в сценарии")
            messagebox.showinfo("Готово", f"Имя персонажа успешно обновлено в {updated} блоках!", parent=self.dialog)

    def _apply_color_to_canvas_nodes(self) -> None:
        if not self._selected_character:
            return

        name = self._selected_character.name
        color = self._selected_character.color or "#ffffff"
        nodes = getattr(self.editor, "nodes", [])

        count = self.manager.apply_color_to_nodes(name, color, nodes)
        if hasattr(self.editor, "redraw"):
            self.editor.redraw()
        if hasattr(self.editor, "set_dirty"):
            self.editor.set_dirty(True)

        self._set_status(f"✓ Окрашено {count} блоков персонажа «{name}»")
        messagebox.showinfo("Окрашивание блоков", f"Цвет {color} применен к {count} репликам героя «{name}» на холсте!", parent=self.dialog)

    def _notify_editor(self) -> None:
        if hasattr(self.editor, "set_dirty"):
            self.editor.set_dirty(True)
        if self.on_change:
            self.on_change()

    def _set_status(self, text: str) -> None:
        self.lbl_status.config(text=text)

    def _close_dialog(self) -> None:
        self._notify_editor()
        if hasattr(self.editor, "redraw"):
            self.editor.redraw()
        self.dialog.destroy()

"""
Dialogue Engine - Hotkey Settings Dialog.
Диалоговое окно для удобного назначения и изменения горячих клавиш редактора.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable

from core.hotkeys import (
    ACTION_METADATA,
    DEFAULT_HOTKEYS,
    HotkeyManager,
    format_hotkey_from_event,
)
from ui.theme import COLORS, BTN_ACTION_STYLE, BTN_NORMAL_STYLE


class KeyCaptureDialog:
    """Модальное окно для интерактивного перехвата и назначения новой комбинации клавиш."""

    def __init__(
        self,
        parent: tk.Widget,
        action_id: str,
        current_key: str,
        existing_hotkeys: dict[str, str],
        on_assigned: Callable[[str], None]
    ):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Назначение горячей клавиши")
        self.dialog.geometry("460x260")
        self.dialog.configure(bg=COLORS["bg"])
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)

        self.action_id = action_id
        self.current_key = current_key
        self.existing_hotkeys = existing_hotkeys
        self.on_assigned = on_assigned
        self.captured_key: str | None = None

        meta = ACTION_METADATA.get(action_id, {})
        title = meta.get("title", action_id)
        desc = meta.get("description", "")

        # Центрирование относительно родителя
        self.dialog.update_idletasks()
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() // 2) - 230
            py = parent.winfo_rooty() + (parent.winfo_height() // 2) - 130
            self.dialog.geometry(f"+{max(50, px)}+{max(50, py)}")
        except Exception:
            pass

        # Верхняя информационная секция
        tk.Label(
            self.dialog,
            text=f"Действие: {title}",
            bg=COLORS["bg"],
            fg="white",
            font=("Segoe UI", 11, "bold")
        ).pack(pady=(16, 2))

        if desc:
            tk.Label(
                self.dialog,
                text=desc,
                bg=COLORS["bg"],
                fg="#aaaaaa",
                font=("Segoe UI", 8)
            ).pack(pady=(0, 8))

        # Большой интерактивный бейдж клавиши
        self.badge_frame = tk.Frame(
            self.dialog,
            bg="#252526",
            padx=18,
            pady=12,
            highlightthickness=1,
            highlightbackground="#4a90e2"
        )
        self.badge_frame.pack(fill=tk.X, padx=30, pady=8)

        display_text = current_key if current_key else "Нажмите клавишу или сочетание..."
        self.lbl_key = tk.Label(
            self.badge_frame,
            text=display_text,
            bg="#252526",
            fg="#4a90e2" if current_key else "#888888",
            font=("Segoe UI", 13, "bold")
        )
        self.lbl_key.pack()

        # Пояснение
        tk.Label(
            self.dialog,
            text="Поддерживаются Ctrl, Shift, Alt, цифры, буквы (любая раскладка).\nEscape — отмена, Backspace — очистить.",
            bg=COLORS["bg"],
            fg="#777777",
            font=("Segoe UI", 8),
            justify="center"
        ).pack(pady=4)

        # Нижние кнопки
        btn_box = tk.Frame(self.dialog, bg=COLORS["bg"])
        btn_box.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=12)

        tk.Button(
            btn_box,
            text="❌ Очистить",
            command=self.clear_hotkey,
            bg="#5a2020",
            fg="white",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_box,
            text="Отмена",
            command=self.dialog.destroy,
            bg="#333333",
            fg="white",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
            font=("Segoe UI", 9)
        ).pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_save = tk.Button(
            btn_box,
            text="✓ Применить",
            command=self.apply_captured,
            bg="#1f618d",
            fg="white",
            relief="flat",
            padx=14,
            pady=3,
            state=tk.DISABLED,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        self.btn_save.pack(side=tk.RIGHT)

        # Перехват нажатия клавиш
        self.dialog.bind("<KeyPress>", self.on_key_press)
        self.dialog.focus_force()

    def on_key_press(self, event: Any) -> str:
        if event.keysym == "Escape":
            self.dialog.destroy()
            return "break"

        # BackSpace без модификаторов очищает клавишу
        if event.keysym in ("BackSpace", "Backspace") and not (event.state & (4 | 8 | 0x20000)):
            self.clear_hotkey()
            return "break"

        formatted = format_hotkey_from_event(event)
        if formatted:
            self.captured_key = formatted
            self.lbl_key.config(text=formatted, fg="#00ff00")
            self.btn_save.config(state=tk.NORMAL)
            self.apply_captured()
            return "break"
        else:
            # Превью зажатых модификаторов (Ctrl + ...)
            mods: list[str] = []
            if event.state & 4 or event.keysym in ("Control_L", "Control_R"):
                mods.append("Ctrl")
            if event.state & 8 or event.state & 0x20000 or event.keysym in ("Alt_L", "Alt_R"):
                mods.append("Alt")
            if event.state & 1 or event.keysym in ("Shift_L", "Shift_R"):
                mods.append("Shift")
            if mods:
                self.lbl_key.config(text=f"{' + '.join(mods)} + ...", fg="#ffcc00")

        return "break"

    def clear_hotkey(self) -> None:
        self.on_assigned("")
        self.dialog.destroy()

    def apply_captured(self) -> None:
        if not self.captured_key:
            return

        # Проверка конфликта с другим действием
        conflicts = [
            (aid, key) for aid, key in self.existing_hotkeys.items()
            if aid != self.action_id and key.lower() == self.captured_key.lower()
        ]
        if conflicts:
            conflict_aid, _ = conflicts[0]
            c_meta = ACTION_METADATA.get(conflict_aid, {})
            c_title = c_meta.get("title", conflict_aid)
            resp = messagebox.askyesno(
                "Конфликт клавиш",
                f"Сочетание '{self.captured_key}' уже назначено для:\n«{c_title}»\n\nПереназначить на текущее действие?",
                parent=self.dialog
            )
            if not resp:
                return
            self.existing_hotkeys[conflict_aid] = ""

        self.on_assigned(self.captured_key)
        self.dialog.destroy()


class HotkeySettingsDialog:
    """Главное окно управления настройками горячих клавиш редактора."""

    def __init__(self, parent: tk.Widget, editor: Any):
        self.parent = parent
        self.editor = editor
        self.hotkey_manager: HotkeyManager = editor.hotkey_manager

        # Локальная рабочая копия хоткеев для возможности отмены
        self.working_hotkeys: dict[str, str] = dict(self.hotkey_manager.hotkeys)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Настройки горячих клавиш")
        self.dialog.geometry("720x560")
        self.dialog.minsize(580, 420)
        self.dialog.configure(bg=COLORS["bg"])
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Центрирование
        self.dialog.update_idletasks()
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() // 2) - 360
            py = parent.winfo_rooty() + (parent.winfo_height() // 2) - 280
            self.dialog.geometry(f"+{max(50, px)}+{max(50, py)}")
        except Exception:
            pass

        self._build_ui()
        self._populate_tree()

    def _build_ui(self) -> None:
        top_frame = tk.Frame(self.dialog, bg=COLORS["bg"])
        top_frame.pack(fill=tk.X, padx=16, pady=(12, 6))

        tk.Label(
            top_frame,
            text="⌨️ Настройка сочетаний клавиш",
            bg=COLORS["bg"],
            fg="white",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w")

        tk.Label(
            top_frame,
            text="Дважды кликните по строке действия (или выберите и нажмите 'Изменить клавишу'), чтобы назначить свой хоткей.",
            bg=COLORS["bg"],
            fg="#aaaaaa",
            font=("Segoe UI", 8)
        ).pack(anchor="w", pady=(2, 6))

        # Поле поиска
        search_frame = tk.Frame(top_frame, bg=COLORS["bg"])
        search_frame.pack(fill=tk.X, pady=(2, 4))

        tk.Label(
            search_frame,
            text="🔍 Поиск:",
            bg=COLORS["bg"],
            fg="#cccccc",
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.e_search = tk.Entry(
            search_frame,
            bg="#333",
            fg="white",
            insertbackground="white",
            font=("Segoe UI", 9)
        )
        self.e_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.e_search.bind("<KeyRelease>", lambda e: self._populate_tree())

        # Центральная таблица действий
        table_frame = tk.Frame(self.dialog, bg=COLORS["bg"])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # Стилизация ttk.Treeview под тёмную тему
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Hotkeys.Treeview",
            background="#252526",
            foreground="#e0e0e0",
            fieldbackground="#252526",
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0
        )
        style.configure(
            "Hotkeys.Treeview.Heading",
            background="#333333",
            foreground="white",
            relief="flat",
            font=("Segoe UI", 9, "bold")
        )
        style.map(
            "Hotkeys.Treeview",
            background=[("selected", "#094771")],
            foreground=[("selected", "white")]
        )

        columns = ("title", "category", "hotkey")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="Hotkeys.Treeview",
            selectmode="browse"
        )
        self.tree.heading("title", text="Действие")
        self.tree.heading("category", text="Категория")
        self.tree.heading("hotkey", text="Сочетание клавиш")

        self.tree.column("title", width=260, minwidth=180)
        self.tree.column("category", width=140, minwidth=100)
        self.tree.column("hotkey", width=160, minwidth=110, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self.tree.bind("<Return>", lambda e: self.edit_selected())

        # Кнопки управления выбранным действием
        mid_btns = tk.Frame(self.dialog, bg=COLORS["bg"])
        mid_btns.pack(fill=tk.X, padx=16, pady=6)

        tk.Button(
            mid_btns,
            text="⌨️ Изменить клавишу",
            command=self.edit_selected,
            **BTN_ACTION_STYLE
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            mid_btns,
            text="❌ Очистить клавишу",
            command=self.clear_selected,
            **BTN_NORMAL_STYLE
        ).pack(side=tk.LEFT)

        # Нижняя панель действий
        bottom_frame = tk.Frame(self.dialog, bg=COLORS["bg"])
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(8, 14))

        tk.Button(
            bottom_frame,
            text="🔄 Сбросить по умолчанию",
            command=self.reset_defaults,
            bg="#374151",
            fg="#f3f4f6",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT)

        tk.Button(
            bottom_frame,
            text="Отмена",
            command=self.dialog.destroy,
            bg="#333333",
            fg="white",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 9)
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            bottom_frame,
            text="💾 Применить и сохранить",
            command=self.save_and_apply,
            bg="#16a34a",
            fg="white",
            relief="flat",
            padx=14,
            pady=4,
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        ).pack(side=tk.RIGHT)

    def _populate_tree(self) -> None:
        """Заполняет список действий с учётом фильтра поиска."""
        selected_id = None
        sel = self.tree.selection()
        if sel:
            selected_id = sel[0]

        self.tree.delete(*self.tree.get_children())
        query = self.e_search.get().lower().strip()

        # Группировка порядка отображения
        cat_order = ["Создание нод", "Файл и Проект", "Редактирование", "Холст и Инструменты"]

        actions_by_cat: dict[str, list[str]] = {}
        for aid in self.working_hotkeys:
            meta = ACTION_METADATA.get(aid, {})
            cat = meta.get("category", "Другое")
            actions_by_cat.setdefault(cat, []).append(aid)

        for cat in cat_order + [c for c in actions_by_cat if c not in cat_order]:
            if cat not in actions_by_cat:
                continue
            for aid in actions_by_cat[cat]:
                meta = ACTION_METADATA.get(aid, {})
                title = meta.get("title", aid)
                hotkey = self.working_hotkeys.get(aid, "")

                if query and query not in title.lower() and query not in cat.lower() and query not in hotkey.lower() and query not in aid.lower():
                    continue

                display_key = hotkey if hotkey else "—"
                self.tree.insert("", "end", iid=aid, values=(title, cat, display_key))

        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)
            self.tree.see(selected_id)

    def edit_selected(self) -> None:
        """Открывает окно записи хоткея для выбранного действия."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Настройки", "Пожалуйста, выберите действие из списка.", parent=self.dialog)
            return

        action_id = sel[0]
        current_key = self.working_hotkeys.get(action_id, "")

        def on_assigned(new_key: str) -> None:
            self.working_hotkeys[action_id] = new_key
            self._populate_tree()

        KeyCaptureDialog(
            parent=self.dialog,
            action_id=action_id,
            current_key=current_key,
            existing_hotkeys=self.working_hotkeys,
            on_assigned=on_assigned
        )

    def clear_selected(self) -> None:
        """Очищает горячую клавишу для выбранного действия."""
        sel = self.tree.selection()
        if not sel:
            return
        action_id = sel[0]
        self.working_hotkeys[action_id] = ""
        self._populate_tree()

    def reset_defaults(self) -> None:
        """Сбрасывает все горячие клавиши к исходным значениям по умолчанию."""
        if messagebox.askyesno("Сброс настроек", "Вернуть все сочетания клавиш к значениям по умолчанию?", parent=self.dialog):
            self.working_hotkeys = dict(DEFAULT_HOTKEYS)
            self._populate_tree()

    def save_and_apply(self) -> None:
        """Сохраняет изменённые хоткеи и применяет их к редактору."""
        self.hotkey_manager.save_hotkeys(self.working_hotkeys)
        self.editor.reload_hotkeys()
        self.dialog.destroy()

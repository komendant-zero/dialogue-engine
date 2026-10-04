"""
Dialogue Engine - Search and Replace Dialog with Camera Navigation.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from typing import Any, List

from ui.theme import COLORS


class SearchReplaceDialog:
    """Диалог поиска и замены текста с поддержкой навигации/фокусировки камеры."""

    def __init__(self, parent: tk.Widget, editor: Any):
        self.parent = parent
        self.editor = editor
        self._matched_nodes: List[Any] = []
        self._current_match_idx: int = -1

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Поиск и Замена")
        self.dialog.geometry("380x300")
        self.dialog.configure(bg=COLORS["bg"])
        self.dialog.attributes("-topmost", True)

        self._build_ui()

    def _build_ui(self) -> None:
        tk.Label(self.dialog, text="Найти (текст / персонаж):", bg=COLORS["bg"], fg="white").pack(pady=(10, 3))
        self.e_find = tk.Entry(self.dialog, bg="#333", fg="white", insertbackground="white")
        self.e_find.pack(fill=tk.X, padx=15)
        self.e_find.focus_set()

        tk.Label(self.dialog, text="Заменить на:", bg=COLORS["bg"], fg="white").pack(pady=(8, 3))
        self.e_replace = tk.Entry(self.dialog, bg="#333", fg="white", insertbackground="white")
        self.e_replace.pack(fill=tk.X, padx=15)

        self.lbl_status = tk.Label(self.dialog, text="", bg=COLORS["bg"], fg="#aaaaaa", font=("Segoe UI", 8))
        self.lbl_status.pack(pady=5)

        btn_box = tk.Frame(self.dialog, bg=COLORS["bg"])
        btn_box.pack(pady=5)

        tk.Button(
            btn_box, text="🔍 Найти след.", command=self.find_next,
            bg="#2c3e50", fg="white", relief="flat", padx=8, pady=3
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_box, text="📝 Заменить везде", command=self.do_replace_all,
            bg=COLORS["header_choice"], fg="white", relief="flat", padx=8, pady=3
        ).pack(side=tk.LEFT, padx=4)

        self.e_find.bind("<Return>", lambda e: self.find_next())

    def find_next(self) -> None:
        find_str = self.e_find.get()
        if not find_str:
            self.lbl_status.config(text="Введите строку для поиска", fg="#e74c3c")
            return

        matches = []
        for node in self.editor.nodes:
            if find_str.lower() in node.title.lower() or find_str.lower() in node.content.lower():
                matches.append(node)

        if not matches:
            self.lbl_status.config(text="Совпадений не найдено", fg="#e74c3c")
            return

        self._matched_nodes = matches
        self._current_match_idx = (self._current_match_idx + 1) % len(matches)
        target_node = matches[self._current_match_idx]

        # Выделяем найденный узел
        self.editor.selected_nodes = [target_node]
        self.editor.selected_connection = None
        self.editor.redraw()

        # Фокусируем камеру холста на узле
        if hasattr(self.editor, "focus_on_node"):
            self.editor.focus_on_node(target_node)

        self.lbl_status.config(
            text=f"Найдено: {self._current_match_idx + 1} из {len(matches)}",
            fg="#2ecc71"
        )

    def do_replace_all(self) -> None:
        find_str = self.e_find.get()
        replace_str = self.e_replace.get()

        if not find_str:
            self.lbl_status.config(text="Введите строку для поиска", fg="#e74c3c")
            return

        self.editor.save_state()
        count = 0
        for node in self.editor.nodes:
            changed = False
            if find_str in node.title:
                node.title = node.title.replace(find_str, replace_str)
                changed = True
                count += 1

            if find_str in node.content:
                node.content = node.content.replace(find_str, replace_str)
                changed = True
                count += 1

            if changed:
                node.calculate_size()

        if count > 0:
            self.editor.redraw()
            self.editor.set_dirty(True)
            messagebox.showinfo("Успех", f"Произведено замен: {count}", parent=self.dialog)
            self.dialog.destroy()
        else:
            self.lbl_status.config(text="Совпадений для замены не найдено", fg="#e67e22")

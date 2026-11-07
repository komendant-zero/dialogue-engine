"""
Dialogue Engine - Scenario & Asset Audit Modal Dialog.
Интерактивное окно аудита сценария с фильтрацией проблем и мгновенной навигацией к узлам на холсте.
"""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, List, Optional

from core.models import NodeData
from harness.models import AuditIssue, AuditReport, IssueCategory, IssueSeverity
from harness.scenario_auditor import ScenarioAuditor
from ui.theme import BTN_ACTION_STYLE, BTN_NORMAL_STYLE, COLORS


class ScenarioAuditDialog:
    """Модальное окно результатов автоматического тестирования сценария."""

    def __init__(self, parent: tk.Widget, editor: Any):
        self.parent = parent
        self.editor = editor
        self.report: Optional[AuditReport] = None
        self.filtered_issues: List[AuditIssue] = []

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("🧪 Авто-тестирование сценария и ассетов (Harness)")
        self.dialog.geometry("860x650")
        self.dialog.minsize(740, 500)
        self.dialog.configure(bg=COLORS.get("bg", "#1e1e1e"))
        self.dialog.transient(parent)

        self._build_ui()
        self.run_audit()

    def _build_ui(self) -> None:
        bg = COLORS.get("bg", "#1e1e1e")

        # ── 1. Верхний баннер статуса ─────────────────────────────────────
        self.banner_frame = tk.Frame(self.dialog, bg="#2b2b2b", padx=16, pady=12)
        self.banner_frame.pack(fill=tk.X, padx=12, pady=(10, 6))

        self.lbl_main_status = tk.Label(
            self.banner_frame,
            text="⏳ Выполняется полный аудит сценария...",
            font=("Segoe UI", 12, "bold"),
            bg="#2b2b2b",
            fg="white"
        )
        self.lbl_main_status.pack(anchor="w")

        self.lbl_sub_status = tk.Label(
            self.banner_frame,
            text="Проверка сюжетных путей, тупиков, ассетов и развилок...",
            font=("Segoe UI", 8),
            bg="#2b2b2b",
            fg="#aaaaaa"
        )
        self.lbl_sub_status.pack(anchor="w", pady=(2, 0))

        # Бейджи статистики
        self.badges_frame = tk.Frame(self.banner_frame, bg="#2b2b2b")
        self.badges_frame.pack(anchor="w", pady=(8, 0))

        self.lbl_badge_err = tk.Label(self.badges_frame, text="Ошибок: 0", font=("Segoe UI", 8, "bold"), bg="#c0392b", fg="white", padx=8, pady=2)
        self.lbl_badge_err.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_badge_warn = tk.Label(self.badges_frame, text="Предупреждений: 0", font=("Segoe UI", 8, "bold"), bg="#d35400", fg="white", padx=8, pady=2)
        self.lbl_badge_warn.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_badge_endings = tk.Label(self.badges_frame, text="Концовок: 0", font=("Segoe UI", 8, "bold"), bg="#27ae60", fg="white", padx=8, pady=2)
        self.lbl_badge_endings.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_badge_words = tk.Label(self.badges_frame, text="Слов: 0", font=("Segoe UI", 8), bg="#34495e", fg="white", padx=8, pady=2)
        self.lbl_badge_words.pack(side=tk.LEFT, padx=(0, 6))

        # ── 2. Панель фильтров ────────────────────────────────────────────
        filter_bar = tk.Frame(self.dialog, bg=bg)
        filter_bar.pack(fill=tk.X, padx=12, pady=(4, 6))

        tk.Label(filter_bar, text="Фильтр:", bg=bg, fg="#cccccc", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))

        self.filter_var = tk.StringVar(value="ALL")
        filters = [
            ("Все", "ALL"),
            ("Ошибки", "ERRORS"),
            ("Сюжет / Тупики", "GRAPH"),
            ("Выборы", "CHOICES"),
            ("Ассеты", "ASSETS"),
        ]
        for title, val in filters:
            tk.Radiobutton(
                filter_bar,
                text=title,
                value=val,
                variable=self.filter_var,
                command=self._apply_filter,
                bg=bg,
                fg="white",
                selectcolor="#2b2b2b",
                activebackground=bg,
                activeforeground="white",
                font=("Segoe UI", 8)
            ).pack(side=tk.LEFT, padx=4)

        # Кнопка быстрой навигации
        btn_jump = tk.Button(
            filter_bar,
            text="🔍 Перейти к выбранному узлу",
            command=self._jump_to_selected_issue,
            bg="#2980b9",
            fg="white",
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=2,
            cursor="hand2"
        )
        btn_jump.pack(side=tk.RIGHT)

        # ── 3. Таблица замечаний (Treeview) ───────────────────────────────
        table_frame = tk.Frame(self.dialog, bg=bg)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        columns = ("severity", "category", "node_title", "message", "suggestion")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("severity", text="Важность")
        self.tree.heading("category", text="Категория")
        self.tree.heading("node_title", text="Узел")
        self.tree.heading("message", text="Описание проблемы")
        self.tree.heading("suggestion", text="Рекомендация по исправлению")

        self.tree.column("severity", width=95, anchor="center")
        self.tree.column("category", width=125, anchor="w")
        self.tree.column("node_title", width=140, anchor="w")
        self.tree.column("message", width=310, anchor="w")
        self.tree.column("suggestion", width=250, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-Button-1>", lambda e: self._jump_to_selected_issue())

        # ── 4. Нижняя панель действий ─────────────────────────────────────
        bottom_bar = tk.Frame(self.dialog, bg=bg, pady=8)
        bottom_bar.pack(fill=tk.X, padx=12)

        tk.Button(
            bottom_bar,
            text="🔄 Перезапустить аудит",
            command=self.run_audit,
            bg="#2c3e50",
            fg="white",
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            bottom_bar,
            text="📝 Экспорт отчёта в Markdown (.md)",
            command=self._export_markdown,
            bg="#34495e",
            fg="white",
            relief="flat",
            font=("Segoe UI", 8),
            padx=10,
            pady=4,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            bottom_bar,
            text="📄 Открыть лог (audit.log)",
            command=self._open_log_file,
            bg="#2c3e50",
            fg="white",
            relief="flat",
            font=("Segoe UI", 8),
            padx=10,
            pady=4,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            bottom_bar,
            text="Закрыть",
            command=self.dialog.destroy,
            bg="#333333",
            fg="#cccccc",
            relief="flat",
            font=("Segoe UI", 8),
            padx=12,
            pady=4,
            cursor="hand2"
        ).pack(side=tk.RIGHT)

    def run_audit(self) -> None:
        """Собирает текущие данные редактора и запускает тестирование."""
        try:
            # Преобразуем холст редактора в ProjectData
            project = self.editor._export_to_project_data()
            auditor = ScenarioAuditor(
                project_data=project,
                project_file_path=self.editor.current_file
            )
            self.report = auditor.run_full_audit()
            self._update_ui_with_report()
        except Exception as e:
            messagebox.showerror("Ошибка аудита", f"Не удалось выполнить проверку: {e}", parent=self.dialog)

    def _update_ui_with_report(self) -> None:
        if not self.report:
            return

        # Обновляем баннер статуса
        if self.report.critical_count > 0:
            self.lbl_main_status.config(text="🔴 ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ ОШИБКИ СЮЖЕТА", fg="#e74c3c")
            self.lbl_sub_status.config(text="В сценарии есть битые связи или тупиковые выборы, блокирующие прохождение.")
        elif self.report.error_count > 0:
            self.lbl_main_status.config(text="🟠 НАЙДЕНЫ ОШИБКИ АССЕТОВ ИЛИ РАЗВИЛОК", fg="#e67e22")
            self.lbl_sub_status.config(text="Сюжет проходим, но часть спрайтов, звуков или вариантов выбора не подключены.")
        elif self.report.warning_count > 0:
            self.lbl_main_status.config(text="🟡 СЦЕНАРИЙ ПРОХОДИМ, ЕСТЬ ЗАМЕЧАНИЯ", fg="#f1c40f")
            self.lbl_sub_status.config(text="Найдены изолированные узлы или сюжетные обрывы без явной метки финала.")
        else:
            self.lbl_main_status.config(text="🟢 СЦЕНАРИЙ И АССЕТЫ ПОЛНОСТЬЮ ВАЛИДНЫ!", fg="#2ecc71")
            self.lbl_sub_status.config(text="Все связи, варианты выбора, спрайты и концовки проверены и работают корректно.")

        # Обновляем бейджи
        total_errs = self.report.critical_count + self.report.error_count
        self.lbl_badge_err.config(text=f"Ошибок: {total_errs}")
        self.lbl_badge_warn.config(text=f"Предупреждений: {self.report.warning_count}")
        self.lbl_badge_endings.config(text=f"Концовок: {len(self.report.endings)}")

        words_stat = self.report.stats.get("Общее число слов", "0")
        self.lbl_badge_words.config(text=f"Слов: {words_stat}")

        self._apply_filter()

    def _apply_filter(self) -> None:
        if not self.report:
            return

        self.tree.delete(*self.tree.get_children())
        filter_mode = self.filter_var.get()

        self.filtered_issues = []
        for issue in self.report.issues:
            if filter_mode == "ERRORS" and issue.severity not in (IssueSeverity.CRITICAL, IssueSeverity.ERROR):
                continue
            if filter_mode == "GRAPH" and issue.category != IssueCategory.GRAPH_FLOW:
                continue
            if filter_mode == "CHOICES" and issue.category != IssueCategory.CHOICES:
                continue
            if filter_mode == "ASSETS" and issue.category != IssueCategory.ASSETS:
                continue
            self.filtered_issues.append(issue)

        for idx, issue in enumerate(self.filtered_issues):
            sev_icon = {
                IssueSeverity.CRITICAL: "🔴 CRITICAL",
                IssueSeverity.ERROR: "🟠 ERROR",
                IssueSeverity.WARNING: "🟡 WARN",
                IssueSeverity.INFO: "🔵 INFO",
            }.get(issue.severity, issue.severity.value)

            node_disp = issue.node_title or (f"ID: {issue.node_id}" if issue.node_id else "—")
            self.tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(sev_icon, issue.category.value, node_disp, issue.message, issue.suggestion)
            )

    def _jump_to_selected_issue(self) -> None:
        """Фокусирует холст редактора на узле, выбранном в таблице аудита."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Навигация", "Выберите строку с замечанием из списка.", parent=self.dialog)
            return

        idx = int(selected[0])
        if idx < len(self.filtered_issues):
            issue = self.filtered_issues[idx]
            if not issue.node_id:
                messagebox.showinfo("Навигация", "Это замечание относится к графу в целом, а не к конкретному узлу.", parent=self.dialog)
                return

            target_node = self.editor.find_node_by_id(issue.node_id)
            if target_node:
                self.editor.selected_nodes = [target_node]
                self.editor.selected_connection = None
                self.editor.focus_on_node(target_node)
                self.editor.redraw()
                # Сворачиваем диалог или переводим фокус на редактор
                self.dialog.iconify()
                self.editor.lift()
                self.editor.focus_force()
            else:
                messagebox.showwarning("Навигация", f"Узел '{issue.node_id}' не найден на холсте.", parent=self.dialog)

    def _export_markdown(self) -> None:
        if not self.report:
            return
        f = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt")],
            initialfile="scenario_audit_report.md",
            parent=self.dialog
        )
        if f:
            try:
                with open(f, "w", encoding="utf-8") as out:
                    out.write(self.report.to_markdown())
                messagebox.showinfo("Экспорт отчёта", f"Отчёт успешно сохранён в:\n{f}", parent=self.dialog)
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", f"Не удалось записать файл:\n{e}", parent=self.dialog)

    def _open_log_file(self) -> None:
        """Открывает автоматически сохранённый файл лога audit.log в системе."""
        pdir = os.path.dirname(os.path.abspath(self.editor.current_file)) if getattr(self.editor, "current_file", None) else os.getcwd()
        log_file = os.path.join(pdir, "audit.log")
        if not os.path.exists(log_file):
            log_file = os.path.join(os.getcwd(), "audit.log")

        if os.path.exists(log_file):
            try:
                os.startfile(log_file)
            except Exception:
                messagebox.showinfo("Лог аудита", f"Файл лога сохранён в:\n{log_file}", parent=self.dialog)
        else:
            messagebox.showinfo("Лог аудита", "Файл лога ещё не создан. Запустите аудит.", parent=self.dialog)

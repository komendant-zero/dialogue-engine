"""
Dialogue Engine - Windows Styled Update & Splash Progress Dialogs.
Реализует прогресс-бар в стиле Windows для проверки обновлений при запуске
и диалог ручного обновления по кнопке с автосохранением.
"""

from __future__ import annotations
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable, Optional

from core.models import ENGINE_VERSION
from core.updater import EngineUpdater
from ui.theme import COLORS, BTN_ACTION_STYLE, BTN_NORMAL_STYLE


class StartupSplashDialog(tk.Toplevel):
    """
    Экран запуска с Windows-прогресс-баром и автоматической проверкой обновлений.
    """

    def __init__(self, parent: Optional[Any] = None, on_finish: Optional[Callable[[], None]] = None, timeout_sec: float = 3.0):
        super().__init__(parent)
        self.parent = parent
        self.on_finish = on_finish
        self.timeout_sec = timeout_sec
        self.finished = False

        self.title("Dialogue Engine - Запуск")
        self.geometry("460x220")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])

        # Центрирование окна на экране Windows
        self.update_idletasks()
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws - 460) // 2
        y = (hs - 220) // 2
        self.geometry(f"+{x}+{y}")

        # Убираем стандартную рамку или оставляем заголовок
        self.protocol("WM_DELETE_WINDOW", self._skip)

        self._create_widgets()
        self._start_check_thread()

    def _create_widgets(self) -> None:
        main_frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=18)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Шапка / Логотип
        header_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        header_frame.pack(fill=tk.X, pady=(0, 10))

        lbl_icon = tk.Label(header_frame, text="⚡", font=("Segoe UI", 22), bg=COLORS["bg"], fg="#4a90e2")
        lbl_icon.pack(side=tk.LEFT, padx=(0, 10))

        title_box = tk.Frame(header_frame, bg=COLORS["bg"])
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        lbl_title = tk.Label(
            title_box,
            text="Dialogue Engine",
            font=("Segoe UI", 14, "bold"),
            bg=COLORS["bg"],
            fg="#ffffff"
        )
        lbl_title.pack(anchor="w")

        lbl_ver = tk.Label(
            title_box,
            text=f"Версия {ENGINE_VERSION} • GitHub Sync",
            font=("Segoe UI", 8),
            bg=COLORS["bg"],
            fg="#888888"
        )
        lbl_ver.pack(anchor="w")

        # Статус
        self.lbl_status = tk.Label(
            main_frame,
            text="Проверка обновлений GitHub...",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg="#dcdcdc",
            anchor="w"
        )
        self.lbl_status.pack(fill=tk.X, pady=(10, 6))

        # Windows-стилизованный ttk прогресс-бар
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "WinUpdate.Horizontal.TProgressbar",
            troughcolor="#2d2d2d",
            background="#4a90e2",
            bordercolor="#1e1e1e",
            lightcolor="#4a90e2",
            darkcolor="#357abd"
        )

        self.progress = ttk.Progressbar(
            main_frame,
            style="WinUpdate.Horizontal.TProgressbar",
            orient="horizontal",
            mode="indeterminate",
            length=420
        )
        self.progress.pack(fill=tk.X, pady=(0, 14))
        self.progress.start(12)

        # Нижняя панель с кнопкой пропуска
        btn_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        btn_frame.pack(fill=tk.X)

        self.lbl_detail = tk.Label(
            btn_frame,
            text="Подключение к github.com...",
            font=("Segoe UI", 8),
            bg=COLORS["bg"],
            fg="#777777"
        )
        self.lbl_detail.pack(side=tk.LEFT)

        btn_skip = tk.Button(
            btn_frame,
            text="Пропустить ❯",
            command=self._skip,
            **BTN_NORMAL_STYLE
        )
        btn_skip.pack(side=tk.RIGHT)

    def _start_check_thread(self) -> None:
        t = threading.Thread(target=self._run_check, daemon=True)
        t.start()

    def _run_check(self) -> None:
        time.sleep(0.3)
        res = EngineUpdater.check_for_updates(timeout_sec=self.timeout_sec)

        if self.finished:
            return

        if res.get("available"):
            # Найдено обновление!
            self.after(0, self._handle_update_found, res)
        elif res.get("offline"):
            self.after(0, self._finish_with_status, "Автономный режим. Запуск редактора...", 100)
        else:
            self.after(0, self._finish_with_status, "Версия актуальна! Запуск редактора...", 100)

    def _handle_update_found(self, res: dict) -> None:
        remote_sha = res.get("remote_sha", "")
        self.lbl_status.config(text=f"Доступно обновление [{remote_sha}]! Установка...")
        self.lbl_detail.config(text="Загрузка файлов из GitHub...")

        def do_update():
            success, msg = EngineUpdater.perform_full_update(
                editor=None,
                progress_cb=lambda text, pct: self.after(0, lambda: self._update_progress_ui(text, pct)),
                restart_on_complete=True
            )
            if not success:
                self.after(0, self._finish_with_status, f"Ошибка обновления: {msg}. Запуск...", 100)

        threading.Thread(target=do_update, daemon=True).start()

    def _update_progress_ui(self, text: str, pct: float) -> None:
        self.lbl_status.config(text=text)
        self.progress.stop()
        self.progress.config(mode="determinate", value=pct)

    def _finish_with_status(self, text: str, pct: float = 100) -> None:
        if self.finished:
            return
        self.lbl_status.config(text=text)
        self.progress.stop()
        self.progress.config(mode="determinate", value=pct)
        self.after(600, self._done)

    def _skip(self) -> None:
        self._done()

    def _done(self) -> None:
        if self.finished:
            return
        self.finished = True
        try:
            self.destroy()
        except Exception:
            pass
        if self.on_finish:
            self.on_finish()


class ManualUpdateDialog(tk.Toplevel):
    """
    Диалоговое окно обновления по кнопке из редактора.
    Автоматически сохраняет проект и обновляет движок.
    """

    def __init__(self, editor: Any):
        super().__init__(editor)
        self.editor = editor
        self.title("Обновление Dialogue Engine")
        self.geometry("480x240")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.transient(editor)
        self.grab_set()

        # Центрирование над родительским окном
        self.update_idletasks()
        x = editor.winfo_x() + (editor.winfo_width() - 480) // 2
        y = editor.winfo_y() + (editor.winfo_height() - 240) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._create_widgets()
        self._start_update_process()

    def _create_widgets(self) -> None:
        main_frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=18)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header = tk.Label(
            main_frame,
            text="🚀 Обновление Dialogue Engine",
            font=("Segoe UI", 13, "bold"),
            bg=COLORS["bg"],
            fg="#ffffff"
        )
        header.pack(anchor="w", pady=(0, 6))

        self.lbl_status = tk.Label(
            main_frame,
            text="Связь с GitHub и автосохранение проекта...",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg="#4a90e2",
            anchor="w"
        )
        self.lbl_status.pack(fill=tk.X, pady=(4, 6))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "ManualUpdate.Horizontal.TProgressbar",
            troughcolor="#2d2d2d",
            background="#27ae60",
            bordercolor="#1e1e1e",
            lightcolor="#2ecc71",
            darkcolor="#1e8449"
        )

        self.progress = ttk.Progressbar(
            main_frame,
            style="ManualUpdate.Horizontal.TProgressbar",
            orient="horizontal",
            mode="indeterminate",
            length=440
        )
        self.progress.pack(fill=tk.X, pady=(6, 12))
        self.progress.start(10)

        self.txt_log = tk.Text(
            main_frame,
            height=4,
            bg="#161616",
            fg="#bbbbbb",
            font=("Consolas", 8),
            relief="flat",
            padx=8,
            pady=6
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.txt_log.insert(tk.END, "Инициализация процесса обновления...\n")
        self.txt_log.config(state=tk.DISABLED)

        btn_box = tk.Frame(main_frame, bg=COLORS["bg"])
        btn_box.pack(fill=tk.X)

        self.btn_cancel = tk.Button(
            btn_box,
            text="Отмена",
            command=self.destroy,
            **BTN_NORMAL_STYLE
        )
        self.btn_cancel.pack(side=tk.RIGHT)

    def _log(self, text: str) -> None:
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, f"{text}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)

    def _set_status(self, text: str, pct: Optional[float] = None) -> None:
        self.lbl_status.config(text=text)
        self._log(text)
        if pct is not None:
            self.progress.stop()
            self.progress.config(mode="determinate", value=pct)

    def _start_update_process(self) -> None:
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    def _worker(self) -> None:
        time.sleep(0.2)
        self.after(0, self._set_status, "1/3 Автоматическое сохранение проекта...", 15.0)

        # 1. Автосохранение проекта
        saved_path = EngineUpdater.auto_save_project(self.editor)
        if saved_path:
            self.after(0, self._log, f"✓ Проект сохранён: {os.path.basename(saved_path)}")
        else:
            self.after(0, self._log, "✓ Снимок состояния проекта зафиксирован")

        # 2. Проверка обновлений
        self.after(0, self._set_status, "2/3 Проверка репозитория GitHub...", 35.0)
        res = EngineUpdater.check_for_updates(timeout_sec=4.0)

        if res.get("offline"):
            self.after(0, self._log, "⚠️ GitHub недоступен или отсутствует интернет.")
            self.after(0, self._set_status, "Нет соединения с GitHub", 100.0)
            self.after(1000, lambda: messagebox.showwarning("Обновление", "Не удалось связаться с GitHub. Проверьте подключение к интернету.", parent=self))
            return

        if not res.get("available") and not res.get("error"):
            self.after(0, self._log, f"✓ Движок уже на актуальном коммите ({res.get('local_sha')}).")
            self.after(0, self._set_status, "Установлена последняя версия!", 100.0)

            # Спросить пользователя, хочет ли он принудительно пересинхронизировать
            def ask_force():
                ans = messagebox.askyesno(
                    "Версия актуальна",
                    f"Ваш движок уже обновлен до последней версии ({res.get('local_sha')}).\nХотите выполнить принудительную пересинхронизацию и перезапуск?",
                    parent=self
                )
                if ans:
                    self._proceed_download_and_restart(saved_path)
                else:
                    self.destroy()

            self.after(500, ask_force)
            return

        # Найдено обновление
        self.after(0, self._log, f"★ Найдено обновление! Удаленный коммит: {res.get('remote_sha')}")
        self._proceed_download_and_restart(saved_path)

    def _proceed_download_and_restart(self, saved_path: Optional[str]) -> None:
        self.after(0, self._set_status, "3/3 Скачивание и применение изменений...", 65.0)

        def cb(text: str, pct: float):
            self.after(0, self._set_status, text, pct)

        success, msg = EngineUpdater.apply_git_pull(cb)
        if not success:
            self.after(0, self._log, f"Git pull не удался, пробуем резервную загрузку: {msg}")
            success, msg = EngineUpdater.apply_zip_download(cb)

        if success:
            self.after(0, self._set_status, "Обновление завершено! Перезапуск...", 100.0)
            self.after(0, self._log, "✓ Все файлы успешно обновлены.")
            time.sleep(1.0)
            self.after(0, lambda: EngineUpdater.restart_engine(saved_path))
        else:
            self.after(0, self._set_status, f"Ошибка: {msg}", 100.0)
            self.after(0, self._log, f"❌ Ошибка обновления: {msg}")
            self.after(500, lambda: messagebox.showerror("Ошибка обновления", msg, parent=self))

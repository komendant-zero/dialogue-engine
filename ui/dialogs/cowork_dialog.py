"""
Dialogue Engine - Cowork & Server Management Dialog.
Позволяет управлять сервером совместной работы, сканировать QR-код телефоном
и включать живую синхронизацию с десктопным редактором.
"""

from __future__ import annotations
import io
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
import webbrowser
from typing import Any, Optional

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

from core.network import get_lan_ip
from core.cowork_client import DesktopCoworkClient
from ui.theme import COLORS, BTN_ACTION_STYLE, BTN_NORMAL_STYLE


class CoworkServerManagerDialog(tk.Toplevel):
    """Окно управления сервером совместной работы и подключением мобильных устройств."""

    def __init__(self, editor: Any, port: int = 8000):
        super().__init__(editor)
        self.editor = editor
        self.port = port
        self.qr_image_tk: Optional[Any] = None

        self.title("Dialogue Engine - Сервер совместной работы (Коворк)")
        self.geometry("540x520")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.transient(editor)

        # Центрирование
        self.update_idletasks()
        x = editor.winfo_x() + (editor.winfo_width() - 540) // 2
        y = editor.winfo_y() + (editor.winfo_height() - 520) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._create_widgets()
        self._update_status_ui()

    def _create_widgets(self) -> None:
        main_frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        header = tk.Label(
            main_frame,
            text="🌐 Совместная работа (Коворк 24/7)",
            font=("Segoe UI", 13, "bold"),
            bg=COLORS["bg"],
            fg="#ffffff"
        )
        header.pack(anchor="w", pady=(0, 4))

        sub = tk.Label(
            main_frame,
            text="Работайте над проектом одновременно с телефона, планшета или другого ПК через сайт.",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg="#aaaaaa",
            wraplength=490,
            justify=tk.LEFT
        )
        sub.pack(anchor="w", pady=(0, 14))

        # Панель статуса сервера
        status_box = tk.Frame(main_frame, bg="#252526", padx=14, pady=12, highlightbackground="#3d3d3d", highlightthickness=1)
        status_box.pack(fill=tk.X, pady=(0, 14))

        self.lbl_server_state = tk.Label(
            status_box,
            text="● Статус сервера: Проверка...",
            font=("Segoe UI", 10, "bold"),
            bg="#252526",
            fg="#e67e22"
        )
        self.lbl_server_state.pack(anchor="w")

        lan_ip = get_lan_ip()
        self.network_url = f"http://{lan_ip}:{self.port}"
        self.local_url = f"http://localhost:{self.port}"

        self.lbl_url_info = tk.Label(
            status_box,
            text=f"📱 Вход с телефона / планшета (Wi-Fi): {self.network_url}\n💻 Вход с этого компьютера: {self.local_url}",
            font=("Segoe UI", 9),
            bg="#252526",
            fg="#dcdcdc",
            justify=tk.LEFT
        )
        self.lbl_url_info.pack(anchor="w", pady=(6, 8))

        btn_row = tk.Frame(status_box, bg="#252526")
        btn_row.pack(fill=tk.X)

        self.btn_toggle_server = tk.Button(
            btn_row,
            text="▶️ Запустить локальный сервер",
            command=self._toggle_server,
            **BTN_ACTION_STYLE
        )
        self.btn_toggle_server.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_open_browser = tk.Button(
            btn_row,
            text="🌐 Открыть в браузере",
            command=self._open_in_browser,
            **BTN_NORMAL_STYLE
        )
        self.btn_open_browser.pack(side=tk.LEFT)

        # Блок QR-кода
        qr_frame = tk.Frame(main_frame, bg="#1c1c1c", padx=12, pady=10, highlightbackground="#333333", highlightthickness=1)
        qr_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        lbl_qr_title = tk.Label(
            qr_frame,
            text="📱 Отсканируйте камерой телефона для входа:",
            font=("Segoe UI", 9, "bold"),
            bg="#1c1c1c",
            fg="#4a90e2"
        )
        lbl_qr_title.pack(anchor="w")

        self.lbl_qr_display = tk.Label(qr_frame, bg="#1c1c1c")
        self.lbl_qr_display.pack(pady=8)
        self._generate_qr_preview()

        # Чекбокс живой синхронизации с десктопом
        sync_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        sync_frame.pack(fill=tk.X, pady=(0, 10))

        self.var_sync = tk.BooleanVar(value=getattr(self.editor, "cowork_sync_enabled", False))
        self.chk_sync = tk.Checkbutton(
            sync_frame,
            text="Синхронизировать этот десктопный редактор с сервером (Live Sync)",
            variable=self.var_sync,
            command=self._on_sync_toggled,
            bg=COLORS["bg"],
            fg="#ffffff",
            selectcolor="#252526",
            activebackground=COLORS["bg"],
            activeforeground="#ffffff",
            font=("Segoe UI", 9)
        )
        self.chk_sync.pack(anchor="w")

        # Кнопка закрытия
        btn_close = tk.Button(
            main_frame,
            text="Закрыть",
            command=self.destroy,
            **BTN_NORMAL_STYLE
        )
        btn_close.pack(side=tk.RIGHT)

    def _generate_qr_preview(self) -> None:
        """Создает и выводит QR-код в окно Tkinter."""
        if HAS_QRCODE and HAS_PIL:
            try:
                qr = qrcode.QRCode(box_size=4, border=1)
                qr.add_data(self.network_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#4a90e2", back_color="#1c1c1c")
                self.qr_image_tk = ImageTk.PhotoImage(img)
                self.lbl_qr_display.config(image=self.qr_image_tk)
                return
            except Exception:
                pass

        self.lbl_qr_display.config(
            text=f"QR-код недоступен.\nОткройте в браузере телефона:\n{self.network_url}",
            fg="#888888",
            font=("Segoe UI", 9)
        )

    def _is_server_running(self) -> bool:
        srv_proc = getattr(self.editor, "cowork_server_proc", None)
        if srv_proc and srv_proc.poll() is None:
            return True
        return False

    def _update_status_ui(self) -> None:
        running = self._is_server_running()
        if running:
            self.lbl_server_state.config(text="● Сервер активен (работает 24/7)", fg="#2ecc71")
            self.btn_toggle_server.config(text="⏹️ Остановить сервер", bg="#c0392b")
        else:
            self.lbl_server_state.config(text="○ Сервер остановлен", fg="#888888")
            self.btn_toggle_server.config(text="▶️ Запустить локальный сервер", bg="#2c3e50")

    def _toggle_server(self) -> None:
        if self._is_server_running():
            # Остановка
            proc = getattr(self.editor, "cowork_server_proc", None)
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    pass
                self.editor.cowork_server_proc = None
            self._update_status_ui()
            messagebox.showinfo("Коворк", "Сервер совместной работы остановлен.", parent=self)
        else:
            # Запуск
            main_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            server_script = os.path.join(main_dir, "server.py")
            proj_arg = self.editor.current_file or "Save/cowork_project.json"

            try:
                proc = subprocess.Popen(
                    [sys.executable, server_script, "--port", str(self.port), "--project", proj_arg, "--no-open"],
                    cwd=main_dir
                )
                self.editor.cowork_server_proc = proc
                self._update_status_ui()
                time.sleep(0.5)
                messagebox.showinfo(
                    "Коворк запущен!",
                    f"Сервер успешно запущен!\n\nДля входа с телефона отсканируйте QR-код или откройте:\n{self.network_url}",
                    parent=self
                )
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось запустить сервер: {e}", parent=self)

    def _open_in_browser(self) -> None:
        webbrowser.open(self.local_url)

    def _on_sync_toggled(self) -> None:
        enabled = self.var_sync.get()
        self.editor.cowork_sync_enabled = enabled

        if enabled:
            if not hasattr(self.editor, "cowork_client") or not self.editor.cowork_client:
                self.editor.cowork_client = DesktopCoworkClient(self.editor, f"ws://127.0.0.1:{self.port}/ws")
            self.editor.cowork_client.connect()
            messagebox.showinfo("Синхронизация", "Синхронизация с сервером включена! Изменения будут синхронизироваться в реальном времени.", parent=self)
        else:
            if hasattr(self.editor, "cowork_client") and self.editor.cowork_client:
                self.editor.cowork_client.disconnect()
            messagebox.showinfo("Синхронизация", "Синхронизация отключена.", parent=self)

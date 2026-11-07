"""
Dialogue Engine - Cowork & Server Management Dialog.
Позволяет подключаться к удалённому серверу совместной работы (DuckDNS / VPS),
синхронизировать проект в реальном времени, а также запускать локальный сервер для домашней сети.
"""

from __future__ import annotations
import io
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk
import urllib.parse
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
    """Окно управления подключением к серверу совместной работы и сессиям."""

    def __init__(self, editor: Any, port: int = 8000):
        super().__init__(editor)
        self.editor = editor
        self.port = port
        self.qr_image_tk: Optional[Any] = None
        self.current_tab = "remote"  # "remote" or "local"

        self.title("Dialogue Engine - Совместная работа (Коворк)")
        self.geometry("600x640")
        self.minsize(560, 580)
        self.configure(bg=COLORS["bg"])
        self.transient(editor)

        # Центрирование
        self.update_idletasks()
        x = editor.winfo_x() + (editor.winfo_width() - 600) // 2
        y = editor.winfo_y() + (editor.winfo_height() - 640) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self._ensure_client()
        self._create_widgets()
        self._update_all_ui()

    def _ensure_client(self) -> None:
        """Гарантирует инициализацию клиента коворка в редакторе."""
        if not getattr(self.editor, "cowork_client", None):
            self.editor.cowork_client = DesktopCoworkClient(
                self.editor,
                server_url="https://dialogue-engine.duckdns.org",
                session_id="violant",
                user_name="Автор (ПК)",
                user_color="#3498db",
                password="SPARTA1werXYZ"
            )
        self.editor.cowork_client.on_status_change = self._on_client_status_change

    def _create_widgets(self) -> None:
        main_container = tk.Frame(self, bg=COLORS["bg"], padx=18, pady=14)
        main_container.pack(fill=tk.BOTH, expand=True)

        # ── 1. Верхний переключатель режимов (Табы) ─────────────────────────
        tab_bar = tk.Frame(main_container, bg="#202020", padx=4, pady=4)
        tab_bar.pack(fill=tk.X, pady=(0, 14))

        self.btn_tab_remote = tk.Button(
            tab_bar,
            text="☁️ Облачный сервер (DuckDNS / Интернет)",
            font=("Segoe UI", 9, "bold"),
            command=lambda: self._switch_tab("remote"),
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2"
        )
        self.btn_tab_remote.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self.btn_tab_local = tk.Button(
            tab_bar,
            text="🏠 Локальный сервер (Wi-Fi / Дома)",
            font=("Segoe UI", 9, "bold"),
            command=lambda: self._switch_tab("local"),
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2"
        )
        self.btn_tab_local.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        # ── 2. Контейнеры вкладок ──────────────────────────────────────────
        self.frame_remote = tk.Frame(main_container, bg=COLORS["bg"])
        self.frame_local = tk.Frame(main_container, bg=COLORS["bg"])

        self._build_remote_tab(self.frame_remote)
        self._build_local_tab(self.frame_local)

        self._switch_tab("remote")

        # ── 3. Нижняя панель с кнопкой закрытия ─────────────────────────────
        bottom_bar = tk.Frame(main_container, bg=COLORS["bg"])
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        btn_close = tk.Button(
            bottom_bar,
            text="Закрыть",
            command=self.destroy,
            **BTN_NORMAL_STYLE
        )
        btn_close.pack(side=tk.RIGHT)

    def _switch_tab(self, tab_name: str) -> None:
        self.current_tab = tab_name
        if tab_name == "remote":
            self.frame_local.pack_forget()
            self.frame_remote.pack(fill=tk.BOTH, expand=True)
            self.btn_tab_remote.configure(bg="#2ecc71", fg="#ffffff")
            self.btn_tab_local.configure(bg="#2b2b2b", fg="#888888")
        else:
            self.frame_remote.pack_forget()
            self.frame_local.pack(fill=tk.BOTH, expand=True)
            self.btn_tab_remote.configure(bg="#2b2b2b", fg="#888888")
            self.btn_tab_local.configure(bg="#3498db", fg="#ffffff")

    # ── Вкладка 1: Облачный сервер (DuckDNS) ────────────────────────────────
    def _build_remote_tab(self, parent: tk.Frame) -> None:
        client: DesktopCoworkClient = self.editor.cowork_client

        # Заголовок
        lbl_head = tk.Label(
            parent,
            text="🌐 Подключение к серверу совместной работы",
            font=("Segoe UI", 12, "bold"),
            bg=COLORS["bg"],
            fg="#ffffff"
        )
        lbl_head.pack(anchor="w", pady=(0, 2))

        lbl_desc = tk.Label(
            parent,
            text="Синхронизируйте проект с облаком и работайте вместе с любого устройства.",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg="#aaaaaa"
        )
        lbl_desc.pack(anchor="w", pady=(0, 10))

        # Форма настроек подключения
        box_form = tk.Frame(parent, bg="#252526", padx=12, pady=10, highlightbackground="#3d3d3d", highlightthickness=1)
        box_form.pack(fill=tk.X, pady=(0, 10))

        # 1. Адрес сервера
        row_srv = tk.Frame(box_form, bg="#252526")
        row_srv.pack(fill=tk.X, pady=3)
        tk.Label(row_srv, text="Адрес сервера:", width=14, anchor="w", bg="#252526", fg="#dcdcdc", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.entry_server = tk.Entry(row_srv, bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT, font=("Segoe UI", 9))
        self.entry_server.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.entry_server.insert(0, client.server_input)

        btn_preset_duck = tk.Button(
            row_srv,
            text="DuckDNS",
            font=("Segoe UI", 8),
            bg="#333333",
            fg="#dcdcdc",
            relief=tk.FLAT,
            command=lambda: self._set_server_preset("https://dialogue-engine.duckdns.org")
        )
        btn_preset_duck.pack(side=tk.LEFT, padx=2)

        btn_preset_local = tk.Button(
            row_srv,
            text="Localhost",
            font=("Segoe UI", 8),
            bg="#333333",
            fg="#dcdcdc",
            relief=tk.FLAT,
            command=lambda: self._set_server_preset(f"http://127.0.0.1:{self.port}")
        )
        btn_preset_local.pack(side=tk.LEFT, padx=2)

        # 2. Комната / Сессия
        row_sess = tk.Frame(box_form, bg="#252526")
        row_sess.pack(fill=tk.X, pady=3)
        tk.Label(row_sess, text="Сессия (комната):", width=14, anchor="w", bg="#252526", fg="#dcdcdc", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.entry_session = tk.Entry(row_sess, bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT, font=("Segoe UI", 9))
        self.entry_session.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_session.insert(0, client.session_id)

        # 3. Пароль
        row_pwd = tk.Frame(box_form, bg="#252526")
        row_pwd.pack(fill=tk.X, pady=3)
        tk.Label(row_pwd, text="Пароль сервера:", width=14, anchor="w", bg="#252526", fg="#dcdcdc", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.entry_password = tk.Entry(row_pwd, show="●", bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT, font=("Segoe UI", 9))
        self.entry_password.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_password.insert(0, client.password)

        # 4. Имя и цвет участника
        row_user = tk.Frame(box_form, bg="#252526")
        row_user.pack(fill=tk.X, pady=3)
        tk.Label(row_user, text="Ваше имя на холсте:", width=14, anchor="w", bg="#252526", fg="#dcdcdc", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.entry_user_name = tk.Entry(row_user, bg="#1e1e1e", fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT, font=("Segoe UI", 9))
        self.entry_user_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.entry_user_name.insert(0, client.user_name)

        self.btn_user_color = tk.Button(
            row_user,
            text="Цвет",
            bg=client.user_color,
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT,
            padx=10,
            command=self._pick_user_color
        )
        self.btn_user_color.pack(side=tk.LEFT)

        # Большая кнопка Подключиться / Отключиться
        self.btn_connect_remote = tk.Button(
            parent,
            text="🔌 Подключиться к серверу",
            font=("Segoe UI", 10, "bold"),
            command=self._toggle_remote_connection,
            **BTN_ACTION_STYLE
        )
        self.btn_connect_remote.pack(fill=tk.X, pady=(0, 10))

        # Статус-панель
        self.box_remote_status = tk.Frame(parent, bg="#1c1c1c", padx=12, pady=10, highlightbackground="#333333", highlightthickness=1)
        self.box_remote_status.pack(fill=tk.X, pady=(0, 10))

        self.lbl_remote_status = tk.Label(
            self.box_remote_status,
            text="○ Статус: Отключено",
            font=("Segoe UI", 9, "bold"),
            bg="#1c1c1c",
            fg="#888888"
        )
        self.lbl_remote_status.pack(anchor="w")

        self.lbl_collaborators = tk.Label(
            self.box_remote_status,
            text="Участники онлайн: нет",
            font=("Segoe UI", 9),
            bg="#1c1c1c",
            fg="#cccccc",
            wraplength=520,
            justify=tk.LEFT
        )
        self.lbl_collaborators.pack(anchor="w", pady=(4, 0))

        # Чекбокс Live Sync
        self.var_sync = tk.BooleanVar(value=getattr(self.editor, "cowork_sync_enabled", True))
        chk_sync = tk.Checkbutton(
            parent,
            text="Синхронизировать действия в реальном времени (ноды, перемещения, связи)",
            variable=self.var_sync,
            command=self._on_live_sync_changed,
            bg=COLORS["bg"],
            fg="#ffffff",
            selectcolor="#252526",
            activebackground=COLORS["bg"],
            activeforeground="#ffffff",
            font=("Segoe UI", 9)
        )
        chk_sync.pack(anchor="w", pady=(0, 10))

        # Кнопки синхронизации проекта
        box_actions = tk.Frame(parent, bg="#202020", padx=10, pady=8)
        box_actions.pack(fill=tk.X, pady=(0, 6))

        tk.Label(box_actions, text="Синхронизация проекта:", bg="#202020", fg="#888888", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))

        row_acts = tk.Frame(box_actions, bg="#202020")
        row_acts.pack(fill=tk.X)

        self.btn_pull = tk.Button(
            row_acts,
            text="📥 Загрузить с сервера",
            font=("Segoe UI", 9),
            command=self._pull_project_from_server,
            **BTN_NORMAL_STYLE
        )
        self.btn_pull.pack(side=tk.LEFT, padx=(0, 6), expand=True, fill=tk.X)

        self.btn_push = tk.Button(
            row_acts,
            text="📤 Выгрузить на сервер",
            font=("Segoe UI", 9),
            command=self._push_project_to_server,
            **BTN_NORMAL_STYLE
        )
        self.btn_push.pack(side=tk.LEFT, padx=(0, 6), expand=True, fill=tk.X)

        self.btn_share_link = tk.Button(
            row_acts,
            text="🔗 Копировать ссылку",
            font=("Segoe UI", 9),
            command=self._copy_web_share_link,
            **BTN_NORMAL_STYLE
        )
        self.btn_share_link.pack(side=tk.LEFT, expand=True, fill=tk.X)

    # ── Вкладка 2: Локальный сервер (Wi-Fi) ─────────────────────────────────
    def _build_local_tab(self, parent: tk.Frame) -> None:
        lan_ip = get_lan_ip()
        self.network_url = f"http://{lan_ip}:{self.port}"
        self.local_url = f"http://localhost:{self.port}"

        lbl_head = tk.Label(
            parent,
            text="🏠 Локальный сервер для домашней сети Wi-Fi",
            font=("Segoe UI", 12, "bold"),
            bg=COLORS["bg"],
            fg="#ffffff"
        )
        lbl_head.pack(anchor="w", pady=(0, 4))

        lbl_sub = tk.Label(
            parent,
            text="Запустите встроенный сервер на этом ПК и подключите смартфон по Wi-Fi через QR-код.",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg="#aaaaaa",
            wraplength=520,
            justify=tk.LEFT
        )
        lbl_sub.pack(anchor="w", pady=(0, 10))

        # Панель статуса локального сервера
        status_box = tk.Frame(parent, bg="#252526", padx=12, pady=10, highlightbackground="#3d3d3d", highlightthickness=1)
        status_box.pack(fill=tk.X, pady=(0, 10))

        self.lbl_local_server_state = tk.Label(
            status_box,
            text="○ Статус: Проверка...",
            font=("Segoe UI", 9, "bold"),
            bg="#252526",
            fg="#888888"
        )
        self.lbl_local_server_state.pack(anchor="w")

        self.lbl_local_urls = tk.Label(
            status_box,
            text=f"📱 Вход с телефона / планшета (Wi-Fi): {self.network_url}\n💻 Вход с этого компьютера: {self.local_url}",
            font=("Segoe UI", 8),
            bg="#252526",
            fg="#dcdcdc",
            justify=tk.LEFT
        )
        self.lbl_local_urls.pack(anchor="w", pady=(4, 6))

        btn_row = tk.Frame(status_box, bg="#252526")
        btn_row.pack(fill=tk.X)

        self.btn_toggle_local_server = tk.Button(
            btn_row,
            text="▶️ Запустить локальный сервер",
            command=self._toggle_local_server,
            **BTN_ACTION_STYLE
        )
        self.btn_toggle_local_server.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_open_browser = tk.Button(
            btn_row,
            text="🌐 Открыть в браузере",
            command=lambda: webbrowser.open(self.local_url),
            **BTN_NORMAL_STYLE
        )
        self.btn_open_browser.pack(side=tk.LEFT)

        # Блок QR-кода
        qr_frame = tk.Frame(parent, bg="#1c1c1c", padx=10, pady=8, highlightbackground="#333333", highlightthickness=1)
        qr_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        tk.Label(
            qr_frame,
            text="📱 Отсканируйте камерой телефона (в одной сети Wi-Fi):",
            font=("Segoe UI", 8, "bold"),
            bg="#1c1c1c",
            fg="#4a90e2"
        )
        self.lbl_qr_display = tk.Label(qr_frame, bg="#1c1c1c")
        self.lbl_qr_display.pack(pady=4)
        self._generate_qr_preview()

    # ── Управление подключением к серверу ───────────────────────────────────
    def _set_server_preset(self, url: str) -> None:
        self.entry_server.delete(0, tk.END)
        self.entry_server.insert(0, url)

    def _pick_user_color(self) -> None:
        client: DesktopCoworkClient = self.editor.cowork_client
        color = colorchooser.askcolor(color=client.user_color, title="Выберите цвет курсора", parent=self)
        if color and color[1]:
            client.user_color = color[1]
            self.btn_user_color.configure(bg=color[1])

    def _toggle_remote_connection(self) -> None:
        client: DesktopCoworkClient = self.editor.cowork_client
        if client.is_connected:
            client.disconnect()
            self._update_all_ui()
        else:
            server = self.entry_server.get().strip()
            session = self.entry_session.get().strip() or "violant"
            pwd = self.entry_password.get().strip()
            uname = self.entry_user_name.get().strip() or "Автор (ПК)"

            client.set_config(
                server_url=server,
                session_id=session,
                password=pwd,
                user_name=uname
            )
            self.editor.cowork_sync_enabled = self.var_sync.get()
            client.connect()
            self._update_all_ui()

    def _on_client_status_change(self, state: str, message: str) -> None:
        """Вызывается клиентом коворка при изменении состояния связи."""
        self._update_all_ui()

    def _on_live_sync_changed(self) -> None:
        self.editor.cowork_sync_enabled = self.var_sync.get()

    def _pull_project_from_server(self) -> None:
        """Скачивает актуальный проект из сессии сервера в десктопный редактор."""
        client: DesktopCoworkClient = self.editor.cowork_client
        server = self.entry_server.get().strip()
        session = self.entry_session.get().strip() or "violant"
        pwd = self.entry_password.get().strip()
        client.set_config(server_url=server, session_id=session, password=pwd)

        data = client.fetch_server_project()
        if not data:
            messagebox.showerror(
                "Ошибка загрузки",
                f"Не удалось получить проект из сессии '{session}' с сервера {server}.\nПроверьте подключение и пароль.",
                parent=self
            )
            return

        nodes_count = len(data.get("nodes", []))
        resp = messagebox.askyesno(
            "Загрузка с сервера",
            f"С сервера успешно получен проект сессии '{session}' ({nodes_count} узлов).\n"
            "Загрузить его в текущий редактор? Несохранённые изменения будут заменены.",
            parent=self
        )
        if resp:
            try:
                self.editor.load_project_from_dict(data)
                messagebox.showinfo("Успешно", f"Проект '{session}' загружен в редактор ({nodes_count} узлов)!", parent=self)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось применить проект:\n{e}", parent=self)

    def _push_project_to_server(self) -> None:
        """Выгружает текущий локальный проект из десктопного редактора на сервер."""
        client: DesktopCoworkClient = self.editor.cowork_client
        server = self.entry_server.get().strip()
        session = self.entry_session.get().strip() or "violant"
        pwd = self.entry_password.get().strip()
        client.set_config(server_url=server, session_id=session, password=pwd)

        nodes_count = len(self.editor.nodes)
        resp = messagebox.askyesno(
            "Выгрузка на сервер",
            f"Выгрузить текущий проект ({nodes_count} узлов) в сессию '{session}' на сервер {server}?\n"
            "Это обновит состояние сессии для всех участников.",
            parent=self
        )
        if not resp:
            return

        try:
            proj_dict = self.editor.get_project_as_dict()
            ok = client.push_server_project(proj_dict)
            if ok:
                messagebox.showinfo("Успешно", f"Проект успешно выгружен в сессию '{session}' на сервере!", parent=self)
            else:
                messagebox.showerror("Ошибка", "Сервер вернул ошибку при сохранении проекта.", parent=self)
        except Exception as e:
            messagebox.showerror("Ошибка выгрузки", f"Не удалось выгрузить проект:\n{e}", parent=self)

    def _copy_web_share_link(self) -> None:
        """Копирует ссылку на сессию в буфер обмена."""
        session = self.entry_session.get().strip() or "violant"
        server = self.entry_server.get().strip()

        # Если указан DuckDNS, даём прямую ссылку на DuckDNS или GitHub Pages
        if "duckdns.org" in server:
            url = f"https://dialogue-engine.duckdns.org/?session={urllib.parse.quote(session)}"
        else:
            url = f"https://komendant-zero.github.io/dialogue-engine/app/?session={urllib.parse.quote(session)}"

        self.clipboard_clear()
        self.clipboard_append(url)
        messagebox.showinfo(
            "Ссылка скопирована",
            f"Ссылка на сессию скопирована в буфер обмена:\n\n{url}\n\nОтправьте её соавтору или откройте на телефоне!",
            parent=self
        )

    # ── Управление локальным сервером ──────────────────────────────────────
    def _is_local_server_running(self) -> bool:
        srv_proc = getattr(self.editor, "cowork_server_proc", None)
        if srv_proc and srv_proc.poll() is None:
            return True
        return False

    def _toggle_local_server(self) -> None:
        if self._is_local_server_running():
            proc = getattr(self.editor, "cowork_server_proc", None)
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    pass
                self.editor.cowork_server_proc = None
            self._update_all_ui()
            messagebox.showinfo("Коворк", "Локальный сервер остановлен.", parent=self)
        else:
            main_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            server_script = os.path.join(main_dir, "server.py")
            proj_arg = self.editor.current_file or "Save/cowork_project.json"

            try:
                proc = subprocess.Popen(
                    [sys.executable, server_script, "--port", str(self.port), "--project", proj_arg, "--no-open"],
                    cwd=main_dir
                )
                self.editor.cowork_server_proc = proc
                self._update_all_ui()
                time.sleep(0.5)
                messagebox.showinfo(
                    "Локальный сервер запущен!",
                    f"Сервер успешно запущен на порту {self.port}!\n\nДля входа с телефона отсканируйте QR-код или откройте:\n{self.network_url}",
                    parent=self
                )
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось запустить локальный сервер: {e}", parent=self)

    def _generate_qr_preview(self) -> None:
        if HAS_QRCODE and HAS_PIL:
            try:
                qr = qrcode.QRCode(box_size=3, border=1)
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
            font=("Segoe UI", 8)
        )

    # ── Обновление состояния всего интерфейса ──────────────────────────────
    def _update_all_ui(self) -> None:
        client: DesktopCoworkClient = getattr(self.editor, "cowork_client", None)

        # 1. Облачный сервер статус
        if client and client.is_connected:
            self.lbl_remote_status.config(
                text=f"● Подключено к '{client.session_id}' на {client.server_input}",
                fg="#2ecc71"
            )
            self.btn_connect_remote.config(
                text="⏹️ Отключиться от сервера",
                bg="#c0392b"
            )
            collabs = client.collaborators
            if collabs:
                user_list = ", ".join([f"{c.get('name', 'Участник')} ({c.get('device', 'web')})" for c in collabs])
                self.lbl_collaborators.config(text=f"Участники онлайн ({len(collabs)}): {user_list}", fg="#2ecc71")
            else:
                self.lbl_collaborators.config(text="Участники онлайн: вы единственный в комнате", fg="#aaaaaa")
        elif client and client.state == "CONNECTING":
            self.lbl_remote_status.config(text="🟡 Подключение к серверу...", fg="#f39c12")
            self.btn_connect_remote.config(text="⏳ Подключение...", bg="#7f8c8d")
            self.lbl_collaborators.config(text="Участники онлайн: поиск...", fg="#888888")
        elif client and client.state == "ERROR":
            self.lbl_remote_status.config(text="🔴 Ошибка подключения", fg="#e74c3c")
            self.btn_connect_remote.config(text="🔌 Повторить подключение", bg="#27ae60")
            self.lbl_collaborators.config(text="Проверьте правильность адреса сервера и пароль.", fg="#e74c3c")
        else:
            self.lbl_remote_status.config(text="○ Статус: Отключено", fg="#888888")
            self.btn_connect_remote.config(text="🔌 Подключиться к серверу", bg="#27ae60")
            self.lbl_collaborators.config(text="Участники онлайн: нет", fg="#888888")

        # 2. Локальный сервер статус
        if self._is_local_server_running():
            self.lbl_local_server_state.config(text="● Локальный сервер активен (порт 8000)", fg="#2ecc71")
            self.btn_toggle_local_server.config(text="⏹️ Остановить сервер", bg="#c0392b")
        else:
            self.lbl_local_server_state.config(text="○ Локальный сервер остановлен", fg="#888888")
            self.btn_toggle_local_server.config(text="▶️ Запустить локальный сервер", bg="#2c3e50")

        # 3. Обновление бейджа на панели редактора
        if hasattr(self.editor, "update_cowork_status_ui"):
            self.editor.update_cowork_status_ui()

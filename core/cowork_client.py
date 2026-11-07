"""
Dialogue Engine - Desktop Cowork Sync Client.
Обеспечивает двустороннюю синхронизацию между десктопным приложением (Tkinter)
и сервером совместной работы (телефонами, планшетами и другими ПК).
"""

from __future__ import annotations
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

logger = logging.getLogger("DialogueEngine.CoworkClient")


def normalize_cowork_urls(server_input: str, session_id: str = "violant", token: str = "") -> tuple[str, str]:
    """
    Преобразует пользовательский ввод адреса сервера в пару (ws_url, http_base_url).
    Примеры server_input:
      - 'dialogue-engine.duckdns.org' -> ('wss://dialogue-engine.duckdns.org/ws/violant', 'https://dialogue-engine.duckdns.org')
      - 'https://dialogue-engine.duckdns.org' -> ('wss://dialogue-engine.duckdns.org/ws/violant', 'https://dialogue-engine.duckdns.org')
      - 'localhost:8000' -> ('ws://localhost:8000/ws/violant', 'http://localhost:8000')
      - 'http://127.0.0.1:8000' -> ('ws://127.0.0.1:8000/ws/violant', 'http://127.0.0.1:8000')
    """
    s = server_input.strip()
    if not s:
        s = "dialogue-engine.duckdns.org"

    # Удаляем путь если пользователь ввёл полный URL
    for prefix in ["https://", "http://", "wss://", "ws://"]:
        if s.startswith(prefix):
            scheme = prefix
            rest = s[len(prefix):]
            break
    else:
        # Схемы нет
        if "localhost" in s or "127.0.0.1" in s or s.startswith("192.168.") or s.startswith("10."):
            scheme = "http://"
        else:
            scheme = "https://"
        rest = s

    # Очищаем rest от путей (/ws, /app, /s/..., etc.)
    host = rest.split("/")[0]

    if scheme in ("https://", "wss://"):
        http_base = f"https://{host}"
        ws_base = f"wss://{host}"
    else:
        http_base = f"http://{host}"
        ws_base = f"ws://{host}"

    sid = session_id.strip() or "violant"
    ws_url = f"{ws_base}/ws/{sid}"
    if token:
        ws_url += f"?token={urllib.parse.quote(token)}"

    return ws_url, http_base


class DesktopCoworkClient:
    """Клиент синхронизации десктопного редактора с сервером коворка."""

    def __init__(
        self,
        editor: Any,
        server_url: str = "https://dialogue-engine.duckdns.org",
        session_id: str = "violant",
        user_name: str = "Автор (ПК)",
        user_color: str = "#3498db",
        password: str = "SPARTA1werXYZ"
    ):
        self.editor = editor
        self.server_input = server_url
        self.session_id = session_id
        self.user_name = user_name
        self.user_color = user_color
        self.password = password
        self.token: str = ""

        self.ws_url: str = ""
        self.http_base: str = ""
        self._update_urls()

        self.ws: Optional[Any] = None
        self.is_connected = False
        self.state: str = "DISCONNECTED"  # DISCONNECTED, CONNECTING, CONNECTED, ERROR
        self.thread: Optional[threading.Thread] = None
        self._suppress_outgoing = False

        self.collaborators: List[Dict[str, Any]] = []
        self.client_id: Optional[str] = None
        self.on_status_change: Optional[Callable[[str, str], None]] = None

    def _update_urls(self) -> None:
        self.ws_url, self.http_base = normalize_cowork_urls(self.server_input, self.session_id, self.token)

    def set_config(
        self,
        server_url: Optional[str] = None,
        session_id: Optional[str] = None,
        user_name: Optional[str] = None,
        user_color: Optional[str] = None,
        password: Optional[str] = None
    ) -> None:
        if server_url is not None:
            self.server_input = server_url
        if session_id is not None:
            self.session_id = session_id
        if user_name is not None:
            self.user_name = user_name
        if user_color is not None:
            self.user_color = user_color
        if password is not None:
            self.password = password
        self._update_urls()

    def _notify_status(self, state: str, message: str = "") -> None:
        self.state = state
        if self.on_status_change and self.editor:
            try:
                self.editor.after(0, lambda: self.on_status_change(state, message))
            except Exception:
                pass

    def authenticate(self) -> bool:
        """Пытается получить токен авторизации с сервера через REST API."""
        if not self.password:
            return True

        self._update_urls()
        login_url = f"{self.http_base}/api/auth/login"
        payload = json.dumps({"password": self.password}).encode("utf-8")
        req = urllib.request.Request(
            login_url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "DialogueEngine-Desktop/2.2"}
        )
        try:
            with urllib.request.urlopen(req, timeout=7) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.token = data.get("token", "")
                self._update_urls()
                return True
        except urllib.error.HTTPError as e:
            if e.code == 401:
                logger.warning("Authentication failed: invalid password")
                self._notify_status("ERROR", "Неверный пароль сервера")
            else:
                logger.warning(f"HTTP login error: {e}")
            return False
        except Exception as e:
            logger.info(f"Auth request skipped/failed: {e}")
            # Возможно пароль на сервере выключен, продолжаем попытку подключения
            return True

    def fetch_server_project(self) -> Optional[Dict[str, Any]]:
        """Скачивает текущее состояние проекта конкретной сессии с сервера."""
        self._update_urls()
        url = f"{self.http_base}/api/session/{urllib.parse.quote(self.session_id)}/project"
        headers = {"User-Agent": "DialogueEngine-Desktop/2.2"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to fetch project from server: {e}")
            return None

    def push_server_project(self, project_data: Dict[str, Any]) -> bool:
        """Выгружает проект на сервер в активную сессию."""
        self._update_urls()
        url = f"{self.http_base}/api/project?session={urllib.parse.quote(self.session_id)}"
        if self.token:
            url += f"&token={urllib.parse.quote(self.token)}"

        payload = json.dumps(project_data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "DialogueEngine-Desktop/2.2"}
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.status in (200, 201)
        except Exception as e:
            logger.error(f"Failed to push project to server: {e}")
            return False

    def connect(self) -> bool:
        if not HAS_WEBSOCKET:
            logger.error("websocket-client not available")
            self._notify_status("ERROR", "Модуль websocket-client не установлен")
            return False

        if self.is_connected:
            return True

        self._notify_status("CONNECTING", f"Подключение к {self.server_input}...")
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        return True

    def disconnect(self) -> None:
        self.is_connected = False
        self.state = "DISCONNECTED"
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        self.collaborators.clear()
        self._notify_status("DISCONNECTED", "Отключено")

    def _run_loop(self) -> None:
        # 1. Попытка авторизации
        try:
            self.authenticate()
        except Exception as e:
            logger.warning(f"Auth check warning: {e}")

        def on_message(ws, message):
            try:
                msg = json.loads(message)
                if self.editor:
                    self.editor.after(0, lambda: self._handle_remote_event(msg))
            except Exception as e:
                logger.error(f"Error handling cowork message: {e}")

        def on_error(ws, error):
            logger.error(f"Cowork WebSocket error: {error}")
            self._notify_status("ERROR", f"Ошибка связи: {error}")

        def on_close(ws, close_status_code, close_msg):
            self.is_connected = False
            self.state = "DISCONNECTED"
            self.collaborators.clear()
            logger.info(f"Cowork connection closed ({close_status_code}): {close_msg}")
            self._notify_status("DISCONNECTED", "Соединение разорвано")

        def on_open(ws):
            self.is_connected = True
            self.state = "CONNECTED"
            logger.info("Connected to Cowork Server!")

            # Передаем информацию об участнике и сессии
            init_payload = {
                "name": self.user_name,
                "color": self.user_color,
                "device": "desktop",
                "session": self.session_id,
                "token": self.token or self.password
            }
            ws.send(json.dumps(init_payload, ensure_ascii=False))

        try:
            self._update_urls()
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            self.ws.run_forever(ping_interval=25, ping_timeout=10)
        except Exception as e:
            logger.error(f"Failed to start WebSocket loop: {e}")
            self.is_connected = False
            self._notify_status("ERROR", f"Не удалось подключиться: {e}")

    def _handle_remote_event(self, msg: Dict[str, Any]) -> None:
        """Применяет изменения, пришедшие от сервера, к локальному холсту Tkinter."""
        mtype = msg.get("type")

        # 0. Инициализация сессии и список участников
        if mtype == "init":
            self.is_connected = True
            self.state = "CONNECTED"
            self.client_id = msg.get("client_id")
            self.collaborators = msg.get("collaborators", [])
            online_count = len(self.collaborators)
            self._notify_status("CONNECTED", f"В сети: {online_count} чел. (сессия '{self.session_id}')")
            return

        elif mtype in ("user_joined", "user_left"):
            self.collaborators = msg.get("collaborators", [])
            online_count = len(self.collaborators)
            self._notify_status("CONNECTED", f"В сети: {online_count} чел. (сессия '{self.session_id}')")
            return

        elif mtype == "auth_error":
            self.is_connected = False
            self._notify_status("ERROR", msg.get("message", "Ошибка авторизации (неверный пароль)"))
            return

        # Защита от эха (чтобы входящие события не ретранслировались обратно)
        self._suppress_outgoing = True
        try:
            # 1. Перемещение узла
            if mtype == "node_move":
                nid = str(msg.get("id"))
                x = float(msg.get("x", 0))
                y = float(msg.get("y", 0))
                node = self.editor.find_node_by_id(nid)
                if node:
                    node.x = x
                    node.y = y
                    self.editor.redraw()

            elif mtype == "batch_move":
                moves = msg.get("moves", [])
                for m in moves:
                    nid = str(m.get("id"))
                    node = self.editor.find_node_by_id(nid)
                    if node:
                        node.x = float(m.get("x", node.x))
                        node.y = float(m.get("y", node.y))
                self.editor.redraw()

            # 2. Создание нового узла
            elif mtype == "node_create":
                nd = msg.get("node")
                if nd and isinstance(nd, dict):
                    nid = str(nd.get("id"))
                    if not self.editor.find_node_by_id(nid):
                        self.editor.add_node(
                            ntype=nd.get("type", "story"),
                            x=float(nd.get("x", 100)),
                            y=float(nd.get("y", 100)),
                            title=nd.get("title", ""),
                            content=nd.get("content", ""),
                            custom_data=nd.get("custom_data", {}),
                            mode=nd.get("mode", "standard"),
                            node_id=nid,
                            save_history=False
                        )

            # 3. Обновление содержания узла
            elif mtype == "node_update":
                nd = msg.get("node")
                if nd and isinstance(nd, dict):
                    nid = str(nd.get("id"))
                    node = self.editor.find_node_by_id(nid)
                    if node:
                        node.title = nd.get("title", node.title)
                        node.content = nd.get("content", node.content)
                        node.node_type = nd.get("type", node.node_type)
                        if "custom_data" in nd and isinstance(nd["custom_data"], dict):
                            node.custom_data.update(nd["custom_data"])
                        node.calculate_size()
                        self.editor.redraw()

            # 4. Удаление узла
            elif mtype == "node_delete":
                nid = str(msg.get("id"))
                node = self.editor.find_node_by_id(nid)
                if node:
                    if node in self.editor.nodes:
                        self.editor.nodes.remove(node)
                    self.editor.connections = [
                        c for c in self.editor.connections
                        if str(c.get("from")) != nid and str(c.get("to")) != nid
                    ]
                    if node in self.editor.selected_nodes:
                        self.editor.selected_nodes.remove(node)
                    self.editor.redraw()

            # 5. Создание связи между узлами
            elif mtype == "connection_create":
                cd = msg.get("connection")
                if cd and isinstance(cd, dict):
                    fn = str(cd.get("from", ""))
                    idx = int(cd.get("out_idx", 0))
                    tn = str(cd.get("to", ""))
                    # Удаляем дубликаты
                    self.editor.connections = [
                        c for c in self.editor.connections
                        if not (str(c.get("from")) == fn and int(c.get("out_idx", 0)) == idx)
                    ]
                    self.editor.connections.append({
                        "from": fn,
                        "out_idx": idx,
                        "to": tn
                    })
                    self.editor.redraw()

            # 6. Удаление связи
            elif mtype == "connection_delete":
                cd = msg.get("connection")
                if cd and isinstance(cd, dict):
                    fn = str(cd.get("from", ""))
                    idx = int(cd.get("out_idx", 0))
                    tn = str(cd.get("to", ""))
                    self.editor.connections = [
                        c for c in self.editor.connections
                        if not (str(c.get("from")) == fn and int(c.get("out_idx", 0)) == idx and str(c.get("to")) == tn)
                    ]
                    self.editor.redraw()

        finally:
            self._suppress_outgoing = False

    def send_event(self, data: Dict[str, Any]) -> None:
        """Отправляет локальное действие редактора на сервер коворка."""
        if self._suppress_outgoing or not self.is_connected or not self.ws:
            return
        try:
            self.ws.send(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error sending event to cowork: {e}")

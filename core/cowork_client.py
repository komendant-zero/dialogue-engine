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
from typing import Any, Callable, Dict, Optional

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

from core.models import ConnectionData, NodeData

logger = logging.getLogger("DialogueEngine.CoworkClient")


class DesktopCoworkClient:
    """Клиент синхронизации десктопного редактора с сервером коворка."""

    def __init__(self, editor: Any, server_url: str = "ws://127.0.0.1:8000/ws"):
        self.editor = editor
        self.server_url = server_url
        self.ws: Optional[Any] = None
        self.is_connected = False
        self.thread: Optional[threading.Thread] = None
        self._suppress_outgoing = False

    def connect(self) -> bool:
        if not HAS_WEBSOCKET:
            logger.error("websocket-client not available")
            return False

        if self.is_connected:
            return True

        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        return True

    def disconnect(self) -> None:
        self.is_connected = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None

    def _run_loop(self) -> None:
        def on_message(ws, message):
            try:
                msg = json.loads(message)
                # Передаем обработку в главный GUI поток Tkinter
                if self.editor:
                    self.editor.after(0, lambda: self._handle_remote_event(msg))
            except Exception as e:
                logger.error(f"Error handling cowork message: {e}")

        def on_error(ws, error):
            logger.error(f"Cowork WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            self.is_connected = False
            logger.info("Cowork connection closed")

        def on_open(ws):
            self.is_connected = True
            logger.info("Connected to Cowork Server!")
            # Регистрируемся как Desktop клиент
            info = {
                "name": "Десктоп (ПК)",
                "color": "#3498db",
                "device": "desktop"
            }
            ws.send(json.dumps(info))

        try:
            self.ws = websocket.WebSocketApp(
                self.server_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            self.ws.run_forever()
        except Exception as e:
            logger.error(f"Failed to start WebSocket loop: {e}")
            self.is_connected = False

    def _handle_remote_event(self, msg: Dict[str, Any]) -> None:
        """Применяет изменения, пришедшие с телефона или браузера, к холсту Tkinter."""
        mtype = msg.get("type")
        self._suppress_outgoing = True
        try:
            if mtype == "node_move":
                nid = str(msg.get("id"))
                x = float(msg.get("x", 0))
                y = float(msg.get("y", 0))
                node = self.editor.find_node_by_id(nid)
                if node:
                    node.x = x
                    node.y = y
                    self.editor.redraw()

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
                            node_id=nid
                        )

            elif mtype == "node_update":
                nd = msg.get("node")
                if nd and isinstance(nd, dict):
                    nid = str(nd.get("id"))
                    node = self.editor.find_node_by_id(nid)
                    if node:
                        node.title = nd.get("title", node.title)
                        node.content = nd.get("content", node.content)
                        node.node_type = nd.get("type", node.node_type)
                        if "custom_data" in nd:
                            node.custom_data.update(nd["custom_data"])
                        node.calculate_size()
                        self.editor.redraw()

            elif mtype == "node_delete":
                nid = str(msg.get("id"))
                node = self.editor.find_node_by_id(nid)
                if node:
                    self.editor.delete_node(node)

            elif mtype == "connection_create":
                cd = msg.get("connection")
                if cd and isinstance(cd, dict):
                    fn = str(cd.get("from", ""))
                    idx = int(cd.get("out_idx", 0))
                    tn = str(cd.get("to", ""))
                    exists = any(
                        c["from"].id == fn and c["out_idx"] == idx and c["to"].id == tn
                        for c in self.editor.connections
                    )
                    if not exists:
                        fn_obj = self.editor.find_node_by_id(fn)
                        tn_obj = self.editor.find_node_by_id(tn)
                        if fn_obj and tn_obj:
                            self.editor.connections.append({
                                "from": fn_obj,
                                "out_idx": idx,
                                "to": tn_obj
                            })
                            self.editor.redraw()

            elif mtype == "connection_delete":
                cd = msg.get("connection")
                if cd and isinstance(cd, dict):
                    fn = str(cd.get("from", ""))
                    idx = int(cd.get("out_idx", 0))
                    tn = str(cd.get("to", ""))
                    self.editor.connections = [
                        c for c in self.editor.connections
                        if not (c["from"].id == fn and c["out_idx"] == idx and c["to"].id == tn)
                    ]
                    self.editor.redraw()
        finally:
            self._suppress_outgoing = False

    def send_event(self, data: Dict[str, Any]) -> None:
        """Отправляет событие из Tkinter на сервер коворка."""
        if self._suppress_outgoing or not self.is_connected or not self.ws:
            return
        try:
            self.ws.send(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error sending event to cowork: {e}")

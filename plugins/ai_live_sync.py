"""
Dialogue Engine - Real-Time AI Live Sync Plugin.
Позволяет AI-ассистенту (через MCP) передавать новые узлы, связи и изменения
напрямую в запущенный редактор со скоростью света (<5мс), с плавной анимацией
появления, подсветкой и фокусировкой камеры на созданных блоках.
"""

from __future__ import annotations
import json
import socket
import threading
import tkinter as tk
from typing import Any, Dict, Optional

from core.models import ConnectionData, NodeData
from plugin_system.base import Plugin
from ui.node_view import Node


DEFAULT_LIVE_PORT = 48123


class AILiveSyncPlugin(Plugin):
    name = "Real-Time AI Live Sync"
    version = "1.0"
    author = "Dialogue Engine Team"
    description = "Прямое отображение генерации узлов нейросетью на холсте в реальном времени"

    def __init__(self, editor: Any):
        super().__init__(editor)
        self.server_thread: Optional[threading.Thread] = None
        self.server_socket: Optional[socket.socket] = None
        self.is_running = False

    def on_enable(self) -> None:
        self.start_server()

    def on_disable(self) -> None:
        self.stop_server()

    def start_server(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()

    def stop_server(self) -> None:
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None

    def _server_loop(self) -> None:
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("127.0.0.1", DEFAULT_LIVE_PORT))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)
            print(f"[AILiveSync] Listening for AI events on 127.0.0.1:{DEFAULT_LIVE_PORT}")
        except Exception as e:
            print(f"[AILiveSync] Could not bind port {DEFAULT_LIVE_PORT}: {e}")
            self.is_running = False
            return

        while self.is_running:
            try:
                conn, _ = self.server_socket.accept()
            except socket.timeout:
                continue
            except Exception:
                break

            try:
                conn.settimeout(2.0)
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in chunk:
                        break

                if data:
                    text = data.decode("utf-8").strip()
                    if text:
                        event = json.loads(text)
                        # Передаем выполнение в главный GUI-поток Tkinter
                        if self.editor:
                            self.editor.after(0, self._handle_ai_event, event)
                        conn.sendall(b'{"status":"ok"}\n')
            except Exception as e:
                print(f"[AILiveSync] Error handling connection: {e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _handle_ai_event(self, event: Dict[str, Any]) -> None:
        """Обработка события в главном потоке редактора."""
        action = event.get("action")

        # 1. Добавление нового узла в реальном времени
        if action == "node_spawn":
            node_data_dict = event.get("node")
            conn_dict = event.get("connection")
            if not node_data_dict:
                return

            n_data = NodeData.from_dict(node_data_dict)
            existing = self.editor.find_node_by_id(n_data.id)
            if existing:
                # Если узел уже есть, обновляем
                existing.title = n_data.title
                existing.content = n_data.content
                existing.calculate_size()
                node_to_pulse = existing
            else:
                new_node = Node.from_node_data(self.editor, n_data)
                new_node.is_new = False
                new_node.calculate_size()
                self.editor.nodes.append(new_node)
                node_to_pulse = new_node

            # Добавляем связь, если указана
            if conn_dict and isinstance(conn_dict, dict):
                from_id = conn_dict.get("from")
                to_id = conn_dict.get("to")
                out_idx = int(conn_dict.get("out_idx", 0))
                if from_id and to_id:
                    # Убираем старую связь с этого выхода
                    self.editor.connections = [
                        c for c in self.editor.connections
                        if not (c["from"] == from_id and c["out_idx"] == out_idx)
                    ]
                    self.editor.connections.append({
                        "from": from_id,
                        "out_idx": out_idx,
                        "to": to_id
                    })

            # Перерисовываем холст
            self.editor.redraw()

            # Фокусируем камеру и запускаем неоновую анимацию появления
            if event.get("focus", True) and node_to_pulse:
                self.editor.canvas.center_on_node(node_to_pulse)
                self._animate_ai_spawn(node_to_pulse)

            # Статус бар
            if hasattr(self.editor, "status_bar"):
                spk = n_data.title or "Сцена"
                self.editor.status_bar.config(text=f"✨ AI сгенерировал блок [{spk}]: {n_data.content[:45]}...")

        # 2. Обновление существующего узла
        elif action == "node_update":
            node_id = event.get("node_id")
            node = self.editor.find_node_by_id(node_id)
            if node:
                if "character" in event:
                    node.title = event["character"]
                if "content" in event:
                    node.content = event["content"]
                if "x" in event:
                    node.x = float(event["x"])
                if "y" in event:
                    node.y = float(event["y"])
                if "custom_data" in event and isinstance(event["custom_data"], dict):
                    node.custom_data.update(event["custom_data"])
                if "header_text_color" in event:
                    node.custom_data["header_text_color"] = event["header_text_color"]
                node.calculate_size()
                self.editor.redraw()
                self._animate_ai_spawn(node)

        # 3. Удаление узла
        elif action == "node_delete":
            node_id = event.get("node_id")
            node = self.editor.find_node_by_id(node_id)
            if node:
                self.editor.nodes.remove(node)
                self.editor.connections = [c for c in self.editor.connections if c["from"] != node_id and c["to"] != node_id]
                self.editor.redraw()

        # 4. Создание отдельной связи
        elif action == "connection_add":
            conn = event.get("connection")
            if conn:
                from_id = conn.get("from")
                out_idx = int(conn.get("out_idx", 0))
                to_id = conn.get("to")
                self.editor.connections = [
                    c for c in self.editor.connections
                    if not (c["from"] == from_id and c["out_idx"] == out_idx)
                ]
                self.editor.connections.append({"from": from_id, "out_idx": out_idx, "to": to_id})
                self.editor.redraw()

    def _animate_ai_spawn(self, node: Node) -> None:
        """Анимация неонового фиолетово-бирюзового свечения вокруг появившегося блока."""
        colors = ["#b86bff", "#9b59b6", "#8e44ad", "#1abc9c", "#16a085"]
        tag = f"ai_pulse_{node.id}"

        def step(idx: int):
            try:
                self.editor.canvas.delete(tag)
                if idx < len(colors):
                    x, y, w, h = node.x, node.y, node.width, node.height
                    pad = (len(colors) - idx) * 2
                    self.editor.canvas.create_rectangle(
                        x - pad, y - pad, x + w + pad, y + h + pad,
                        outline=colors[idx],
                        width=3,
                        tags=(tag, "pulse")
                    )
                    self.editor.after(100, lambda: step(idx + 1))
                else:
                    self.editor.canvas.delete(tag)
            except Exception:
                pass

        step(0)

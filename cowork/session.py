"""
Dialogue Engine - Real-Time Cowork State Manager & Room Session.
Управляет состоянием совместной работы, синхронизацией узлов и связей
через WebSockets, отслеживанием пользователей и фоновым автосохранением.
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Set

from core.models import CharacterData, ConnectionData, NodeData, ProjectData, ProjectMetadata
from core.serialization import ProjectSerializer

logger = logging.getLogger("DialogueEngine.CoworkSession")

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_COLORS = [
    "#4a90e2", "#e67e22", "#2ecc71", "#9b59b6", "#f1c40f",
    "#e74c3c", "#1abc9c", "#3498db", "#ff7979", "#badc58"
]


class CoworkSession:
    """Управляет центральным состоянием проекта и комнатой коворка."""

    def __init__(self, project_path: Optional[str] = None):
        self.project_path = project_path or os.path.join(ENGINE_DIR, "Save", "cowork_project.json")
        self.project_data: ProjectData = self._load_or_create_project()
        self.is_dirty: bool = False
        self.last_save_time: float = time.time()
        self.start_time: float = time.time()

        # Подключенные клиенты: client_id -> info
        self.clients: Dict[str, Dict[str, Any]] = {}
        # WebSocket-соединения: client_id -> websocket
        self.sockets: Dict[str, Any] = {}
        # Лог активности и чата
        self.activity_log: List[Dict[str, Any]] = []

        self._lock: Optional[asyncio.Lock] = None
        self._autosave_task: Optional[asyncio.Task] = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _load_or_create_project(self) -> ProjectData:
        """Загружает проект из файла или создает базовый демо-проект."""
        if os.path.exists(self.project_path):
            try:
                proj = ProjectSerializer.load_from_file(self.project_path)
                logger.info(f"Loaded project '{self.project_path}' with {len(proj.nodes)} nodes.")
                return proj
            except Exception as e:
                logger.error(f"Failed to load project from {self.project_path}: {e}")

        # Создаем новый стартовый проект
        proj = ProjectData(
            metadata=ProjectMetadata(title="Коворк-проект"),
            characters=[
                CharacterData(name="Автор", color="#4a90e2"),
                CharacterData(name="Герой", color="#2ecc71"),
            ]
        )
        # Стартовый узел
        start_node = NodeData(
            id=str(uuid.uuid4().int)[:12],
            x=100.0,
            y=150.0,
            title="Начало истории",
            content="Добро пожаловать в совместную работу Dialogue Engine!\nЗдесь можно писать сценарий вместе с любого устройства.",
            node_type="story"
        )
        proj.nodes.append(start_node)
        return proj

    def set_project(self, project: ProjectData, path: Optional[str] = None) -> None:
        """Заменяет активный проект (например, при передаче из десктопного редактора)."""
        self.project_data = project
        if path:
            self.project_path = path
        self.is_dirty = True

    async def register_client(self, websocket: Any, client_info: Dict[str, Any]) -> str:
        """Регистрирует нового участника коворка."""
        async with self.lock:
            client_id = client_info.get("id") or str(uuid.uuid4().hex[:8])
            color = client_info.get("color") or random.choice(DEFAULT_COLORS)
            name = client_info.get("name") or f"Участник #{client_id[:4]}"
            device = client_info.get("device") or "desktop"

            data = {
                "id": client_id,
                "name": name,
                "color": color,
                "device": device,
                "cursor": [0, 0],
                "joined_at": time.time()
            }
            self.clients[client_id] = data
            self.sockets[client_id] = websocket

            # Запись в активность
            self._add_activity(f"👋 {name} подключился ({device})", data)

        # Рассылка события подключения всем остальным
        await self.broadcast({
            "type": "user_joined",
            "user": data,
            "collaborators": list(self.clients.values())
        }, exclude_client=client_id)

        # Отправка новому клиенту полного состояния проекта
        init_payload = {
            "type": "init",
            "client_id": client_id,
            "user": data,
            "collaborators": list(self.clients.values()),
            "project": self.project_data.to_dict(),
            "activity": self.activity_log[-30:]
        }
        await websocket.send_text(json.dumps(init_payload, ensure_ascii=False))
        return client_id

    async def unregister_client(self, client_id: str) -> None:
        """Удаляет участника при отключении."""
        user_data = None
        async with self.lock:
            if client_id in self.clients:
                user_data = self.clients.pop(client_id)
            if client_id in self.sockets:
                self.sockets.pop(client_id, None)

            if user_data:
                self._add_activity(f"🚪 {user_data['name']} покинул сессию", user_data)

        if user_data:
            await self.broadcast({
                "type": "user_left",
                "client_id": client_id,
                "collaborators": list(self.clients.values())
            })

    def _add_activity(self, text: str, user: Optional[Dict[str, Any]] = None) -> None:
        item = {
            "text": text,
            "time": time.strftime("%H:%M:%S"),
            "user": user.get("name") if user else "Система",
            "color": user.get("color") if user else "#888888"
        }
        self.activity_log.append(item)
        if len(self.activity_log) > 100:
            self.activity_log = self.activity_log[-100:]

    async def broadcast(self, message: Dict[str, Any], exclude_client: Optional[str] = None) -> None:
        """Отправляет сообщение всем подключенным участникам."""
        msg_str = json.dumps(message, ensure_ascii=False)
        disconnected = []

        for cid, ws in list(self.sockets.items()):
            if exclude_client and cid == exclude_client:
                continue
            try:
                await ws.send_text(msg_str)
            except Exception:
                disconnected.append(cid)

        for cid in disconnected:
            await self.unregister_client(cid)

    async def handle_message(self, client_id: str, raw_msg: str) -> None:
        """Обрабатывает входящее действие от участника коворка."""
        try:
            msg = json.loads(raw_msg)
        except Exception:
            return

        mtype = msg.get("type")
        sender = self.clients.get(client_id, {})

        if mtype == "ping":
            if client_id in self.sockets:
                await self.sockets[client_id].send_text(json.dumps({"type": "pong"}))
            return

        # 1. Перемещение узла (drag)
        if mtype == "node_move":
            nid = str(msg.get("id"))
            x = float(msg.get("x", 0))
            y = float(msg.get("y", 0))
            for n in self.project_data.nodes:
                if n.id == nid:
                    n.x = x
                    n.y = y
                    break
            self.is_dirty = True
            # Быстрая рассылка остальным клиентам
            await self.broadcast({
                "type": "node_move",
                "id": nid,
                "x": x,
                "y": y,
                "user": sender.get("name"),
                "color": sender.get("color")
            }, exclude_client=client_id)

        # 1b. Пакетное перемещение узлов (Auto-Layout)
        elif mtype == "batch_move":
            moves = msg.get("moves", [])
            moves_dict = {str(m.get("id")): (float(m.get("x", 0)), float(m.get("y", 0))) for m in moves}
            for n in self.project_data.nodes:
                if n.id in moves_dict:
                    n.x, n.y = moves_dict[n.id]
            self.is_dirty = True
            await self.broadcast({
                "type": "batch_move",
                "moves": moves
            }, exclude_client=client_id)

        # 2. Создание нового узла
        elif mtype == "node_create":
            nd = msg.get("node")
            if nd and isinstance(nd, dict):
                node = NodeData.from_dict(nd)
                self.project_data.nodes.append(node)
                self.is_dirty = True
                self._add_activity(f"📝 {sender.get('name', 'Участник')} создал узел '{node.title or 'Безымянный'}'", sender)
                await self.broadcast({
                    "type": "node_create",
                    "node": node.to_dict(),
                    "sender": sender.get("name")
                })

        # 3. Редактирование содержания узла
        elif mtype == "node_update":
            nd = msg.get("node")
            if nd and isinstance(nd, dict):
                nid = str(nd.get("id"))
                for i, existing in enumerate(self.project_data.nodes):
                    if existing.id == nid:
                        self.project_data.nodes[i] = NodeData.from_dict(nd)
                        break
                self.is_dirty = True
                await self.broadcast({
                    "type": "node_update",
                    "node": nd,
                    "sender": sender.get("name")
                }, exclude_client=client_id)

        # 4. Удаление узла
        elif mtype == "node_delete":
            nid = str(msg.get("id"))
            self.project_data.nodes = [n for n in self.project_data.nodes if n.id != nid]
            self.project_data.connections = [
                c for c in self.project_data.connections
                if c.from_node != nid and c.to_node != nid
            ]
            self.is_dirty = True
            self._add_activity(f"🗑️ {sender.get('name', 'Участник')} удалил узел #{nid[:6]}", sender)
            await self.broadcast({
                "type": "node_delete",
                "id": nid,
                "sender": sender.get("name")
            })

        # 5. Создание связи (connection)
        elif mtype == "connection_create":
            cd = msg.get("connection")
            if cd and isinstance(cd, dict):
                conn = ConnectionData.from_dict(cd)
                # Проверка на существование такой связи
                exists = any(
                    c.from_node == conn.from_node and c.out_idx == conn.out_idx and c.to_node == conn.to_node
                    for c in self.project_data.connections
                )
                if not exists:
                    self.project_data.connections.append(conn)
                    self.is_dirty = True
                    await self.broadcast({
                        "type": "connection_create",
                        "connection": conn.to_dict(),
                        "sender": sender.get("name")
                    })

        # 6. Разрыв связи
        elif mtype == "connection_delete":
            cd = msg.get("connection")
            if cd and isinstance(cd, dict):
                fn = str(cd.get("from", ""))
                idx = int(cd.get("out_idx", 0))
                tn = str(cd.get("to", ""))
                self.project_data.connections = [
                    c for c in self.project_data.connections
                    if not (c.from_node == fn and c.out_idx == idx and c.to_node == tn)
                ]
                self.is_dirty = True
                await self.broadcast({
                    "type": "connection_delete",
                    "connection": cd,
                    "sender": sender.get("name")
                })

        # 7. Движение курсора мыши / пальца участника
        elif mtype == "cursor_move":
            cx = float(msg.get("x", 0))
            cy = float(msg.get("y", 0))
            if client_id in self.clients:
                self.clients[client_id]["cursor"] = [cx, cy]
            await self.broadcast({
                "type": "cursor_move",
                "client_id": client_id,
                "user": sender.get("name"),
                "color": sender.get("color"),
                "x": cx,
                "y": cy
            }, exclude_client=client_id)

        # 8. Чат между участниками коворка
        elif mtype == "chat_message":
            text = str(msg.get("text", "")).strip()
            if text:
                item = {
                    "text": text,
                    "user": sender.get("name", "Гость"),
                    "color": sender.get("color", "#4a90e2"),
                    "time": time.strftime("%H:%M:%S")
                }
                self.activity_log.append(item)
                await self.broadcast({
                    "type": "chat_message",
                    "message": item
                })

        # 9. Сохранение проекта по запросу клиента
        elif mtype == "save_project":
            saved_path = self.save_to_disk()
            await self.broadcast({
                "type": "notification",
                "text": f"💾 Проект сохранен на сервере ({os.path.basename(saved_path)})"
            })

        # 10. Создание / обновление персонажа
        elif mtype == "character_update":
            cd = msg.get("character")
            if cd and isinstance(cd, dict):
                cname = str(cd.get("name", "")).strip()
                if cname:
                    updated = False
                    for i, ch in enumerate(self.project_data.characters):
                        if ch.name.strip().lower() == cname.lower():
                            self.project_data.characters[i] = CharacterData.from_dict(cd)
                            updated = True
                            break
                    if not updated:
                        self.project_data.characters.append(CharacterData.from_dict(cd))
                    self.is_dirty = True
                    await self.broadcast({
                        "type": "characters_list_updated",
                        "characters": [c.to_dict() for c in self.project_data.characters],
                        "updated_character": cd,
                        "sender": sender.get("name")
                    })

        # 11. Пакетное применение цвета ко всем репликам персонажа
        elif mtype == "character_batch_apply_color":
            cname = str(msg.get("name", "")).strip().lower()
            color = str(msg.get("color", "")).strip()
            header_color = msg.get("header_color")
            if cname and color:
                updated_nodes = []
                for n in self.project_data.nodes:
                    title_raw = (n.title or "").strip()
                    base_name = title_raw.split("(")[0].split("[")[0].strip().lower()
                    if base_name == cname:
                        n.custom_data = n.custom_data or {}
                        n.custom_data["header_text_color"] = color
                        if header_color:
                            n.custom_data["header_color"] = header_color
                        updated_nodes.append(n.to_dict())
                self.is_dirty = True
                await self.broadcast({
                    "type": "batch_nodes_updated",
                    "nodes": updated_nodes,
                    "sender": sender.get("name")
                })

    def save_to_disk(self) -> str:
        """Сохраняет текущее состояние проекта на сервере."""
        try:
            target_dir = os.path.dirname(os.path.abspath(self.project_path))
            os.makedirs(target_dir, exist_ok=True)
            ProjectSerializer.save_to_file(self.project_data, self.project_path)
            self.is_dirty = False
            self.last_save_time = time.time()
            logger.info(f"Auto-saved project to {self.project_path}")
            return self.project_path
        except Exception as e:
            logger.error(f"Error saving cowork project: {e}")
            return self.project_path

    async def start_autosave_loop(self, interval_sec: float = 4.0) -> None:
        """Фоновый цикл постоянного автосохранения на сервере."""
        try:
            while True:
                await asyncio.sleep(interval_sec)
                if self.is_dirty:
                    self.save_to_disk()
        except asyncio.CancelledError:
            pass


class SessionManager:
    """Менеджер множественных комнат/сессий коворка. У каждой сессии своя ссылка и файл проекта."""

    def __init__(self, default_project_path: Optional[str] = None):
        self.default_project_path = default_project_path or os.path.join(ENGINE_DIR, "data", "violant.json")
        self.data_dir = os.path.dirname(os.path.abspath(self.default_project_path))
        os.makedirs(self.data_dir, exist_ok=True)
        self.sessions: Dict[str, CoworkSession] = {}
        self.default_session_id = "violant"
        self._get_or_create(self.default_session_id, self.default_project_path)

    def _sanitize_session_id(self, session_id: str) -> str:
        safe = "".join(c for c in (session_id or "").strip() if c.isalnum() or c in ("-", "_")).lower()
        return safe or self.default_session_id

    def get_session_file_path(self, session_id: str) -> str:
        safe_id = self._sanitize_session_id(session_id)
        if safe_id == self.default_session_id and os.path.exists(self.default_project_path):
            return self.default_project_path
        return os.path.join(self.data_dir, f"{safe_id}.json")

    def _get_or_create(self, session_id: str, custom_path: Optional[str] = None) -> CoworkSession:
        safe_id = self._sanitize_session_id(session_id)
        if safe_id not in self.sessions:
            path = custom_path or self.get_session_file_path(safe_id)
            sess = CoworkSession(project_path=path)
            if not os.path.exists(path) and safe_id != self.default_session_id:
                sess.project_data.metadata.title = f"Сессия {safe_id}"
            self.sessions[safe_id] = sess
            logger.info(f"SessionManager: Registered session '{safe_id}' with file {path}")
        return self.sessions[safe_id]

    def get_session(self, session_id: str = "violant") -> CoworkSession:
        return self._get_or_create(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        results = []
        seen = set()
        for sid, sess in self.sessions.items():
            seen.add(sid)
            results.append({
                "id": sid,
                "title": sess.project_data.metadata.title or sid,
                "nodes_count": len(sess.project_data.nodes),
                "active_users": len(sess.clients),
                "collaborators": [c.get("name") for c in sess.clients.values()]
            })

        if os.path.isdir(self.data_dir):
            for f in sorted(os.listdir(self.data_dir)):
                if f.endswith(".json") and not f.endswith(".bak"):
                    sid = os.path.splitext(f)[0]
                    if sid not in seen:
                        seen.add(sid)
                        results.append({
                            "id": sid,
                            "title": sid,
                            "nodes_count": 0,
                            "active_users": 0,
                            "collaborators": []
                        })
        return results

    async def save_all(self) -> None:
        for sid, sess in list(self.sessions.items()):
            if sess.is_dirty:
                sess.save_to_disk()

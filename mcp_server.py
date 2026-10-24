"""
Dialogue Engine — Model Context Protocol (MCP) Server  v2.0.0
═══════════════════════════════════════════════════════════════
Позволяет AI-ассистентам (Antigravity, Claude Desktop, Cursor, Continue)
напрямую управлять графом диалогов: создавать, редактировать и экспортировать
сценарии визуальных новелл через стандарт MCP (2024-11-05).

Транспорт: stdio (newline-delimited JSON и Content-Length framing).
Live-sync:  TCP-порт 48123 → мгновенное обновление открытого редактора.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

# ─── UTF-8 для Windows (кириллица через stdio) ───────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ─── Добавляем корень DE в sys.path ──────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from core.models import ConnectionData, NodeData, ProjectData, CharacterData
from core.graph import GraphModel
from core.serialization import ProjectSerializer
from export.renpy_exporter import RenPyExporter

# ─── Константы ───────────────────────────────────────────────────────────────
MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "dialogue-engine-mcp"
SERVER_VERSION = "2.0.0"
SERVER_DESCRIPTION = (
    "Dialogue Engine MCP Server — управление графом диалогов визуальных новелл. "
    "Создаёт, редактирует и экспортирует сценарии Ren'Py через стандарт MCP."
)
LIVE_EDITOR_HOST = "127.0.0.1"
LIVE_EDITOR_PORT = 48123
LIVE_EDITOR_TIMEOUT = 0.2

# Цвета персонажей по умолчанию (hex)
DEFAULT_CHAR_COLORS: Dict[str, str] = {
    "Ривер":    "#0080ff",
    "Ника":     "#00ffff",
    "Джен":     "#ffff00",
    "Энджи":    "#c060f8",
    "???":      "#8000ff",
    "Телевизор": "#66ccff",
}

# ─── Логирование ─────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG,
    format="[DE-MCP] %(levelname)s %(message)s",
)
log = logging.getLogger("de-mcp")


# ═══════════════════════════════════════════════════════════════════════════════
#  Вспомогательные функции
# ═══════════════════════════════════════════════════════════════════════════════

def notify_live_editor(event: Dict[str, Any]) -> None:
    """Посылает JSON-событие в запущенный редактор по TCP (fire-and-forget)."""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(LIVE_EDITOR_TIMEOUT)
            s.connect((LIVE_EDITOR_HOST, LIVE_EDITOR_PORT))
            payload = json.dumps(event, ensure_ascii=False) + "\n"
            s.sendall(payload.encode("utf-8"))
    except Exception:
        pass  # Редактор закрыт — молча игнорируем


def make_error_response(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def make_tool_result(req_id: Any, text: str, is_error: bool = False) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        },
    }


def resolve_color(character: str, nodes: List[NodeData]) -> Optional[str]:
    """Ищет цвет персонажа среди существующих узлов, затем в таблице по умолчанию."""
    name = character.strip()
    for n in nodes:
        if n.title.strip() == name and "header_text_color" in n.custom_data:
            return n.custom_data["header_text_color"]
    return DEFAULT_CHAR_COLORS.get(name)


# ═══════════════════════════════════════════════════════════════════════════════
#  Основной класс MCP-сервера
# ═══════════════════════════════════════════════════════════════════════════════

class DialogueEngineMCPServer:
    """
    MCP-сервер Dialogue Engine.

    Жизненный цикл:
      1. __init__  — инициализация графа, автопоиск проекта.
      2. run_stdio — главный цикл чтения stdin / записи stdout.
      3. handle_request — маршрутизирует JSON-RPC запросы на handle_* методы.
    """

    def __init__(self, initial_project_path: Optional[str] = None) -> None:
        self.project_path: Optional[str] = None
        self.graph = GraphModel()
        self.characters: List[CharacterData] = []
        self.exporter = RenPyExporter()

        # Автопоиск файла проекта
        candidates = [
            initial_project_path,
            os.environ.get("DE_PROJECT_PATH"),
            r"D:\projects\Violant\game\violant.json",
            os.path.join(SCRIPT_DIR, "violant.json"),
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                try:
                    self._load_project_internal(candidate)
                except Exception as exc:
                    log.warning("Не удалось загрузить '%s': %s", candidate, exc)
                break

    # ── Внутренняя загрузка/сохранение ────────────────────────────────────────

    def _load_project_internal(self, file_path: str) -> Dict[str, Any]:
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        proj_data = ProjectSerializer.load_from_file(file_path)
        self.graph.load_from_project_data(proj_data)
        self.characters = list(getattr(proj_data, "characters", []))
        self.project_path = file_path
        log.info("Проект загружен: %s (%d узлов)", file_path, len(self.graph.nodes))
        return {
            "path": file_path,
            "title": proj_data.metadata.title,
            "nodes_count": len(self.graph.nodes),
            "connections_count": len(self.graph.connections),
        }

    def _save_project_internal(self, target_path: Optional[str] = None) -> str:
        path = target_path or self.project_path
        if not path:
            raise ValueError("Путь для сохранения не указан и нет открытого проекта.")
        path = os.path.abspath(path)
        proj_data = self.graph.to_project_data()
        proj_data.characters = list(self.characters)
        ProjectSerializer.save_to_file(proj_data, path, create_backup=True)
        self.project_path = path
        log.info("Проект сохранён: %s", path)
        return path

    def _auto_save_if_needed(self, auto_save: bool) -> str:
        """Сохраняет если auto_save=True и путь известен. Возвращает суффикс для сообщения."""
        if auto_save and self.project_path:
            self._save_project_internal()
            return f" · сохранено в {os.path.basename(self.project_path)}"
        return ""

    # ── Позиционирование ───────────────────────────────────────────────────────

    def _auto_position(
        self,
        parent_id: Optional[str],
        out_idx: int = 0,
        h_gap: float = 60.0,
        v_gap: float = 130.0,
    ) -> Tuple[float, float]:
        """Вычисляет координаты нового узла справа от родителя."""
        if parent_id:
            parent = self.graph.get_node(parent_id)
            if parent:
                return parent.x + parent.width + h_gap, parent.y + out_idx * v_gap

        if self.graph.nodes:
            max_x = max(n.x for n in self.graph.nodes)
            return max_x + 240.0, 100.0
        return 100.0, 100.0

    def _resolve_xy(
        self,
        args: Dict[str, Any],
        parent_id: Optional[str],
        out_idx: int = 0,
    ) -> Tuple[float, float]:
        auto_x, auto_y = self._auto_position(parent_id, out_idx)
        x = float(args["x"]) if "x" in args and args["x"] is not None else auto_x
        y = float(args["y"]) if "y" in args and args["y"] is not None else auto_y
        return x, y

    # ── Общий создатель узла ───────────────────────────────────────────────────

    def _create_node(
        self,
        node_type: str,
        title: str,
        content: str,
        x: float,
        y: float,
        custom_data: Optional[Dict[str, Any]] = None,
    ) -> NodeData:
        node = NodeData(
            id=str(uuid.uuid4().int)[:13],
            x=x,
            y=y,
            title=title,
            content=content,
            node_type=node_type,
            mode="standard",
            custom_data=dict(custom_data or {}),
        )
        self.graph.add_node(node)
        return node

    def _wire_node(
        self,
        node: NodeData,
        connect_from_id: Optional[str],
        connect_out_idx: int,
        connect_to_id: Optional[str] = None,
    ) -> bool:
        """Подключает узел к графу. Если задан connect_to_id — вставляет между двумя узлами."""
        if connect_from_id and connect_from_id in {n.id for n in self.graph.nodes}:
            if connect_to_id:
                self.graph.remove_connection(connect_from_id, connect_out_idx, connect_to_id)
                self.graph.add_connection(node.id, 0, connect_to_id)
            return self.graph.add_connection(connect_from_id, connect_out_idx, node.id)
        return False

    # ══════════════════════════════════════════════════════════════════════════
    #  ОБРАБОТЧИКИ ИНСТРУМЕНТОВ (tool_*)
    # ══════════════════════════════════════════════════════════════════════════

    # ─── Проект ───────────────────────────────────────────────────────────────

    def tool_load_project(self, args: Dict[str, Any]) -> str:
        path = (
            args.get("file_path")
            or args.get("path")
            or self.project_path
            or r"D:\projects\Violant\game\violant.json"
        )
        res = self._load_project_internal(str(path))
        return (
            f"✅ Проект загружен: {res['path']}\n"
            f"   Узлов: {res['nodes_count']}  |  Связей: {res['connections_count']}"
        )

    def tool_save_project(self, args: Dict[str, Any]) -> str:
        target = args.get("target_path") or args.get("path") or self.project_path
        path = self._save_project_internal(str(target) if target else None)
        return f"✅ Проект сохранён: {path}"

    def tool_reload_server(self, args: Dict[str, Any]) -> str:  # noqa: ARG002
        raise SystemExit(0)

    # ─── Анализ ───────────────────────────────────────────────────────────────

    def tool_get_stats(self, args: Dict[str, Any]) -> str:  # noqa: ARG002
        nodes = self.graph.nodes
        conns = self.graph.connections

        types_count: Dict[str, int] = {}
        speakers: Dict[str, int] = {}
        for n in nodes:
            types_count[n.node_type] = types_count.get(n.node_type, 0) + 1
            if n.node_type == "story":
                spk = n.title or "Без автора"
                speakers[spk] = speakers.get(spk, 0) + 1

        target_ids = {c.to_node for c in conns}
        source_ids = {c.from_node for c in conns}
        roots = [n.id for n in nodes if n.id not in target_ids]
        leaves = [n.id for n in nodes if n.id not in source_ids]
        unreachable = self.graph.get_unreachable_nodes()

        lines = [
            "╔══ СТАТИСТИКА ПРОЕКТА ══════════════════════════════╗",
            f"  Файл:     {self.project_path or '(не сохранён)'}",
            f"  Узлов:    {len(nodes)}",
            f"  Связей:   {len(conns)}",
            f"  Корни:    {len(roots)}  |  Листья: {len(leaves)}  |  Изолировано: {len(unreachable)}",
            "╠══ Распределение по типам ══════════════════════════╣",
        ]
        for t, cnt in sorted(types_count.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {t:<14} {cnt}")
        if speakers:
            lines.append("╠══ Реплики по персонажам ════════════════════════════╣")
            for spk, cnt in sorted(speakers.items(), key=lambda kv: -kv[1]):
                lines.append(f"  {spk:<20} {cnt}")
        lines.append("╚════════════════════════════════════════════════════╝")
        return "\n".join(lines)

    def tool_get_characters(self, args: Dict[str, Any]) -> str:  # noqa: ARG002
        """Возвращает список всех уникальных персонажей с их цветами и числом реплик."""
        char_data: Dict[str, Dict[str, Any]] = {}
        for ch in getattr(self, "characters", []):
            if ch.name.strip():
                char_data[ch.name.strip()] = {
                    "count": 0,
                    "color": ch.color,
                    "emotions": list(ch.emotions),
                }

        for n in self.graph.nodes:
            if n.node_type != "story" or not n.title or n.title.startswith("#"):
                continue
            name = n.title.strip()
            if name not in char_data:
                char_data[name] = {
                    "count": 0,
                    "color": n.custom_data.get("header_text_color", ""),
                    "emotions": [],
                }
            char_data[name]["count"] += 1
            if not char_data[name]["color"]:
                char_data[name]["color"] = n.custom_data.get("header_text_color", "")

        if not char_data:
            return "Персонажей (story-узлов) не найдено."

        lines = [f"Персонажи ({len(char_data)} шт.):\n"]
        for name, info in sorted(char_data.items(), key=lambda kv: -kv[1]["count"]):
            color = info["color"] or DEFAULT_CHAR_COLORS.get(name, "—")
            emo_str = f"   эмоции: [{', '.join(info['emotions'])}]" if info.get("emotions") else ""
            lines.append(f"  {name:<20} {info['count']:>4} реплик   цвет: {color}{emo_str}")
        return "\n".join(lines)

    def tool_find_leaf_endpoints(self, args: Dict[str, Any]) -> str:  # noqa: ARG002
        nodes = {n.id: n for n in self.graph.nodes}
        source_ids = {c.from_node for c in self.graph.connections}
        leaves = [n for nid, n in nodes.items() if nid not in source_ids]

        if not leaves:
            return "В графе нет конечных точек — все узлы имеют продолжение."

        res = [f"Найдено {len(leaves)} конечных точек (где сюжет останавливается):\n"]
        for idx, leaf in enumerate(leaves, 1):
            incoming = self.graph.get_incoming(leaf.id)
            prev = (
                f"← от [{incoming[0].from_node}] вых.{incoming[0].out_idx}"
                if incoming
                else "← нет входящих"
            )
            preview = leaf.content.replace("\n", " ").strip()[:140]
            res.append(f"#{idx:>3}  [{leaf.id}] ({leaf.node_type}) {leaf.title}  {prev}")
            res.append(f"       {preview}")
            res.append("")
        return "\n".join(res)

    def tool_get_node(self, args: Dict[str, Any]) -> str:
        node_id = str(args.get("node_id", ""))
        node = self.graph.get_node(node_id)
        if not node:
            return f"❌ Узел '{node_id}' не найден."

        outgoing = sorted(self.graph.get_outgoing(node_id), key=lambda c: c.out_idx)
        incoming = self.graph.get_incoming(node_id)

        data = {
            "id": node.id,
            "title": node.title,
            "type": node.node_type,
            "content": node.content,
            "x": node.x,
            "y": node.y,
            "custom_data": node.custom_data,
            "incoming": [{"from": c.from_node, "out_idx": c.out_idx} for c in incoming],
            "outgoing": [{"out_idx": c.out_idx, "to": c.to_node} for c in outgoing],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def tool_search_nodes(self, args: Dict[str, Any]) -> str:
        query = str(args.get("query", "")).lower()
        character = str(args.get("character", "")).lower()
        node_type = str(args.get("node_type", "")).lower()
        limit = max(1, int(args.get("limit", 20)))

        matches = []
        for n in self.graph.nodes:
            if character and character not in n.title.lower():
                continue
            if node_type and node_type != n.node_type.lower():
                continue
            if query and query not in n.content.lower() and query not in n.title.lower():
                continue
            matches.append(n)
            if len(matches) >= limit:
                break

        if not matches:
            return "Узлы по заданным критериям не найдены."

        lines = [f"Найдено: {len(matches)} (показано до {limit}):\n"]
        for m in matches:
            preview = m.content.replace("\n", " ").strip()[:90]
            lines.append(f"  [{m.id}] ({m.node_type}) {m.title}: {preview}")
        return "\n".join(lines)

    def tool_trace_branch(self, args: Dict[str, Any]) -> str:
        start_node_id = args.get("start_node_id")
        max_depth = int(args.get("max_depth", 30))

        nodes_map = {n.id: n for n in self.graph.nodes}
        out_map: Dict[str, List[ConnectionData]] = {}
        for c in self.graph.connections:
            out_map.setdefault(c.from_node, []).append(c)

        if start_node_id:
            start_ids = [str(start_node_id)]
        else:
            target_ids = {c.to_node for c in self.graph.connections}
            start_ids = [n.id for n in self.graph.nodes if n.id not in target_ids]

        output: List[str] = []

        def trace(curr_id: str, depth: int, visited: Set[str]) -> None:
            if depth > max_depth or curr_id in visited:
                return
            visited.add(curr_id)
            n = nodes_map.get(curr_id)
            if not n:
                return
            indent = "  " * depth
            preview = n.content.replace("\n", " ").strip()
            output.append(f"{indent}[{n.id}] {n.title}: {preview}")
            conns = sorted(out_map.get(curr_id, []), key=lambda c: c.out_idx)
            for c in conns:
                if len(conns) > 1:
                    output.append(f"{indent}  ↳ [Выход #{c.out_idx}]")
                trace(c.to_node, depth + 1, visited.copy())

        for sid in start_ids:
            output.append(f"═══ ТРАССИРОВКА ОТ [{sid}] ═══")
            trace(sid, 0, set())
            output.append("")

        return "\n".join(output)

    # ─── Создание узлов ───────────────────────────────────────────────────────

    def tool_add_story_node(self, args: Dict[str, Any]) -> str:
        character = str(args.get("character", "#Сцена"))
        content = str(args.get("content", ""))
        connect_from_id = args.get("connect_from_id")
        connect_out_idx = int(args.get("connect_out_idx", 0))
        auto_save = bool(args.get("auto_save", True))

        x, y = self._resolve_xy(args, connect_from_id, connect_out_idx)

        custom_data = dict(args.get("custom_data") or {})
        if "header_text_color" not in custom_data:
            color = resolve_color(character, self.graph.nodes)
            if color:
                custom_data["header_text_color"] = color

        node = self._create_node("story", character, content, x, y, custom_data)
        connected = self._wire_node(node, connect_from_id, connect_out_idx)
        saved = self._auto_save_if_needed(auto_save)

        notify_live_editor({
            "action": "node_spawn",
            "node": node.to_dict(),
            "connection": {"from": str(connect_from_id), "out_idx": connect_out_idx, "to": node.id}
                          if connect_from_id else None,
            "focus": True,
        })

        return (
            f"✅ Story-узел создан: [{node.id}] — «{character}»{saved}\n"
            f"   Подключён к [{connect_from_id}]: {connected}"
        )

    def tool_add_choice_node(self, args: Dict[str, Any]) -> str:
        title = str(args.get("title", "Выбор"))
        choices = args.get("choices", [])
        if isinstance(choices, str):
            choices = [c.strip() for c in choices.split("\n") if c.strip()]
        content = "\n".join(str(c) for c in choices)

        connect_from_id = args.get("connect_from_id")
        connect_out_idx = int(args.get("connect_out_idx", 0))
        auto_save = bool(args.get("auto_save", True))

        x, y = self._resolve_xy(args, connect_from_id, connect_out_idx)
        node = self._create_node("choice", title, content, x, y)
        self._wire_node(node, connect_from_id, connect_out_idx)
        saved = self._auto_save_if_needed(auto_save)

        notify_live_editor({
            "action": "node_spawn",
            "node": node.to_dict(),
            "connection": {"from": str(connect_from_id), "out_idx": connect_out_idx, "to": node.id}
                          if connect_from_id else None,
            "focus": True,
        })

        opts = "\n".join(f"  out_idx {i}: «{opt}»" for i, opt in enumerate(choices))
        return (
            f"✅ Узел выбора создан: [{node.id}] — «{title}» ({len(choices)} вариантов){saved}\n"
            f"{opts}"
        )

    def tool_add_condition_node(self, args: Dict[str, Any]) -> str:
        condition = str(args.get("condition", ""))
        title = str(args.get("title", "Условие"))
        connect_from_id = args.get("connect_from_id")
        connect_out_idx = int(args.get("connect_out_idx", 0))
        auto_save = bool(args.get("auto_save", True))

        x, y = self._resolve_xy(args, connect_from_id, connect_out_idx)
        node = self._create_node("condition", title, condition, x, y)
        self._wire_node(node, connect_from_id, connect_out_idx)
        saved = self._auto_save_if_needed(auto_save)

        notify_live_editor({
            "action": "node_spawn",
            "node": node.to_dict(),
            "connection": {"from": str(connect_from_id), "out_idx": connect_out_idx, "to": node.id}
                          if connect_from_id else None,
            "focus": True,
        })

        return (
            f"✅ Узел условия создан: [{node.id}] — «{condition}»{saved}\n"
            f"   out_idx 0 → ИСТИНА  |  out_idx 1 → ЛОЖЬ"
        )

    def tool_add_music_node(self, args: Dict[str, Any]) -> str:
        music_file = str(args.get("music_file", ""))
        music_mode = str(args.get("music_mode", "bg"))
        title = str(args.get("title", "") or os.path.basename(music_file) or "Музыка")
        connect_from_id = args.get("connect_from_id")
        connect_out_idx = int(args.get("connect_out_idx", 0))
        connect_to_id = args.get("connect_to_id")
        auto_save = bool(args.get("auto_save", True))

        x, y = self._resolve_xy(args, connect_from_id, connect_out_idx)

        custom_data: Dict[str, Any] = {
            "music_mode": music_mode,
            "music_file": music_file,
            "bg_color": "#196f3d",
            "header_color": "#0d4528",
            "text_color": "#ffffff",
        }
        if "fadein" in args:
            custom_data["fadein"] = float(args["fadein"])
        if "fadeout" in args:
            custom_data["fadeout"] = float(args["fadeout"])

        node = self._create_node("music", title, music_file, x, y, custom_data)
        self._wire_node(node, connect_from_id, connect_out_idx, connect_to_id)
        saved = self._auto_save_if_needed(auto_save)

        notify_live_editor({
            "action": "node_spawn",
            "node": node.to_dict(),
            "connection": {"from": str(connect_from_id), "out_idx": connect_out_idx, "to": node.id}
                          if connect_from_id else None,
            "focus": True,
        })

        return (
            f"✅ Музыкальный узел создан: [{node.id}] — «{title}»{saved}\n"
            f"   Файл: {music_file}  |  Режим: {music_mode}"
        )

    # ─── Батч-операции ────────────────────────────────────────────────────────

    def tool_bulk_add_nodes(self, args: Dict[str, Any]) -> str:
        """
        Массовое создание узлов из списка. Каждый элемент — словарь с теми же
        ключами, что и у соответствующего de_add_*_node инструмента,
        плюс обязательный ключ «type»: «story» | «choice» | «condition» | «music».
        """
        items: List[Dict[str, Any]] = args.get("nodes", [])
        if not items:
            return "❌ Список узлов пуст (ключ «nodes»)."

        auto_save = bool(args.get("auto_save", True))
        created: List[str] = []
        errors: List[str] = []

        # Подавляем авто-сохранение внутри каждого вызова
        for item in items:
            item_copy = dict(item)
            item_copy["auto_save"] = False
            node_type = str(item_copy.pop("type", "story"))
            handler = {
                "story": self.tool_add_story_node,
                "choice": self.tool_add_choice_node,
                "condition": self.tool_add_condition_node,
                "music": self.tool_add_music_node,
            }.get(node_type)
            if not handler:
                errors.append(f"Неизвестный тип «{node_type}»")
                continue
            try:
                result = handler(item_copy)
                created.append(result.splitlines()[0])
            except Exception as exc:
                errors.append(f"{node_type}: {exc}")

        saved = self._auto_save_if_needed(auto_save)

        lines = [f"Батч-операция завершена: создано {len(created)}/{len(items)} узлов{saved}"]
        lines += created
        if errors:
            lines.append("\nОшибки:")
            lines += [f"  ✗ {e}" for e in errors]
        return "\n".join(lines)

    # ─── Редактирование ───────────────────────────────────────────────────────

    def tool_update_node(self, args: Dict[str, Any]) -> str:
        node_id = str(args.get("node_id", ""))
        node = self.graph.get_node(node_id)
        if not node:
            return f"❌ Узел '{node_id}' не найден."

        changed: List[str] = []
        if "character" in args:
            node.title = str(args["character"])
            changed.append(f"title=«{node.title}»")
        if "title" in args:
            node.title = str(args["title"])
            changed.append(f"title=«{node.title}»")
        if "content" in args:
            node.content = str(args["content"])
            changed.append("content")
        if "node_type" in args:
            node.node_type = str(args["node_type"])
            changed.append(f"type={node.node_type}")
        if "x" in args:
            node.x = float(args["x"])
            changed.append(f"x={node.x}")
        if "y" in args:
            node.y = float(args["y"])
            changed.append(f"y={node.y}")
        if isinstance(args.get("custom_data"), dict):
            node.custom_data.update(args["custom_data"])
            changed.append("custom_data")

        # Цвет персонажа
        if "header_text_color" in args:
            node.custom_data["header_text_color"] = str(args["header_text_color"])
            changed.append("color")
        elif ("character" in args or "title" in args) and "header_text_color" not in node.custom_data:
            color = resolve_color(node.title, self.graph.nodes)
            if color:
                node.custom_data["header_text_color"] = color
                changed.append("color(auto)")

        auto_save = bool(args.get("auto_save", True))
        saved = self._auto_save_if_needed(auto_save)

        notify_live_editor({
            "action": "node_update",
            "node_id": node_id,
            "character": node.title,
            "content": node.content,
            "x": node.x,
            "y": node.y,
            "custom_data": node.custom_data,
            "header_text_color": node.custom_data.get("header_text_color"),
        })

        return f"✅ Узел [{node_id}] обновлён: {', '.join(changed) or 'без изменений'}{saved}"

    def tool_move_node(self, args: Dict[str, Any]) -> str:
        """Перемещает узел на новые координаты (или смещает на delta_x / delta_y)."""
        node_id = str(args.get("node_id", ""))
        node = self.graph.get_node(node_id)
        if not node:
            return f"❌ Узел '{node_id}' не найден."

        if "x" in args:
            node.x = float(args["x"])
        elif "delta_x" in args:
            node.x += float(args["delta_x"])
        if "y" in args:
            node.y = float(args["y"])
        elif "delta_y" in args:
            node.y += float(args["delta_y"])

        auto_save = bool(args.get("auto_save", True))
        saved = self._auto_save_if_needed(auto_save)
        notify_live_editor({"action": "node_update", "node_id": node_id, "x": node.x, "y": node.y})
        return f"✅ Узел [{node_id}] перемещён на ({node.x:.0f}, {node.y:.0f}){saved}"

    def tool_duplicate_node(self, args: Dict[str, Any]) -> str:
        """Создаёт копию узла (без связей), смещая по умолчанию на +240px по X."""
        node_id = str(args.get("node_id", ""))
        src = self.graph.get_node(node_id)
        if not src:
            return f"❌ Узел '{node_id}' не найден."

        offset_x = float(args.get("offset_x", 240.0))
        offset_y = float(args.get("offset_y", 0.0))

        copy = self._create_node(
            node_type=src.node_type,
            title=src.title,
            content=src.content,
            x=src.x + offset_x,
            y=src.y + offset_y,
            custom_data=dict(src.custom_data),
        )
        auto_save = bool(args.get("auto_save", True))
        saved = self._auto_save_if_needed(auto_save)

        notify_live_editor({"action": "node_spawn", "node": copy.to_dict(), "focus": False})
        return f"✅ Дубликат [{copy.id}] создан из [{node_id}]{saved}"

    def tool_delete_node(self, args: Dict[str, Any]) -> str:
        node_id = str(args.get("node_id", ""))
        removed = self.graph.remove_node(node_id)
        if not removed:
            return f"❌ Узел '{node_id}' не найден."

        auto_save = bool(args.get("auto_save", True))
        saved = self._auto_save_if_needed(auto_save)

        notify_live_editor({"action": "node_delete", "node_id": node_id})
        return f"✅ Узел [{node_id}] «{removed.title}» и все его связи удалены{saved}"

    # ─── Связи ────────────────────────────────────────────────────────────────

    def tool_connect_nodes(self, args: Dict[str, Any]) -> str:
        from_node = str(args.get("from_node", ""))
        to_node = str(args.get("to_node", ""))
        out_idx = int(args.get("out_idx", 0))
        auto_save = bool(args.get("auto_save", True))

        node_ids = {n.id for n in self.graph.nodes}
        if from_node not in node_ids:
            return f"❌ Исходный узел '{from_node}' не существует."
        if to_node not in node_ids:
            return f"❌ Целевой узел '{to_node}' не существует."

        success = self.graph.add_connection(from_node, out_idx, to_node)
        if not success:
            return f"❌ Не удалось соединить [{from_node}] → [{to_node}]."

        self._auto_save_if_needed(auto_save)
        notify_live_editor({
            "action": "connection_add",
            "connection": {"from": from_node, "out_idx": out_idx, "to": to_node},
        })
        return f"✅ Связь создана: [{from_node}] (вых.{out_idx}) → [{to_node}]"

    def tool_disconnect_nodes(self, args: Dict[str, Any]) -> str:
        from_node = str(args.get("from_node", ""))
        out_idx = int(args.get("out_idx", 0))
        to_node = args.get("to_node")
        auto_save = bool(args.get("auto_save", True))

        removed = self.graph.remove_connection(
            from_node, out_idx, str(to_node) if to_node else None
        )
        self._auto_save_if_needed(auto_save)
        return f"✅ Связь(и) удалены: {removed}"

    # ─── Валидация и экспорт ──────────────────────────────────────────────────

    def tool_validate_graph(self, args: Dict[str, Any]) -> str:  # noqa: ARG002
        issues = self.graph.validate()
        if not issues:
            return "✅ Граф прошёл проверку: ошибок не обнаружено."

        lines = [f"Найдено замечаний: {len(issues)}\n"]
        for issue in issues:
            nid = f"[{issue.node_id}] " if issue.node_id else ""
            lines.append(f"  [{issue.level.upper():>7}] {nid}{issue.message}")
        return "\n".join(lines)

    def tool_export_renpy(self, args: Dict[str, Any]) -> str:
        output_dir = args.get("output_dir")
        if not output_dir:
            output_dir = (
                os.path.dirname(self.project_path)
                if self.project_path
                else r"D:\projects\Violant\game"
            )
        output_dir = os.path.abspath(str(output_dir))
        proj_data = self.graph.to_project_data()
        success, msg = self.exporter.export(proj_data, output_dir)
        if success:
            rpy_path = os.path.join(output_dir, "script.rpy")
            return (
                f"✅ Экспорт в Ren'Py завершён!\n"
                f"   Файл:   {rpy_path}\n"
                f"   Узлов:  {len(self.graph.nodes)}"
            )
        return f"❌ Ошибка экспорта Ren'Py:\n{msg}"

    # ══════════════════════════════════════════════════════════════════════════
    #  СХЕМЫ ИНСТРУМЕНТОВ (JSON Schema)
    # ══════════════════════════════════════════════════════════════════════════

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Возвращает полный список инструментов в формате MCP tools/list."""
        return [
            # ── Проект ────────────────────────────────────────────────────────
            {
                "name": "de_load_project",
                "description": "Загрузить файл проекта Dialogue Engine (.json).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Абсолютный путь к файлу .json (если пуст — открывает последний проект)",
                        }
                    },
                },
            },
            {
                "name": "de_save_project",
                "description": "Сохранить текущий граф на диск (с резервной копией).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_path": {
                            "type": "string",
                            "description": "Путь для сохранения (если пуст — перезаписывает текущий файл)",
                        }
                    },
                },
            },
            {
                "name": "de_reload_server",
                "description": "Перезапустить MCP-сервер (применяет обновления кода).",
                "inputSchema": {"type": "object", "properties": {}},
            },
            # ── Анализ ────────────────────────────────────────────────────────
            {
                "name": "de_get_stats",
                "description": (
                    "Сводная статистика открытого проекта: число узлов, связей, "
                    "распределение по типам, персонажи, корни, листья и изолированные узлы."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "de_get_characters",
                "description": (
                    "Список всех уникальных персонажей со счётчиком реплик и цветом "
                    "заголовка (из custom_data или таблицы по умолчанию)."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "de_find_leaf_endpoints",
                "description": (
                    "Найти все листья графа — точки, где сюжетные ветки обрываются. "
                    "Идеально для продолжения сценария."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "de_get_node",
                "description": "Получить полную информацию об узле (текст, тип, координаты, входящие и исходящие связи).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "ID узла"}
                    },
                    "required": ["node_id"],
                },
            },
            {
                "name": "de_search_nodes",
                "description": "Поиск узлов по тексту, имени персонажа или типу узла.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query":     {"type": "string",  "description": "Подстрока поиска в тексте или заголовке"},
                        "character": {"type": "string",  "description": "Имя персонажа"},
                        "node_type": {"type": "string",  "description": "Тип: story | choice | condition | music | media | label"},
                        "limit":     {"type": "integer", "description": "Максимум результатов (по умолчанию 20)"},
                    },
                },
            },
            {
                "name": "de_trace_branch",
                "description": (
                    "Трассировка диалоговой ветки от заданного узла (или со всех корней) "
                    "в виде читаемого сценария с развилками."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "start_node_id": {"type": "string",  "description": "ID стартового узла (если пуст — от всех корней)"},
                        "max_depth":     {"type": "integer", "description": "Максимальная глубина (по умолчанию 30)"},
                    },
                },
            },
            # ── Создание узлов ────────────────────────────────────────────────
            {
                "name": "de_add_story_node",
                "description": (
                    "Добавить новую реплику персонажа или нарратив (#Сцена). "
                    "Координаты X/Y вычисляются автоматически справа от родителя."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "character":       {"type": "string",  "description": "Имя спикера или '#Сцена' для нарратива"},
                        "content":         {"type": "string",  "description": "Текст реплики или описание сцены"},
                        "connect_from_id": {"type": "string",  "description": "ID родительского узла (опционально)"},
                        "connect_out_idx": {"type": "integer", "description": "Индекс выхода родителя (по умолчанию 0)"},
                        "x":               {"type": "number",  "description": "Координата X"},
                        "y":               {"type": "number",  "description": "Координата Y"},
                        "custom_data":     {"type": "object",  "description": "Доп. данные узла (например header_text_color)"},
                        "auto_save":       {"type": "boolean", "description": "Сохранить после создания (по умолчанию true)"},
                    },
                    "required": ["character", "content"],
                },
            },
            {
                "name": "de_add_choice_node",
                "description": "Создать узел выбора с несколькими вариантами. Каждый вариант — отдельный исходящий порт.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title":           {"type": "string",  "description": "Заголовок блока выбора"},
                        "choices": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Список текстов вариантов выбора",
                        },
                        "connect_from_id": {"type": "string",  "description": "ID родительского узла (опционально)"},
                        "connect_out_idx": {"type": "integer", "description": "Индекс выхода родителя (по умолчанию 0)"},
                        "x":               {"type": "number",  "description": "Координата X"},
                        "y":               {"type": "number",  "description": "Координата Y"},
                        "auto_save":       {"type": "boolean", "description": "Сохранить после создания (по умолчанию true)"},
                    },
                    "required": ["choices"],
                },
            },
            {
                "name": "de_add_condition_node",
                "description": (
                    "Создать узел проверки условия (напр. 'violant_river == 1'). "
                    "Выход 0 = True, Выход 1 = False/Else."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "condition":       {"type": "string",  "description": "Выражение условия"},
                        "title":           {"type": "string",  "description": "Заголовок (по умолчанию 'Условие')"},
                        "connect_from_id": {"type": "string",  "description": "ID родительского узла (опционально)"},
                        "connect_out_idx": {"type": "integer", "description": "Индекс выхода родителя (по умолчанию 0)"},
                        "x":               {"type": "number",  "description": "Координата X"},
                        "y":               {"type": "number",  "description": "Координата Y"},
                        "auto_save":       {"type": "boolean", "description": "Сохранить после создания (по умолчанию true)"},
                    },
                    "required": ["condition"],
                },
            },
            {
                "name": "de_add_music_node",
                "description": "Создать узел музыки/звука и подключить его в граф (можно вставить между двумя узлами).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "music_file":      {"type": "string",  "description": "Путь к аудиофайлу (напр. 'music/theme.mp3')"},
                        "title":           {"type": "string",  "description": "Название узла"},
                        "music_mode": {
                            "type": "string",
                            "enum": ["bg", "sfx", "voice", "stop"],
                            "description": "bg=фон, sfx=эффект, voice=голос, stop=стоп",
                        },
                        "connect_from_id": {"type": "string",  "description": "ID родительского узла"},
                        "connect_out_idx": {"type": "integer", "description": "Индекс выхода родителя"},
                        "connect_to_id":   {"type": "string",  "description": "Вставить между connect_from_id и этим узлом"},
                        "fadein":          {"type": "number",  "description": "Нарастание громкости (секунды)"},
                        "fadeout":         {"type": "number",  "description": "Затухание (секунды)"},
                        "auto_save":       {"type": "boolean", "description": "Сохранить после создания (по умолчанию true)"},
                    },
                    "required": ["music_file"],
                },
            },
            {
                "name": "de_bulk_add_nodes",
                "description": (
                    "Массово создать несколько узлов за один вызов. "
                    "Каждый элемент списка — словарь с обязательным полем «type» "
                    "(story|choice|condition|music) и параметрами соответствующего инструмента."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "nodes": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Список дескрипторов узлов",
                        },
                        "auto_save": {"type": "boolean", "description": "Сохранить после всех операций (по умолчанию true)"},
                    },
                    "required": ["nodes"],
                },
            },
            # ── Редактирование ────────────────────────────────────────────────
            {
                "name": "de_update_node",
                "description": "Изменить текст, спикера, тип, координаты или custom_data существующего узла.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id":           {"type": "string",  "description": "ID изменяемого узла"},
                        "character":         {"type": "string",  "description": "Новый спикер"},
                        "title":             {"type": "string",  "description": "Новый заголовок"},
                        "content":           {"type": "string",  "description": "Новый текст"},
                        "node_type":         {"type": "string",  "description": "Новый тип узла"},
                        "x":                 {"type": "number",  "description": "Новая координата X"},
                        "y":                 {"type": "number",  "description": "Новая координата Y"},
                        "header_text_color": {"type": "string",  "description": "Цвет имени персонажа в hex"},
                        "custom_data":       {"type": "object",  "description": "Поля для слияния в custom_data"},
                        "auto_save":         {"type": "boolean", "description": "Сохранить после изменения"},
                    },
                    "required": ["node_id"],
                },
            },
            {
                "name": "de_move_node",
                "description": "Переместить узел на абсолютные координаты или сдвинуть на delta_x / delta_y.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string",  "description": "ID узла"},
                        "x":       {"type": "number",  "description": "Новая абсолютная координата X"},
                        "y":       {"type": "number",  "description": "Новая абсолютная координата Y"},
                        "delta_x": {"type": "number",  "description": "Смещение по X"},
                        "delta_y": {"type": "number",  "description": "Смещение по Y"},
                        "auto_save": {"type": "boolean"},
                    },
                    "required": ["node_id"],
                },
            },
            {
                "name": "de_duplicate_node",
                "description": "Создать копию узла без связей, сдвинув по X (по умолчанию +240px).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id":  {"type": "string",  "description": "ID исходного узла"},
                        "offset_x": {"type": "number",  "description": "Смещение по X (по умолчанию 240)"},
                        "offset_y": {"type": "number",  "description": "Смещение по Y (по умолчанию 0)"},
                        "auto_save": {"type": "boolean"},
                    },
                    "required": ["node_id"],
                },
            },
            {
                "name": "de_delete_node",
                "description": "Удалить узел и все связанные с ним входящие / исходящие линии.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id":  {"type": "string",  "description": "ID удаляемого узла"},
                        "auto_save": {"type": "boolean"},
                    },
                    "required": ["node_id"],
                },
            },
            # ── Связи ─────────────────────────────────────────────────────────
            {
                "name": "de_connect_nodes",
                "description": "Соединить выход одного узла со входом другого.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_node": {"type": "string",  "description": "ID исходного узла"},
                        "out_idx":   {"type": "integer", "description": "Индекс порта выхода (0 по умолчанию)"},
                        "to_node":   {"type": "string",  "description": "ID целевого узла"},
                        "auto_save": {"type": "boolean"},
                    },
                    "required": ["from_node", "to_node"],
                },
            },
            {
                "name": "de_disconnect_nodes",
                "description": "Удалить связь между узлами.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_node": {"type": "string",  "description": "ID исходного узла"},
                        "out_idx":   {"type": "integer", "description": "Индекс выхода (по умолчанию 0)"},
                        "to_node":   {"type": "string",  "description": "ID целевого узла (опционально)"},
                        "auto_save": {"type": "boolean"},
                    },
                    "required": ["from_node"],
                },
            },
            # ── Валидация и экспорт ───────────────────────────────────────────
            {
                "name": "de_validate_graph",
                "description": (
                    "Проверить целостность графа: битые ссылки, недостижимые узлы, "
                    "непривязанные ветки выбора и условия."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "de_export_renpy",
                "description": "Экспортировать граф в script.rpy для Ren'Py Visual Novel Engine.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "output_dir": {"type": "string", "description": "Директория game/ проекта Ren'Py"}
                    },
                },
            },
        ]

    # ══════════════════════════════════════════════════════════════════════════
    #  ПРОМПТЫ (prompts/*)
    # ══════════════════════════════════════════════════════════════════════════

    _PROMPTS = [
        {
            "name": "continue_scene",
            "description": "Продолжить ближайшую незавершённую сцену сценария.",
            "arguments": [
                {"name": "leaf_id", "description": "ID конечного узла, от которого продолжать", "required": False}
            ],
        },
        {
            "name": "review_branch",
            "description": "Проанализировать диалоговую ветку и дать рекомендации по улучшению.",
            "arguments": [
                {"name": "start_node_id", "description": "ID стартового узла ветки", "required": True}
            ],
        },
        {
            "name": "add_choice_branch",
            "description": "Добавить узел выбора игрока и создать скелет для каждой ветки.",
            "arguments": [
                {"name": "parent_id",  "description": "ID узла-родителя",             "required": True},
                {"name": "num_choices","description": "Количество вариантов (2–5)",    "required": False},
            ],
        },
    ]

    def handle_prompts_list(self, req_id: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": self._PROMPTS}}

    def handle_prompts_get(self, req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "")
        prompt = next((p for p in self._PROMPTS if p["name"] == name), None)
        if not prompt:
            return make_error_response(req_id, -32602, f"Промпт '{name}' не найден.")

        arguments = params.get("arguments", {})

        if name == "continue_scene":
            leaf_id = arguments.get("leaf_id")
            if leaf_id:
                context = self.tool_get_node({"node_id": leaf_id})
            else:
                context = self.tool_find_leaf_endpoints({})
            text = (
                "Проанализируй незавершённые ветки сценария и продолжи их, "
                "создавая новые реплики через de_add_story_node.\n\n"
                f"Контекст:\n{context}"
            )

        elif name == "review_branch":
            start_id = arguments.get("start_node_id", "")
            branch = self.tool_trace_branch({"start_node_id": start_id, "max_depth": 20})
            text = (
                "Проанализируй диалоговую ветку и дай конкретные рекомендации: "
                "темп, характер персонажей, логические несоответствия, "
                "незавершённые сюжетные линии.\n\n"
                f"Ветка:\n{branch}"
            )

        elif name == "add_choice_branch":
            parent_id = arguments.get("parent_id", "")
            num = int(arguments.get("num_choices", 3))
            parent_info = self.tool_get_node({"node_id": parent_id})
            text = (
                f"Создай узел выбора с {num} вариантами после узла [{parent_id}], "
                f"затем для каждой ветки добавь минимум 2 реплики.\n\n"
                f"Контекст родителя:\n{parent_info}"
            )
        else:
            text = f"Выполни задачу: {name}"

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "description": prompt["description"],
                "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
            },
        }

    # ══════════════════════════════════════════════════════════════════════════
    #  JSON-RPC МАРШРУТИЗАТОР
    # ══════════════════════════════════════════════════════════════════════════

    def handle_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        # ── Инициализация ──────────────────────────────────────────────────────
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools":   {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name":        SERVER_NAME,
                        "version":     SERVER_VERSION,
                        "description": SERVER_DESCRIPTION,
                    },
                },
            }

        if method == "notifications/initialized":
            return None  # Уведомление, ответ не нужен

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # ── Инструменты ────────────────────────────────────────────────────────
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.get_tool_definitions()},
            }

        if method == "tools/call":
            name: str = params.get("name", "")
            tool_args: Dict[str, Any] = params.get("arguments") or {}

            handler_name = (
                f"tool_{name[3:]}"   # de_foo → tool_foo
                if name.startswith("de_")
                else f"tool_{name}"
            )
            handler = getattr(self, handler_name, None)

            if not handler or not callable(handler):
                return make_tool_result(
                    req_id, f"❌ Неизвестный инструмент: '{name}'", is_error=True
                )

            try:
                result_text = handler(tool_args)
                return make_tool_result(req_id, str(result_text))
            except Exception:
                tb = traceback.format_exc()
                log.error("Ошибка в '%s': %s", name, tb)
                return make_tool_result(
                    req_id,
                    f"❌ Ошибка при выполнении '{name}':\n{tb}",
                    is_error=True,
                )

        # ── Ресурсы ────────────────────────────────────────────────────────────
        if method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": [
                        {
                            "uri": "de://project/active",
                            "name": "Активный проект Dialogue Engine",
                            "mimeType": "application/json",
                        }
                    ]
                },
            }

        if method == "resources/read":
            uri = params.get("uri", "")
            if uri == "de://project/active":
                content = json.dumps(
                    self.graph.to_project_data().to_dict(), ensure_ascii=False
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {"uri": uri, "mimeType": "application/json", "text": content}
                        ]
                    },
                }
            return make_error_response(req_id, -32602, f"Неизвестный URI: '{uri}'")

        # ── Промпты ────────────────────────────────────────────────────────────
        if method == "prompts/list":
            return self.handle_prompts_list(req_id)

        if method == "prompts/get":
            return self.handle_prompts_get(req_id, params)

        # ── Отмена (fire-and-forget, no response) ─────────────────────────────
        if method == "$/cancelRequest":
            return None

        # ── Неизвестный метод ─────────────────────────────────────────────────
        if req_id is not None:
            return make_error_response(req_id, -32601, f"Метод не поддерживается: '{method}'")
        return None

    # ══════════════════════════════════════════════════════════════════════════
    #  ТРАНСПОРТНЫЙ УРОВЕНЬ (stdio)
    # ══════════════════════════════════════════════════════════════════════════

    def run_stdio(self) -> None:
        """
        Главный цикл транспорта stdio.
        Поддерживает:
          • newline-delimited JSON (raw NDJSON)
          • Content-Length framing (LSP / HTTP-like headers)
        """
        log.info("Dialogue Engine MCP Server v%s запущен (stdio).", SERVER_VERSION)

        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break  # EOF — клиент отключился

                stripped = line.strip()
                if not stripped:
                    continue

                # Content-Length framing
                if stripped.lower().startswith("content-length:"):
                    length = int(stripped.split(":", 1)[1].strip())
                    # Поглощаем заголовки до пустой строки
                    while True:
                        hdr = sys.stdin.readline().strip()
                        if not hdr:
                            break
                    body = sys.stdin.read(length)
                    req = json.loads(body)
                else:
                    req = json.loads(stripped)

                resp = self.handle_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                    sys.stdout.flush()

            except (KeyboardInterrupt, SystemExit):
                log.info("Сервер завершает работу.")
                break
            except json.JSONDecodeError as exc:
                log.warning("Невалидный JSON: %s", exc)
            except Exception:
                log.error("Необработанное исключение:\n%s", traceback.format_exc())


# ═════════════════════════════════════════════════════════════════════════════
#  Точка входа
# ═════════════════════════════════════════════════════════════════════════════

def main() -> None:
    initial_path = (
        sys.argv[1]
        if len(sys.argv) > 1 and sys.argv[1].endswith(".json")
        else None
    )
    server = DialogueEngineMCPServer(initial_project_path=initial_path)
    server.run_stdio()


if __name__ == "__main__":
    main()

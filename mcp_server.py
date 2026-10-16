"""
Dialogue Engine - Model Context Protocol (MCP) Server.
Позволяет AI-ассистентам (Antigravity, Claude, Cursor) напрямую взаимодействовать
с графом диалогов, создавать реплики, проверять ветки и экспортировать в Ren'Py.
Поддерживает стандарт MCP (2024-11-05) через stdio.
"""

from __future__ import annotations
import json
import os
import sys
import traceback
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

# Устанавливаем UTF-8 для корректной передачи кириллицы
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Добавляем корень Dialogue Engine в sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from core.models import ConnectionData, NodeData, ProjectData
from core.graph import GraphModel
from core.serialization import ProjectSerializer
from export.renpy_exporter import RenPyExporter


def log_debug(msg: str) -> None:
    sys.stderr.write(f"[DE-MCP] {msg}\n")
    sys.stderr.flush()


def notify_live_editor(event: Dict[str, Any]) -> None:
    """Отправляет событие в реальном времени в запущенный редактор (порт 48123)."""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            s.connect(("127.0.0.1", 48123))
            payload = json.dumps(event, ensure_ascii=False) + "\n"
            s.sendall(payload.encode("utf-8"))
    except Exception:
        # Редактор закрыт или не слушает порт — нормально, изменения сохранены в JSON
        pass


class DialogueEngineMCPServer:
    """Сервер MCP для управления Dialogue Engine."""

    def __init__(self, initial_project_path: Optional[str] = None):
        self.project_path: Optional[str] = None
        self.graph = GraphModel()
        self.exporter = RenPyExporter()

        # Автопоиск проекта по умолчанию
        default_candidates = [
            initial_project_path,
            os.environ.get("DE_PROJECT_PATH"),
            r"D:\projects\Violant\game\violant.json",
            os.path.join(SCRIPT_DIR, "violant.json")
        ]
        for candidate in default_candidates:
            if candidate and os.path.exists(candidate):
                self.load_project(candidate)
                break

    def load_project(self, file_path: str) -> Dict[str, Any]:
        """Загружает файл проекта."""
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        proj_data = ProjectSerializer.load_from_file(file_path)
        self.graph.load_from_project_data(proj_data)
        self.project_path = file_path
        log_debug(f"Loaded project from {file_path} ({len(self.graph.nodes)} nodes)")
        return {
            "path": file_path,
            "title": proj_data.metadata.title,
            "nodes_count": len(self.graph.nodes),
            "connections_count": len(self.graph.connections)
        }

    def save_project(self, target_path: Optional[str] = None) -> str:
        """Сохраняет текущий проект на диск."""
        path = target_path or self.project_path
        if not path:
            raise ValueError("Путь для сохранения не указан и нет открытого проекта.")
        path = os.path.abspath(path)
        proj_data = self.graph.to_project_data(title="Dialogue Engine Project")
        ProjectSerializer.save_to_file(proj_data, path, create_backup=True)
        self.project_path = path
        log_debug(f"Saved project to {path}")
        return path

    # --- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ---

    def _auto_position(self, parent_id: Optional[str], out_idx: int = 0) -> Tuple[float, float]:
        """Умное позиционирование нового узла справа от родительского."""
        if parent_id:
            parent = self.graph.get_node(parent_id)
            if parent:
                new_x = parent.x + parent.width + 60.0
                new_y = parent.y + (out_idx * 130.0)
                return new_x, new_y

        # Фолбэк: если родителей нет, ищем максимальный X
        if self.graph.nodes:
            max_x = max(n.x for n in self.graph.nodes)
            return max_x + 240.0, 100.0
        return 100.0, 100.0

    # --- ОБРАБОТЧИКИ ИНСТРУМЕНТОВ ---

    def tool_get_stats(self, args: Dict[str, Any]) -> str:
        nodes = self.graph.nodes
        conns = self.graph.connections
        types_count: Dict[str, int] = {}
        speakers: Dict[str, int] = {}

        for n in nodes:
            t = n.node_type
            types_count[t] = types_count.get(t, 0) + 1
            if t == "story":
                speaker = n.title or "Без автора"
                speakers[speaker] = speakers.get(speaker, 0) + 1

        target_ids = {c.to_node for c in conns}
        source_ids = {c.from_node for c in conns}
        roots = [n.id for n in nodes if n.id not in target_ids]
        leaves = [n.id for n in nodes if n.id not in source_ids]
        unreachable = [n.id for n in self.graph.get_unreachable_nodes()]

        lines = [
            f"=== СТАТИСТИКА ПРОЕКТА ===",
            f"Текущий файл: {self.project_path or 'Не сохранен'}",
            f"Всего узлов: {len(nodes)}",
            f"Всего связей: {len(conns)}",
            f"\nРаспределение по типам узлов:",
        ]
        for t, count in sorted(types_count.items(), key=lambda x: -x[1]):
            lines.append(f"  - {t}: {count}")

        lines.append(f"\nРеплики персонажей (story):")
        for spk, count in sorted(speakers.items(), key=lambda x: -x[1]):
            lines.append(f"  - {spk}: {count}")

        lines.append(f"\nКорневые узлы (старты): {roots}")
        lines.append(f"Конечные узлы (точки обрыва / листья): {len(leaves)} шт.")
        lines.append(f"Недостижимые узлы: {len(unreachable)} шт.")

        return "\n".join(lines)

    def tool_find_leaf_endpoints(self, args: Dict[str, Any]) -> str:
        """Находит все листья графа (точки, где ветки заканчиваются)."""
        nodes = {n.id: n for n in self.graph.nodes}
        source_ids = {c.from_node for c in self.graph.connections}
        leaves = [n for nid, n in nodes.items() if nid not in source_ids]

        if not leaves:
            return "В графе нет конечных точек без исходящих связей (все узлы имеют продолжение или граф пуст)."

        res = [f"Найдено {len(leaves)} конечных точек (где сюжет останавливается):\n"]
        for idx, l in enumerate(leaves, 1):
            incoming = self.graph.get_incoming(l.id)
            prev_info = f"<- от {incoming[0].from_node} (выход {incoming[0].out_idx})" if incoming else "<- нет входящих"
            res.append(f"#{idx} [ID: {l.id}] ({l.node_type}) {l.title} {prev_info}")
            res.append(f"     Текст: {l.content.strip()[:140]}")
            res.append("")
        return "\n".join(res)

    def tool_get_node(self, args: Dict[str, Any]) -> str:
        node_id = str(args.get("node_id", ""))
        node = self.graph.get_node(node_id)
        if not node:
            return f"Ошибка: Узел с ID '{node_id}' не найден."

        outgoing = self.graph.get_outgoing(node_id)
        incoming = self.graph.get_incoming(node_id)

        info = {
            "id": node.id,
            "title": node.title,
            "type": node.node_type,
            "content": node.content,
            "x": node.x,
            "y": node.y,
            "custom_data": node.custom_data,
            "incoming": [{"from": c.from_node, "out_idx": c.out_idx} for c in incoming],
            "outgoing": [{"out_idx": c.out_idx, "to": c.to_node} for c in sorted(outgoing, key=lambda x: x.out_idx)]
        }
        return json.dumps(info, ensure_ascii=False, indent=2)

    def tool_search_nodes(self, args: Dict[str, Any]) -> str:
        query = str(args.get("query", "")).lower()
        character = str(args.get("character", "")).lower()
        node_type = str(args.get("node_type", "")).lower()
        limit = int(args.get("limit", 20))

        matches = []
        for n in self.graph.nodes:
            if character and character not in n.title.lower():
                continue
            if node_type and node_type != n.node_type.lower():
                continue
            if query and (query not in n.content.lower() and query not in n.title.lower()):
                continue
            matches.append(n)
            if len(matches) >= limit:
                break

        if not matches:
            return "Узлов по заданному критерию не найдено."

        lines = [f"Найдено узлов: {len(matches)} (показаны первые {limit}):\n"]
        for m in matches:
            preview = m.content.replace("\n", " ").strip()[:90]
            lines.append(f"- [{m.id}] ({m.node_type}) {m.title}: {preview}")
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

        output_lines = []

        def trace(curr_id: str, depth: int, visited: Set[str]):
            if depth > max_depth or curr_id in visited:
                return
            visited.add(curr_id)
            n = nodes_map.get(curr_id)
            if not n:
                return

            indent = "  " * depth
            preview = n.content.replace("\n", " ").strip()
            output_lines.append(f"{indent}[{n.id}] {n.title}: {preview}")

            conns = sorted(out_map.get(curr_id, []), key=lambda c: c.out_idx)
            for c in conns:
                if len(conns) > 1:
                    output_lines.append(f"{indent}  ↳ [Выход #{c.out_idx}]")
                trace(c.to_node, depth + 1, visited.copy())

        for sid in start_ids:
            output_lines.append(f"=== ТРАССИРОВКА ОТ УЗЛА {sid} ===")
            trace(sid, 0, set())
            output_lines.append("")

        return "\n".join(output_lines)

    def tool_add_story_node(self, args: Dict[str, Any]) -> str:
        character = str(args.get("character", "#Сцена"))
        content = str(args.get("content", ""))
        connect_from_id = args.get("connect_from_id")
        connect_out_idx = int(args.get("connect_out_idx", 0))
        auto_save = bool(args.get("auto_save", True))

        x = args.get("x")
        y = args.get("y")
        if x is None or y is None:
            auto_x, auto_y = self._auto_position(connect_from_id, connect_out_idx)
            x = x if x is not None else auto_x
            y = y if y is not None else auto_y

        # Автоматическое определение цвета заголовка персонажа
        custom_data = dict(args.get("custom_data", {}))
        if "header_text_color" not in custom_data:
            found_color = None
            for n in self.graph.nodes:
                if n.title.strip() == character.strip() and "header_text_color" in n.custom_data:
                    found_color = n.custom_data["header_text_color"]
                    break

            if not found_color:
                DEFAULT_CHAR_COLORS = {
                    "Ривер": "#0080ff",
                    "Ника": "#00ffff",
                    "Джен": "#ffff00",
                    "Энджи": "#c060f8",
                    "???": "#8000ff",
                    "Телевизор": "#66ccff"
                }
                found_color = DEFAULT_CHAR_COLORS.get(character.strip())

            if found_color:
                custom_data["header_text_color"] = found_color

        node_id = str(uuid.uuid4().int)[:13]
        new_node = NodeData(
            id=node_id,
            x=float(x),
            y=float(y),
            title=character,
            content=content,
            node_type="story",
            mode="standard",
            custom_data=custom_data
        )
        self.graph.add_node(new_node)

        connected = False
        if connect_from_id and connect_from_id in {n.id for n in self.graph.nodes}:
            connected = self.graph.add_connection(str(connect_from_id), connect_out_idx, node_id)

        saved = ""
        if auto_save and self.project_path:
            self.save_project()
            saved = f" и сохранен в {os.path.basename(self.project_path)}"

        # Уведомляем запущенный редактор для отрисовки в реальном времени
        conn_dict = {"from": str(connect_from_id), "out_idx": connect_out_idx, "to": node_id} if connect_from_id else None
        notify_live_editor({
            "action": "node_spawn",
            "node": new_node.to_dict(),
            "connection": conn_dict,
            "focus": True
        })

        return f"Узел {node_id} ('{character}') успешно создан{saved}. Соединен с {connect_from_id}: {connected}."

    def tool_add_choice_node(self, args: Dict[str, Any]) -> str:
        title = str(args.get("title", "Выбор"))
        choices = args.get("choices", [])
        if isinstance(choices, str):
            choices = [c.strip() for c in choices.split("\n") if c.strip()]
        content = "\n".join(choices)

        connect_from_id = args.get("connect_from_id")
        connect_out_idx = int(args.get("connect_out_idx", 0))
        auto_save = bool(args.get("auto_save", True))

        x = args.get("x")
        y = args.get("y")
        if x is None or y is None:
            auto_x, auto_y = self._auto_position(connect_from_id, connect_out_idx)
            x = x if x is not None else auto_x
            y = y if y is not None else auto_y

        node_id = str(uuid.uuid4().int)[:13]
        new_node = NodeData(
            id=node_id,
            x=float(x),
            y=float(y),
            title=title,
            content=content,
            node_type="choice",
            mode="standard"
        )
        self.graph.add_node(new_node)

        if connect_from_id:
            self.graph.add_connection(str(connect_from_id), connect_out_idx, node_id)

        if auto_save and self.project_path:
            self.save_project()

        conn_dict = {"from": str(connect_from_id), "out_idx": connect_out_idx, "to": node_id} if connect_from_id else None
        notify_live_editor({
            "action": "node_spawn",
            "node": new_node.to_dict(),
            "connection": conn_dict,
            "focus": True
        })

        return (
            f"Узел выбора {node_id} ('{title}') создан с {len(choices)} вариантами.\n"
            f"Выходы для подключения:\n" +
            "\n".join(f"  - out_idx {i}: '{opt}'" for i, opt in enumerate(choices))
        )

    def tool_add_condition_node(self, args: Dict[str, Any]) -> str:
        condition = str(args.get("condition", ""))
        title = str(args.get("title", "Условие"))
        connect_from_id = args.get("connect_from_id")
        connect_out_idx = int(args.get("connect_out_idx", 0))
        auto_save = bool(args.get("auto_save", True))

        x = args.get("x")
        y = args.get("y")
        if x is None or y is None:
            auto_x, auto_y = self._auto_position(connect_from_id, connect_out_idx)
            x = x if x is not None else auto_x
            y = y if y is not None else auto_y

        node_id = str(uuid.uuid4().int)[:13]
        new_node = NodeData(
            id=node_id,
            x=float(x),
            y=float(y),
            title=title,
            content=condition,
            node_type="condition",
            mode="standard"
        )
        self.graph.add_node(new_node)

        if connect_from_id:
            self.graph.add_connection(str(connect_from_id), connect_out_idx, node_id)

        if auto_save and self.project_path:
            self.save_project()

        conn_dict = {"from": str(connect_from_id), "out_idx": connect_out_idx, "to": node_id} if connect_from_id else None
        notify_live_editor({
            "action": "node_spawn",
            "node": new_node.to_dict(),
            "connection": conn_dict,
            "focus": True
        })

        return (
            f"Узел условия {node_id} ('{condition}') успешно создан.\n"
            f"Выходы:\n"
            f"  - out_idx 0: ИСТИНА (True)\n"
            f"  - out_idx 1: ЛОЖЬ (False / Else)"
        )

    def tool_connect_nodes(self, args: Dict[str, Any]) -> str:
        from_node = str(args.get("from_node", ""))
        to_node = str(args.get("to_node", ""))
        out_idx = int(args.get("out_idx", 0))
        auto_save = bool(args.get("auto_save", True))

        if from_node not in {n.id for n in self.graph.nodes}:
            return f"Ошибка: Исходный узел '{from_node}' не существует."
        if to_node not in {n.id for n in self.graph.nodes}:
            return f"Ошибка: Целевой узел '{to_node}' не существует."

        success = self.graph.add_connection(from_node, out_idx, to_node)
        if not success:
            return f"Ошибка связывания узлов {from_node} -> {to_node}."

        if auto_save and self.project_path:
            self.save_project()

        notify_live_editor({
            "action": "connection_add",
            "connection": {"from": from_node, "out_idx": out_idx, "to": to_node}
        })

        return f"Связь успешно создана: [{from_node}] (выход {out_idx}) -> [{to_node}]."

    def tool_disconnect_nodes(self, args: Dict[str, Any]) -> str:
        from_node = str(args.get("from_node", ""))
        out_idx = int(args.get("out_idx", 0))
        to_node = args.get("to_node")
        auto_save = bool(args.get("auto_save", True))

        removed = self.graph.remove_connection(from_node, out_idx, str(to_node) if to_node else None)
        if auto_save and self.project_path:
            self.save_project()
        return f"Связи удалены: {removed}."

    def tool_update_node(self, args: Dict[str, Any]) -> str:
        node_id = str(args.get("node_id", ""))
        node = self.graph.get_node(node_id)
        if not node:
            return f"Ошибка: Узел '{node_id}' не найден."

        if "character" in args:
            node.title = str(args["character"])
        if "title" in args:
            node.title = str(args["title"])
        if "content" in args:
            node.content = str(args["content"])
        if "node_type" in args:
            node.node_type = str(args["node_type"])
        if "x" in args:
            node.x = float(args["x"])
        if "y" in args:
            node.y = float(args["y"])
        if "custom_data" in args and isinstance(args["custom_data"], dict):
            node.custom_data.update(args["custom_data"])
        if "header_text_color" in args:
            node.custom_data["header_text_color"] = str(args["header_text_color"])
        elif ("character" in args or "title" in args) and "header_text_color" not in node.custom_data:
            char_name = node.title.strip()
            found_color = None
            for n in self.graph.nodes:
                if n.title.strip() == char_name and "header_text_color" in n.custom_data:
                    found_color = n.custom_data["header_text_color"]
                    break
            if not found_color:
                DEFAULT_CHAR_COLORS = {
                    "Ривер": "#0080ff",
                    "Ника": "#00ffff",
                    "Джен": "#ffff00",
                    "Энджи": "#c060f8",
                    "???": "#8000ff",
                    "Телевизор": "#66ccff"
                }
                found_color = DEFAULT_CHAR_COLORS.get(char_name)
            if found_color:
                node.custom_data["header_text_color"] = found_color

        auto_save = bool(args.get("auto_save", True))
        if auto_save and self.project_path:
            self.save_project()

        notify_live_editor({
            "action": "node_update",
            "node_id": node_id,
            "character": node.title,
            "content": node.content,
            "x": node.x,
            "y": node.y,
            "custom_data": node.custom_data,
            "header_text_color": node.custom_data.get("header_text_color")
        })

        return f"Узел {node_id} успешно обновлен."

    def tool_delete_node(self, args: Dict[str, Any]) -> str:
        node_id = str(args.get("node_id", ""))
        removed = self.graph.remove_node(node_id)
        if not removed:
            return f"Ошибка: Узел '{node_id}' не найден."

        if auto_save and self.project_path:
            self.save_project()

        notify_live_editor({
            "action": "node_delete",
            "node_id": node_id
        })

        return f"Узел {node_id} ('{removed.title}') и все его связи удалены."

    def tool_validate_graph(self, args: Dict[str, Any]) -> str:
        issues = self.graph.validate()
        if not issues:
            return "✅ Проверка графа пройдена: ошибок и несогласованностей не обнаружено."

        lines = [f"Найдено замечаний по графу: {len(issues)}:\n"]
        for issue in issues:
            nid_str = f"[Узел {issue.node_id}] " if issue.node_id else ""
            lines.append(f"• [{issue.level.upper()}] {nid_str}{issue.message}")
        return "\n".join(lines)

    def tool_export_renpy(self, args: Dict[str, Any]) -> str:
        output_dir = args.get("output_dir")
        if not output_dir:
            if self.project_path:
                output_dir = os.path.dirname(self.project_path)
            else:
                output_dir = r"D:\projects\Violant\game"

        output_dir = os.path.abspath(output_dir)
        proj_data = self.graph.to_project_data()
        success, msg = self.exporter.export(proj_data, output_dir)
        if success:
            rpy_path = os.path.join(output_dir, "script.rpy")
            return f"✅ Экспорт в Ren'Py успешно завершен!\nФайл: {rpy_path}\nУзлов экспортировано: {len(self.graph.nodes)}"
        return f"❌ Ошибка при экспорте в Ren'Py:\n{msg}"

    def tool_load_project(self, args: Dict[str, Any]) -> str:
        file_path = args.get("file_path") or self.project_path or r"D:\projects\Violant\game\violant.json"
        res = self.load_project(file_path)
        return f"✅ Проект успешно загружен: {res['path']}\nУзлов: {res['nodes_count']}, Связей: {res['connections_count']}"

    def tool_save_project(self, args: Dict[str, Any]) -> str:
        target_path = args.get("target_path") or self.project_path
        path = self.save_project(target_path)
        return f"✅ Проект успешно сохранен в: {path}"

    def tool_reload_server(self, args: Dict[str, Any]) -> str:
        raise SystemExit(0)

    # --- MCP СПИСОК ИНСТРУМЕНТОВ ---

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "de_load_project",
                "description": "Загрузить или перезагрузить проект из указанного json файла.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Путь к файлу violant.json"}
                    }
                }
            },
            {
                "name": "de_save_project",
                "description": "Сохранить текущий граф проекта на диск.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_path": {"type": "string", "description": "Целевой путь (опционально)"}
                    }
                }
            },
            {
                "name": "de_reload_server",
                "description": "Перезапустить MCP сервер для применения изменений в коде.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "de_get_stats",
                "description": "Получить сводку открытого проекта Dialogue Engine (узлы, персонажи, конечные точки, переменные).",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "de_find_leaf_endpoints",
                "description": "Найти все конечные точки сценария (листья графа без исходящих связей), где сейчас останавливается сюжет.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "de_load_project",
                "description": "Загрузить файл сценария Dialogue Engine (.json).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Абсолютный или относительный путь к файлу .json"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "de_save_project",
                "description": "Сохранить текущий проект Dialogue Engine на диск.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Опциональный путь для сохранения (если не указан, перезаписывает текущий)"}
                    }
                }
            },
            {
                "name": "de_get_node",
                "description": "Получить полную информацию об узле по его ID (текст, автор, тип, входящие и исходящие связи).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "ID узла"}
                    },
                    "required": ["node_id"]
                }
            },
            {
                "name": "de_search_nodes",
                "description": "Поиск узлов по подстроке в тексте, имени персонажа или типу узла.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Подстрока поиска в тексте или заголовке"},
                        "character": {"type": "string", "description": "Имя персонажа/автора"},
                        "node_type": {"type": "string", "description": "Тип узла: story, choice, condition, media, music, label"},
                        "limit": {"type": "integer", "description": "Максимум результатов (по умолчанию 20)"}
                    }
                }
            },
            {
                "name": "de_trace_branch",
                "description": "Трассировка диалоговой ветки от заданного узла (или от начала) в виде читаемого сценария с развилками.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "start_node_id": {"type": "string", "description": "ID стартового узла (если не указан, начинает со всех корней)"},
                        "max_depth": {"type": "integer", "description": "Максимальная глубина (по умолчанию 30)"}
                    }
                }
            },
            {
                "name": "de_add_story_node",
                "description": "Добавить новую реплику персонажа или нарратив (#Сцена). Может сразу присоединить к предыдущему узлу.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "character": {"type": "string", "description": "Имя спикера (например, 'Ривер', 'Ника', 'Джен', '#Сцена')"},
                        "content": {"type": "string", "description": "Текст реплики или описания сцены"},
                        "connect_from_id": {"type": "string", "description": "Опциональный ID узла, от которого протянуть связь к новому узлу"},
                        "connect_out_idx": {"type": "integer", "description": "Индекс выхода на узле connect_from_id (по умолчанию 0)"},
                        "x": {"type": "number", "description": "Координата X (если не указана, вычисляется автоматически)"},
                        "y": {"type": "number", "description": "Координата Y (если не указана, вычисляется автоматически)"},
                        "auto_save": {"type": "boolean", "description": "Автоматически сохранить проект на диск (по умолчанию true)"}
                    },
                    "required": ["character", "content"]
                }
            },
            {
                "name": "de_add_choice_node",
                "description": "Создать узел интерактивного выбора игрока с несколькими вариантами ответов.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Заголовок выбора (по умолчанию 'Выбор')"},
                        "choices": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Список вариантов выбора для игрока"
                        },
                        "connect_from_id": {"type": "string", "description": "Опциональный ID узла, от которого протянуть связь"},
                        "connect_out_idx": {"type": "integer", "description": "Индекс выхода на connect_from_id (по умолчанию 0)"},
                        "x": {"type": "number", "description": "Координата X"},
                        "y": {"type": "number", "description": "Координата Y"},
                        "auto_save": {"type": "boolean", "description": "Автоматически сохранить проект (по умолчанию true)"}
                    },
                    "required": ["choices"]
                }
            },
            {
                "name": "de_add_condition_node",
                "description": "Создать узел проверки условия (например, 'violant_river == 1'). Выход 0 = True, Выход 1 = False/Else.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "condition": {"type": "string", "description": "Выражение условия, например 'violant_river == 1'"},
                        "title": {"type": "string", "description": "Заголовок (по умолчанию 'Условие')"},
                        "connect_from_id": {"type": "string", "description": "ID узла, от которого протянуть связь"},
                        "connect_out_idx": {"type": "integer", "description": "Индекс выхода на connect_from_id (по умолчанию 0)"},
                        "x": {"type": "number", "description": "Координата X"},
                        "y": {"type": "number", "description": "Координата Y"},
                        "auto_save": {"type": "boolean", "description": "Автоматически сохранить проект (по умолчанию true)"}
                    },
                    "required": ["condition"]
                }
            },
            {
                "name": "de_connect_nodes",
                "description": "Соединить выход одного узла со входом другого узла.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_node": {"type": "string", "description": "ID исходного узла"},
                        "out_idx": {"type": "integer", "description": "Индекс порта выхода (0 для обычных узлов, 0/1/2 для выбора)"},
                        "to_node": {"type": "string", "description": "ID целевого узла"},
                        "auto_save": {"type": "boolean", "description": "Автоматически сохранить проект (по умолчанию true)"}
                    },
                    "required": ["from_node", "to_node"]
                }
            },
            {
                "name": "de_disconnect_nodes",
                "description": "Удалить связь между узлами.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_node": {"type": "string", "description": "ID исходного узла"},
                        "out_idx": {"type": "integer", "description": "Индекс выхода (по умолчанию 0)"},
                        "to_node": {"type": "string", "description": "Опциональный целевой узел"},
                        "auto_save": {"type": "boolean", "description": "Автоматически сохранить проект"}
                    },
                    "required": ["from_node"]
                }
            },
            {
                "name": "de_update_node",
                "description": "Отредактировать текст, автора или тип существующего узла.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "ID узла для изменения"},
                        "character": {"type": "string", "description": "Новый спикер/заголовок"},
                        "content": {"type": "string", "description": "Новый текст"},
                        "node_type": {"type": "string", "description": "Новый тип узла"},
                        "x": {"type": "number", "description": "Новая координата X"},
                        "y": {"type": "number", "description": "Новая координата Y"},
                        "header_text_color": {"type": "string", "description": "Цвет имени персонажа в hex (например '#0080ff', '#00ffff')"},
                        "custom_data": {"type": "object", "description": "Дополнительные данные узла"},
                        "auto_save": {"type": "boolean", "description": "Автоматически сохранить проект"}
                    },
                    "required": ["node_id"]
                }
            },
            {
                "name": "de_delete_node",
                "description": "Удалить узел и все связанные с ним входящие и исходящие линии.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "ID удаляемого узла"},
                        "auto_save": {"type": "boolean", "description": "Автоматически сохранить проект"}
                    },
                    "required": ["node_id"]
                }
            },
            {
                "name": "de_validate_graph",
                "description": "Проверить граф сценария на логические ошибки, висячие концы, пустые ветки и циклы.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "de_export_renpy",
                "description": "Экспортировать текущий граф сценария напрямую в script.rpy для Ren'Py.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "output_dir": {"type": "string", "description": "Директория game проекта Ren'Py"}
                    }
                }
            }
        ]

    # --- JSON-RPC ОБРАБОТЧИК ---

    def handle_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        # Инициализация MCP
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False}
                    },
                    "serverInfo": {
                        "name": "dialogue-engine-mcp",
                        "version": "1.0.0"
                    }
                }
            }

        elif method == "notifications/initialized":
            # Уведомление об успешной инициализации от клиента
            return None

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # Список инструментов
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tool_definitions()
                }
            }

        # Вызов инструмента
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})

            handler_name = f"tool_{name.replace('de_', '')}" if name.startswith("de_") else f"tool_{name}"
            handler = getattr(self, handler_name, None)

            if not handler:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Неизвестный инструмент: '{name}'"}],
                        "isError": True
                    }
                }

            try:
                res_text = handler(args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": str(res_text)}],
                        "isError": False
                    }
                }
            except Exception as e:
                err_trace = traceback.format_exc()
                log_debug(f"Error in {name}: {err_trace}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Ошибка при выполнении '{name}': {str(e)}\n{err_trace}"}],
                        "isError": True
                    }
                }

        # Ресурсы
        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": [
                        {
                            "uri": "de://project/active",
                            "name": "Активный проект Dialogue Engine",
                            "mimeType": "application/json"
                        }
                    ]
                }
            }

        elif method == "resources/read":
            uri = params.get("uri")
            if uri == "de://project/active":
                content = json.dumps(self.graph.to_project_data().to_dict(), ensure_ascii=False)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": content
                            }
                        ]
                    }
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": f"Неизвестный URI ресурса: {uri}"}
            }

        # Неизвестный метод
        if req_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Метод не поддерживается: '{method}'"}
            }
        return None

    def run_stdio(self) -> None:
        """Главный цикл чтения stdio (поддерживает raw JSON-lines и Content-Length заголовки)."""
        log_debug("Dialogue Engine MCP Server started over stdio.")
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                line_stripped = line.strip()
                if not line_stripped:
                    continue

                # Поддержка Content-Length framing (LSP / Stream style)
                if line_stripped.lower().startswith("content-length:"):
                    length = int(line_stripped.split(":", 1)[1].strip())
                    # Читаем пустую строку-разделитель
                    while True:
                        hdr = sys.stdin.readline().strip()
                        if not hdr:
                            break
                    body = sys.stdin.read(length)
                    req = json.loads(body)
                else:
                    # Обычный newline-delimited JSON
                    req = json.loads(line_stripped)

                resp = self.handle_request(req)
                if resp is not None:
                    out = json.dumps(resp, ensure_ascii=False)
                    sys.stdout.write(out + "\n")
                    sys.stdout.flush()

            except (KeyboardInterrupt, SystemExit):
                break
            except Exception as e:
                log_debug(f"Exception in stdio loop: {traceback.format_exc()}")


def main():
    initial_path = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".json") else None
    server = DialogueEngineMCPServer(initial_project_path=initial_path)
    server.run_stdio()


if __name__ == "__main__":
    main()

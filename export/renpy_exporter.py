"""
Dialogue Engine - Ren'Py Script Exporter.
Генерирует чистый script.rpy из графа сценария. Поддерживает работу в headless/CLI режиме и в GUI.
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from core.models import ConnectionData, NodeData, ProjectData
from export.base_exporter import BaseExporter


class RenPyExporter(BaseExporter):
    """Экспортер диалогов в синтаксис Ren'Py Visual Novel Engine."""

    def __init__(self, plugin_manager: Any = None):
        self.plugin_manager = plugin_manager

    @staticmethod
    def clean_rel_path(path: str, export_dir: str = "") -> str:
        """Очищает путь к медиа-файлам для использования в Ren'Py."""
        if not path:
            return ""
        path = path.replace("\\", "/")
        path_lower = path.lower()

        if "/game/" in path_lower:
            idx = path_lower.find("/game/")
            path = path[idx + 6:]
        elif path_lower.startswith("game/"):
            path = path[5:]
        elif export_dir and os.path.isabs(path):
            try:
                rel = os.path.relpath(path, export_dir).replace("\\", "/")
                if not rel.startswith(".."):
                    path = rel
            except ValueError:
                pass
        return path.lstrip("/")

    def should_pause_after_media(self, node: NodeData, connections: List[ConnectionData], nodes_map: Dict[str, NodeData]) -> bool:
        """Определяет необходимость паузы после показа медиа-узла."""
        out_conns = [c for c in connections if c.from_node == node.id]
        if not out_conns:
            return True

        curr_id = out_conns[0].to_node
        visited = set()
        while curr_id and curr_id not in visited:
            visited.add(curr_id)
            target = nodes_map.get(curr_id)
            if not target:
                break
            if target.node_type in ("story", "choice"):
                return False
            if target.node_type in ("media", "animation"):
                return True
            next_outs = [c for c in connections if c.from_node == curr_id]
            if not next_outs:
                break
            curr_id = next_outs[0].to_node

        return False

    def export(self, project: Union[ProjectData, Dict[str, Any]], output_dir: str, **kwargs) -> Tuple[bool, str]:
        """Экспортирует проект в script.rpy внутри output_dir."""
        if isinstance(project, dict):
            project = ProjectData.from_dict(project)

        nodes = project.nodes
        connections = project.connections

        if not nodes:
            return False, "Проект пуст! Добавьте узлы для экспорта."

        os.makedirs(output_dir, exist_ok=True)
        rpy_path = os.path.join(output_dir, "script.rpy")
        nodes_map = {n.id: n for n in nodes}

        try:
            with open(rpy_path, "w", encoding="utf-8") as f:
                f.write("# --- Сгенерировано Dialogue Engine ---\n\n")

                # Хук для инициализации глобальных блоков (анимации, ATL и т.д.)
                if self.plugin_manager:
                    init_data = {
                        "file": f,
                        "nodes": nodes,
                        "connections": [c.to_dict() for c in connections],
                        "export_dir": output_dir
                    }
                    self.plugin_manager.notify("renpy_export_init", init_data)

                # Поиск стартового узла
                target_ids = {c.to_node for c in connections}
                root_nodes = [n for n in nodes if n.id not in target_ids]
                if not root_nodes:
                    root_nodes = [nodes[0]]

                start_node = next(
                    (n for n in root_nodes if (n.node_type in ("label", "story")) and n.title.lower() in ("start", "старт")),
                    root_nodes[0]
                )

                f.write("label start:\n")
                f.write(f"    jump node_{start_node.id}\n\n")

                for node in nodes:
                    if self.plugin_manager:
                        check_data = {"node": node, "skip": False}
                        self.plugin_manager.notify("renpy_export_check", check_data)
                        if check_data.get("skip", False):
                            continue

                    f.write(f"# --- {node.title} ({node.node_type}) ---\n")
                    f.write(f"label node_{node.id}:\n")

                    handled = False
                    if self.plugin_manager:
                        export_data = {
                            "node": node,
                            "file": f,
                            "connections": [c.to_dict() for c in connections],
                            "export_dir": output_dir,
                            "handled": False
                        }
                        self.plugin_manager.notify("renpy_export_node", export_data)
                        handled = export_data.get("handled", False)

                    if not handled:
                        self.write_node_content_default(f, node, connections, output_dir=output_dir, nodes_map=nodes_map)

                    f.write("\n")

            return True, f"Скрипт успешно экспортирован:\n{rpy_path}"
        except Exception as e:
            return False, f"Ошибка при экспорте в Ren'Py: {e}"

    def write_node_content_default(
        self,
        f: Any,
        node: NodeData,
        connections: List[ConnectionData],
        output_dir: str = "",
        nodes_map: Optional[Dict[str, NodeData]] = None
    ) -> None:
        """Стандартная логика генерации контента для базовых типов узлов."""
        # 1. Текстовый узел (Story)
        if node.node_type == "story":
            if node.custom_data.get("pause_before"):
                p_mode = node.custom_data.get("pause_before_mode", "click")
                p_dur = node.custom_data.get("pause_before_duration", 1.0)
                try:
                    if p_mode == "time" and float(p_dur) > 0:
                        f.write(f"    pause {p_dur}\n")
                    else:
                        f.write("    pause\n")
                except (ValueError, TypeError):
                    f.write("    pause\n")

            char_name = node.title.replace('"', '\\"')
            text = node.content.replace('"', '\\"').replace("\n", "\\n")

            if "highlights" in node.custom_data:
                for word, color in node.custom_data["highlights"].items():
                    if word:
                        text = text.replace(word, f"{{color={color}}}{word}{{/color}}")

            header_color = node.custom_data.get("header_text_color", "")
            if header_color and header_color.lower() not in ("#ffffff", "white"):
                char_name = f"{{color={header_color}}}{char_name}{{/color}}"

            if getattr(node, "mode", "standard") == "continue":
                if not text.startswith(" ") and not text.startswith("\\n"):
                    text = " " + text
                f.write(f'    extend "{text}"\n')
            elif char_name.startswith("#") or not char_name or char_name == f"{{color={header_color}}}#{{/color}}":
                f.write(f'    "{text}"\n')
            else:
                f.write(f'    "{char_name}" "{text}"\n')
            self.write_jump(f, node.id, connections)

        # 2. Узел Музыки/Звука
        elif node.node_type == "music":
            mode = node.custom_data.get("music_mode", "bg")
            path = self.clean_rel_path(node.custom_data.get("music_file", ""), output_dir)
            if path:
                if mode == "bg":
                    f.write(f'    play music "{path}"\n')
                elif mode == "sfx":
                    f.write(f'    play sound "{path}"\n')
                else:
                    f.write(f'    voice "{path}"\n')
            self.write_jump(f, node.id, connections)

        # 3. Узел Медиа (Фон / Спрайт)
        elif node.node_type == "media":
            try:
                data = json.loads(node.content) if isinstance(node.content, str) else node.content
                mode = data.get("mode", "sprite")
                path = self.clean_rel_path(data.get("image_path", ""), output_dir)
                anim = data.get("animation", "none")
                dur = data.get("animation_duration", 0.5)
                with_clause = ""

                if anim.lower() != "none":
                    if anim[0].isupper():
                        with_clause = f" with {anim}({dur})"
                    else:
                        if dur != 0.5:
                            with_clause = f" with {anim.capitalize()}({dur})"
                        else:
                            with_clause = f" with {anim}"

                if path:
                    if mode == "background":
                        f.write(f'    scene expression "{path}"{with_clause}\n')
                    else:
                        align = data.get("position", "center")
                        f.write(f'    show expression "{path}" at {align}{with_clause}\n')

                if data.get("pause", False) or (nodes_map and self.should_pause_after_media(node, connections, nodes_map)):
                    f.write("    pause\n")
            except Exception:
                pass
            self.write_jump(f, node.id, connections)

        # 4. Узел Выбора (Choice)
        elif node.node_type == "choice":
            options = node.content.split("\n")
            f.write("    menu:\n")
            out_conns = [c for c in connections if c.from_node == node.id]
            for i, opt in enumerate(options):
                if not opt.strip():
                    continue
                clean_opt = opt.replace('"', '\\"')
                hover_color = None
                if "highlights" in node.custom_data:
                    for word, color in node.custom_data["highlights"].items():
                        if word and word in opt:
                            hover_color = color
                            break

                if hover_color:
                    f.write(f'        "{clean_opt}" (hover_outlines=[(2, "{hover_color}", 0, 0)]):\n')
                else:
                    f.write(f'        "{clean_opt}":\n')

                target_conn = next((c for c in out_conns if c.out_idx == i), None)
                if target_conn:
                    f.write(f"            jump node_{target_conn.to_node}\n")
                else:
                    f.write("            pass\n")

        # 5. Узел Label (Логическая метка)
        elif node.node_type == "label":
            f.write(f"    # Метка: {node.title}\n")
            self.write_jump(f, node.id, connections)

        # 6. Узел Переменных (Variable)
        elif node.node_type == "variable":
            lines = node.content.split("\n")
            for line in lines:
                if line.strip():
                    f.write(f"    $ {line.strip()}\n")
            self.write_jump(f, node.id, connections)

    def write_jump(self, f: Any, node_id: str, connections: List[ConnectionData]) -> None:
        """Записывает переход на следующий узел или return."""
        out_conns = [c for c in connections if c.from_node == node_id]
        if out_conns:
            f.write(f"    jump node_{out_conns[0].to_node}\n")
        else:
            f.write("    return\n")

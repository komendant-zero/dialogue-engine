"""
Dialogue Engine - Node Visual Canvas Item.
"""

from __future__ import annotations
import math
import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Dict, List, Optional, Tuple
import uuid

from core.models import NodeData
from ui.theme import COLORS, PC_USER


class Node:
    """Визуальное представление узла сценария на холсте Tkinter."""

    def __init__(
        self,
        editor: Any,
        x: float,
        y: float,
        title: str,
        content: str,
        node_type: str,
        custom_data: Optional[Dict[str, Any]] = None,
        mode: str = "standard",
        node_id: Optional[str] = None
    ):
        self.editor = editor
        self.id = str(node_id) if node_id is not None else str(uuid.uuid4().hex[:12])
        self.x = float(x)
        self.y = float(y)
        self.width = 180
        self.height = 100
        self.title = title
        self.content = content
        self.node_type = node_type
        self.mode = mode

        self.custom_data: Dict[str, Any] = custom_data if custom_data is not None else {}
        self.outputs: List[Dict[str, Any]] = []

        try:
            self.font_content = tkfont.Font(family="Segoe UI", size=9)
        except Exception:
            self.font_content = None

        self.calculate_size()

    def _get_display_text(self, text: str) -> str:
        """Заменяет плейсхолдеры на реальные данные пользователя."""
        if not text:
            return ""
        return text.replace("[ИГРОК]", PC_USER)

    def calculate_size(self) -> None:
        base_h = 40
        display_content = self._get_display_text(self.content)

        calc_data = {
            "node": self,
            "base_h": base_h,
            "display_content": display_content,
            "height": None,
            "handled": {"done": False}
        }
        if self.editor and hasattr(self.editor, "plugin_manager") and self.editor.plugin_manager:
            self.editor.plugin_manager.notify("calculate_node_size", calc_data)

        if calc_data["handled"]["done"] and calc_data["height"] is not None:
            self.height = calc_data["height"]
        else:
            if self.editor and hasattr(self.editor, "canvas") and self.editor.canvas and self.font_content:
                text_val = display_content if display_content else " "
                temp_text = self.editor.canvas.create_text(
                    0, 0, text=text_val, width=self.width - 20, font=self.font_content, anchor="nw"
                )
                bbox = self.editor.canvas.bbox(temp_text)
                self.editor.canvas.delete(temp_text)
                text_h = (bbox[3] - bbox[1]) if bbox else 20
                self.height = base_h + text_h + 15
            else:
                self.height = 100

    def draw(self, canvas: tk.Canvas) -> None:
        x, y, w, h = self.x, self.y, self.width, self.height

        display_title = self._get_display_text(self.title)
        display_content = self._get_display_text(self.content)

        default_bg = COLORS.get(f"node_{self.node_type}", COLORS["node_story"])
        default_head = COLORS.get(f"header_{self.node_type}", COLORS["header_story"])

        bg_col = self.custom_data.get("bg_color", default_bg)
        head_col = self.custom_data.get("header_color", default_head)
        text_col = self.custom_data.get("text_color", COLORS["text"])
        header_text_col = self.custom_data.get("header_text_color", "white")

        # 1. Тело блока
        is_selected = getattr(self.editor, "selected_nodes", []) and self in self.editor.selected_nodes
        outline_color = COLORS["selection"] if is_selected else COLORS["grid_bold"]
        outline_width = 3 if is_selected else 2
        canvas.create_rectangle(
            x, y, x + w, y + h,
            fill=bg_col, outline=outline_color, width=outline_width, tags=("node", self.id)
        )

        # 2. Заголовок
        canvas.create_rectangle(x, y, x + w, y + 25, fill=head_col, outline="", tags=("node", self.id))

        # Логика отображения заголовка
        final_title = display_title
        title_font = ("Segoe UI", 9, "bold")
        title_fill = header_text_col

        if display_title.startswith("#") or not display_title.strip():
            if self.node_type == "story":
                comment = display_title.lstrip("#").strip()
                final_title = f"💭 {comment}" if comment else "💭 Слова автора"
                title_font = ("Segoe UI", 8, "italic")
                title_fill = "#aaaaaa"
            else:
                final_title = ""
        else:
            if self.node_type == "story":
                final_title = f"👤 {display_title}"

        canvas.create_text(
            x + 10, y + 12, text=final_title, fill=title_fill, anchor="w", font=title_font, tags=("node", self.id)
        )

        # Индикатор режима Continue
        if self.node_type == "story" and self.mode == "continue":
            canvas.create_text(
                x + w - 10, y + 12, text="[+]", fill="#fff", anchor="e", font=("Segoe UI", 8, "bold"), tags=("node", self.id)
            )

        # 3. Отрисовка контента
        draw_data = {"node": self, "canvas": canvas, "handled": False}
        if self.editor and hasattr(self.editor, "plugin_manager") and self.editor.plugin_manager:
            self.editor.plugin_manager.notify("draw_node_content", draw_data)

        if not draw_data["handled"]:
            canvas.create_text(
                x + 10, y + 35,
                text=display_content,
                fill=text_col,
                anchor="nw",
                width=w - 20,
                font=self.font_content,
                tags=("node", self.id)
            )
            self.draw_port(canvas, x + w, y + math.floor(h / 2), 0)

        # 4. Входной порт
        port_data = {"node": self, "canvas": canvas, "handled": False}
        if self.editor and hasattr(self.editor, "plugin_manager") and self.editor.plugin_manager:
            self.editor.plugin_manager.notify("draw_node_ports", port_data)
        if not port_data["handled"]:
            self.draw_input_port(canvas, x, y + math.floor(h / 2))

        # Hook для кастомной отрисовки плагинами
        if self.editor and hasattr(self.editor, "plugin_manager") and self.editor.plugin_manager:
            self.editor.plugin_manager.notify("draw_node", {"node": self, "canvas": canvas})

    def draw_port(self, canvas: tk.Canvas, px: float, py: float, index: int) -> None:
        r = 5
        tag = f"port_out_{self.id}_{index}"
        canvas.create_oval(px - r, py - r, px + r, py + r, fill=COLORS["port"], outline="", tags=("port", "output", tag))
        self.outputs.append({"id": index, "x": px, "y": py, "tag": tag})

    def draw_input_port(self, canvas: tk.Canvas, px: float, py: float) -> None:
        r = 5
        tag = f"port_in_{self.id}"
        canvas.create_oval(px - r, py - r, px + r, py + r, fill=COLORS["port"], outline="", tags=("port", "input", tag))

    def get_output_pos(self, index: int) -> Tuple[float, float]:
        if self.node_type in ("choice", "battle", "condition"):
            if self.node_type == "condition":
                return (self.x + self.width, self.y + 35 + (15 if index == 0 else 40))
            return (self.x + self.width, self.y + 35 + (index * 25))
        return (self.x + self.width, self.y + self.height / 2)

    def get_input_pos(self) -> Tuple[float, float]:
        if self.node_type == "condition":
            return (self.x, self.y + 35)
        y_pos = self.y + 25 if self.node_type in ("choice", "battle") else self.y + self.height / 2
        return (self.x, y_pos)

    def is_inside(self, x: float, y: float) -> bool:
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

    def to_node_data(self) -> NodeData:
        is_char = not self.title.startswith("#") if self.title else False
        return NodeData(
            id=self.id,
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            title=self.title,
            content=self.content,
            node_type=self.node_type,
            mode=self.mode,
            custom_data=dict(self.custom_data),
            is_character=is_char
        )

    @classmethod
    def from_node_data(cls, editor: Any, data: NodeData) -> Node:
        node = cls(
            editor=editor,
            x=data.x,
            y=data.y,
            title=data.title,
            content=data.content,
            node_type=data.node_type,
            custom_data=dict(data.custom_data),
            mode=data.mode
        )
        node.id = data.id
        node.width = data.width
        node.height = data.height
        return node

"""
Dialogue Engine - Editor Canvas Component.
"""

from __future__ import annotations
import math
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

from ui.theme import COLORS


class EditorCanvas(tk.Canvas):
    """Специализированный холст редактора с поддержкой бесконечной сетки, кривых Безье, зума и физики скролла."""

    def __init__(self, parent: tk.Widget, editor: Any, **kwargs):
        kwargs.setdefault("bg", COLORS["canvas_bg"])
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("xscrollincrement", 1)
        kwargs.setdefault("yscrollincrement", 1)
        super().__init__(parent, **kwargs)

        self.editor = editor
        self._media_image_refs: List[Any] = []
        self.create_grid()

    def create_grid(self) -> None:
        """Создает координатную сетку на холсте."""
        limit = 50000
        step = 20
        self.config(scrollregion=(0, -limit, limit, limit))

        for i in range(0, limit, step):
            if i == 0:
                continue
            color = COLORS["grid_bold"] if i % 100 == 0 else COLORS["grid_light"]
            self.create_line(i, -limit, i, limit, tag="grid", fill=color)

        for i in range(-limit, limit, step):
            color = COLORS["grid_bold"] if i % 100 == 0 else COLORS["grid_light"]
            self.create_line(0, i, limit, i, tag="grid", fill=color)

        self.create_line(0, -limit, 0, limit, tag="grid", fill=COLORS["boundary_line"], width=2)
        self.tag_lower("grid")

    def draw_bezier(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        tags: Any = "conn",
        fill: Optional[str] = None
    ) -> int:
        """Отрисовывает сглаженную кривую Безье со стрелкой."""
        if fill is None:
            fill = COLORS["line"]
        x1, y1 = start
        x2, y2 = end
        dist = abs(x2 - x1) * 0.5
        return self.create_line(
            x1, y1, x1 + dist, y1, x2 - dist, y2, x2, y2,
            smooth=True, width=2, fill=fill, arrow=tk.LAST, tags=tags
        )

    def draw_connection(self, conn: Dict[str, Any]) -> None:
        from_node = self.editor.find_node_by_id(conn["from"])
        to_node = self.editor.find_node_by_id(conn["to"])
        if from_node and to_node:
            start = from_node.get_output_pos(conn["out_idx"])
            end = to_node.get_input_pos()
            is_selected = (getattr(self.editor, "selected_connection", None) == conn)
            color = COLORS["line_active"] if is_selected else COLORS["line"]
            conn_tag = f"conn_{conn['from']}_{conn['out_idx']}_{conn['to']}"
            self.draw_bezier(start, end, tags=("conn", conn_tag), fill=color)

    def redraw_all(self) -> None:
        """Перерисовывает все узлы и соединения."""
        self.delete("node")
        self.delete("port")
        self.delete("conn")
        self._media_image_refs.clear()

        for conn in self.editor.connections:
            self.draw_connection(conn)

        for node in self.editor.nodes:
            node.outputs = []
            node.draw(self)

    def center_on_node(self, node: Any) -> None:
        """Плавно центрирует холст на выбранном узле."""
        try:
            cw = self.winfo_width()
            ch = self.winfo_height()
            if cw <= 1 or ch <= 1:
                return

            limit = 50000
            # Нормализация координат для scrollregion (0, -limit, limit, limit)
            target_cx = node.x + node.width / 2
            target_cy = node.y + node.height / 2

            # xview_moveto принимает значение от 0.0 до 1.0 относительно полной ширины limit
            norm_x = max(0.0, min(1.0, (target_cx - cw / 2) / limit))
            # yview_moveto принимает значение относительно полной высоты 2 * limit
            norm_y = max(0.0, min(1.0, (target_cy + limit - ch / 2) / (2 * limit)))

            self.xview_moveto(norm_x)
            self.yview_moveto(norm_y)
        except Exception:
            pass

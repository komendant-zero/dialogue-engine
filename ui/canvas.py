"""
Dialogue Engine - Editor Canvas Component.
"""

from __future__ import annotations
import math
import tkinter as tk
from typing import Any, Dict, List, Optional, Tuple

from ui.theme import COLORS


class EditorCanvas(tk.Canvas):
    """Специализированный холст редактора с бесконечной процедурной сеткой во все 4 стороны,
    кривыми Безье, зумом и физикой скролла.
    """
    LIMIT = 5000000

    def __init__(self, parent: tk.Widget, editor: Any, **kwargs):
        kwargs.setdefault("bg", COLORS["canvas_bg"])
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("xscrollincrement", 1)
        kwargs.setdefault("yscrollincrement", 1)
        super().__init__(parent, **kwargs)

        self.editor = editor
        self._media_image_refs: List[Any] = []
        self.config(scrollregion=(-self.LIMIT, -self.LIMIT, self.LIMIT, self.LIMIT))
        self.bind("<Configure>", lambda e: self.update_grid())
        self.update_grid()

    def create_grid(self) -> None:
        """Алиас для обратной совместимости."""
        self.update_grid()

    def update_grid(self) -> None:
        """Процедурно отрисовывает координатную сетку только в видимой области экрана.
        Это делает холст бесконечным в любую сторону (включая отрицательные координаты)
        и обеспечивает максимальную производительность без лагов.
        """
        self.delete("grid")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1 or h <= 1:
            return

        x1 = self.canvasx(0)
        y1 = self.canvasy(0)
        x2 = self.canvasx(w)
        y2 = self.canvasy(h)

        step = 20
        bold_step = 100

        start_x = int(math.floor(x1 / step)) * step
        end_x = int(math.ceil(x2 / step)) * step
        start_y = int(math.floor(y1 / step)) * step
        end_y = int(math.ceil(y2 / step)) * step

        # Вертикальные линии
        for x in range(start_x, end_x + step, step):
            if x == 0:
                color = "#3d5a80"  # Центральная ось координат Y
                width = 2
            elif x % bold_step == 0:
                color = COLORS["grid_bold"]
                width = 1
            else:
                color = COLORS["grid_light"]
                width = 1
            self.create_line(x, y1, x, y2, tag="grid", fill=color, width=width)

        # Горизонтальные линии
        for y in range(start_y, end_y + step, step):
            if y == 0:
                color = "#3d5a80"  # Центральная ось координат X
                width = 2
            elif y % bold_step == 0:
                color = COLORS["grid_bold"]
                width = 1
            else:
                color = COLORS["grid_light"]
                width = 1
            self.create_line(x1, y, x2, y, tag="grid", fill=color, width=width)

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
        """Перерисовывает все узлы, соединения и процедурную сетку."""
        self.delete("node")
        self.delete("port")
        self.delete("conn")
        self._media_image_refs.clear()

        self.update_grid()

        for conn in self.editor.connections:
            self.draw_connection(conn)

        for node in self.editor.nodes:
            node.outputs = []
            node.draw(self)

    def center_on_node(self, node: Any) -> None:
        """Плавно центрирует холст на выбранном узле в бесконечном пространстве."""
        try:
            cw = self.winfo_width()
            ch = self.winfo_height()
            if cw <= 1 or ch <= 1:
                return

            target_cx = node.x + node.width / 2
            target_cy = node.y + node.height / 2

            norm_x = max(0.0, min(1.0, (target_cx + self.LIMIT - cw / 2) / (2 * self.LIMIT)))
            norm_y = max(0.0, min(1.0, (target_cy + self.LIMIT - ch / 2) / (2 * self.LIMIT)))

            self.xview_moveto(norm_x)
            self.yview_moveto(norm_y)
            self.update_grid()
        except Exception:
            pass

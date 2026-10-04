"""
Dialogue Engine - Main Application Entry Point.
"""

import os
import sys

# --- ПУТИ ДЛЯ СТАБИЛЬНОГО ЗАПУСКА (Double-Click Fix) ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# --- DPI AWARENESS (Windows Fix for Crisp Fonts and Coordinates) ---
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Экспортируем ключевые сущности для обратной совместимости
from core.models import ConnectionData, NodeData, ProjectData
from core.graph import GraphModel
from core.serialization import ProjectSerializer
from ui.theme import COLORS, NODE_COLOR_PRESETS, darken_color, PC_USER, get_pc_user
from ui.node_view import Node
from ui.canvas import EditorCanvas
from ui.editor import ScenarioEditor


def main() -> None:
    """Точка входа приложения."""
    initial_file = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".json") else None
    app = ScenarioEditor(initial_file=initial_file)
    app.mainloop()


if __name__ == "__main__":
    main()
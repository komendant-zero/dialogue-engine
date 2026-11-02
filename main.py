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
from ui.dialogs.update_dialog import StartupSplashDialog


def check_environment() -> None:
    """Диагностика окружения Python и наличия зависимостей."""
    missing = []
    try:
        import PIL
    except ImportError:
        missing.append("Pillow")

    if missing:
        print("\n" + "=" * 65)
        print(" [ВНИМАНИЕ] Не обнаружены некоторые библиотеки проекта:")
        print(f"   Отсутствуют: {', '.join(missing)}")
        print(f"   Текущий Python: {sys.executable}")
        print("   Для полной установки зависимостей запустите:")
        print("     install_dependencies.bat  или  pip install -r requirements.txt")
        print("=" * 65 + "\n")


def main() -> None:
    """Точка входа приложения."""
    check_environment()

    # Режим постоянного 24/7 сервера совместной работы (коворк)
    if "--server" in sys.argv:
        import server
        server.main()
        return

    # Определение начального файла проекта
    initial_file = None
    skip_splash = "--no-update" in sys.argv or "--no-splash" in sys.argv

    for arg in sys.argv[1:]:
        if arg.endswith(".json") and os.path.exists(arg):
            initial_file = arg
            break

    app = ScenarioEditor(initial_file=initial_file)

    if skip_splash:
        app.mainloop()
        return

    # Скрываем главное окно на время показа Windows прогресс-бара обновления
    app.withdraw()

    def on_splash_finish() -> None:
        try:
            app.deiconify()
            app.lift()
            app.focus_force()
        except Exception:
            pass

    # Запуск окна проверки обновлений с Windows прогресс-баром
    StartupSplashDialog(parent=app, on_finish=on_splash_finish, timeout_sec=3.0)
    app.mainloop()


if __name__ == "__main__":
    main()

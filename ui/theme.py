"""
Dialogue Engine - UI Theme, Colors & System Helpers.
"""

from __future__ import annotations
import getpass
import sys
from typing import Dict, List, Tuple


def get_pc_user() -> str:
    """Пытается получить имя пользователя (Full Name для Windows, иначе логин)."""
    username = getpass.getuser()
    if sys.platform == "win32":
        try:
            import ctypes
            GetUserNameEx = ctypes.windll.secur32.GetUserNameExW
            size = ctypes.c_ulong(512)
            buffer = ctypes.create_unicode_buffer(size.value)
            if GetUserNameEx(3, buffer, ctypes.byref(size)):
                if buffer.value:
                    return buffer.value
        except Exception:
            pass
    return username


PC_USER = get_pc_user()

# Конфигурация цветовой палитры интерфейса
COLORS: Dict[str, str] = {
    "bg": "#1e1e1e",
    "canvas_bg": "#2b2b2b",
    "grid_light": "#333333",
    "grid_bold": "#3a3a3a",
    "node_story": "#3c3f41",
    "node_choice": "#2d4a57",
    "node_music": "#8e44ad",
    "header_story": "#4a90e2",
    "header_choice": "#e67e22",
    "header_music": "#9b59b6",
    "text": "#dcdcdc",
    "port": "#888888",
    "line": "#a9b7c6",
    "line_active": "#ffcc00",
    "boundary_line": "#e74c3c",
    "selection": "#00ff00",
    "marquee": "#4a90e2",
}

# Пресеты цветов блоков
NODE_COLOR_PRESETS: List[Tuple[str, str, str]] = [
    ("🟠 Оранжевый", "#d35400", "#a04000"),
    ("🟢 Зелёный", "#27ae60", "#1e8449"),
    ("🔵 Синий", "#2980b9", "#1f618d"),
    ("🟣 Фиолетовый", "#8e44ad", "#71368a"),
    ("🔴 Красный", "#c0392b", "#922b21"),
    ("💠 Бирюзовый", "#16a085", "#117a65"),
    ("🟡 Золотой", "#d4ac0d", "#b7950b"),
    ("🟤 Коричневый", "#795548", "#5d4037"),
    ("⚫ Тёмно-серый", "#34495e", "#2c3e50"),
]


def darken_color(hex_color: str, factor: float = 0.75) -> str:
    """Генерирует гармоничный тёмный оттенок для шапки блока."""
    try:
        hex_clean = hex_color.lstrip("#")
        if len(hex_clean) == 6:
            r = int(hex_clean[0:2], 16)
            g = int(hex_clean[2:4], 16)
            b = int(hex_clean[4:6], 16)
            r = max(0, min(255, int(r * factor)))
            g = max(0, min(255, int(g * factor)))
            b = max(0, min(255, int(b * factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        pass
    return hex_color


# Стили для кнопок интерфейса
BTN_ACTION_STYLE = {
    "bg": "#2c3e50",
    "fg": "white",
    "activebackground": "#34495e",
    "activeforeground": "white",
    "relief": "flat",
    "font": ("Segoe UI", 9, "bold"),
    "padx": 9,
    "pady": 3,
    "cursor": "hand2"
}

BTN_NORMAL_STYLE = {
    "bg": "#333333",
    "fg": "#dddddd",
    "activebackground": "#444444",
    "activeforeground": "white",
    "relief": "flat",
    "font": ("Segoe UI", 9),
    "padx": 8,
    "pady": 3,
    "cursor": "hand2"
}

MENU_CFG_STYLE = {
    "bg": "#252526",
    "fg": "white",
    "activebackground": "#094771",
    "activeforeground": "white",
    "font": ("Segoe UI", 9),
    "relief": "flat",
    "tearoff": 0
}

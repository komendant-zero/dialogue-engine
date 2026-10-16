"""
Dialogue Engine - Hotkeys Configuration & Manager.
Обеспечивает централизованную настройку, сохранение и кросс-раскладковую диспетчеризацию хоткеев.
"""

from __future__ import annotations
import json
import os
from typing import Any, Callable, NamedTuple

SETTINGS_FILE = "settings.json"

# Таблица сопоставления латинских букв клавиш с кириллическими keysyms Tkinter
CYRILLIC_KEY_MAP: dict[str, tuple[str, str]] = {
    "a": ("Cyrillic_ef", "Cyrillic_EF"),              # Ф
    "b": ("Cyrillic_i", "Cyrillic_I"),                # И
    "c": ("Cyrillic_es", "Cyrillic_ES"),              # С
    "d": ("Cyrillic_ve", "Cyrillic_VE"),              # В
    "e": ("Cyrillic_u", "Cyrillic_U"),                # У
    "f": ("Cyrillic_a", "Cyrillic_A"),                # А
    "g": ("Cyrillic_pe", "Cyrillic_PE"),              # П
    "h": ("Cyrillic_er", "Cyrillic_ER"),              # Р
    "i": ("Cyrillic_sha", "Cyrillic_SHA"),            # Ш
    "j": ("Cyrillic_o", "Cyrillic_O"),                # О
    "k": ("Cyrillic_el", "Cyrillic_EL"),              # Л
    "l": ("Cyrillic_de", "Cyrillic_DE"),              # Д
    "m": ("Cyrillic_softsign", "Cyrillic_SOFTSIGN"),  # Ь
    "n": ("Cyrillic_te", "Cyrillic_TE"),              # Т
    "o": ("Cyrillic_shcha", "Cyrillic_SHCHA"),        # Щ
    "p": ("Cyrillic_ze", "Cyrillic_ZE"),              # З
    "q": ("Cyrillic_shorti", "Cyrillic_SHORTI"),      # Й
    "r": ("Cyrillic_ka", "Cyrillic_KA"),              # К
    "s": ("Cyrillic_yeru", "Cyrillic_YERU"),          # Ы
    "t": ("Cyrillic_ie", "Cyrillic_IE"),              # Е
    "u": ("Cyrillic_ghe", "Cyrillic_GHE"),            # Г
    "v": ("Cyrillic_em", "Cyrillic_EM"),              # М
    "w": ("Cyrillic_tse", "Cyrillic_TSE"),            # Ц
    "x": ("Cyrillic_che", "Cyrillic_CHE"),            # Ч
    "y": ("Cyrillic_en", "Cyrillic_EN"),              # Н
    "z": ("Cyrillic_ya", "Cyrillic_YA"),              # Я
}

# Обратное сопоставление кириллических keysyms в латинские символы
CYRILLIC_TO_LATIN: dict[str, str] = {}
for _lat, (_cyr_l, _cyr_u) in CYRILLIC_KEY_MAP.items():
    CYRILLIC_TO_LATIN[_cyr_l.lower()] = _lat.upper()
    CYRILLIC_TO_LATIN[_cyr_u.lower()] = _lat.upper()

# Значения горячих клавиш по умолчанию
DEFAULT_HOTKEYS: dict[str, str] = {
    # Создание нод
    "add_story": "1",
    "add_choice": "2",
    "add_condition": "3",
    "add_music": "4",
    "add_pause": "5",

    # Файл и Проект
    "save_project": "Ctrl+S",
    "load_project": "Ctrl+O",
    "search": "Ctrl+F",

    # Редактирование
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Y",
    "copy": "Ctrl+C",
    "paste": "Ctrl+V",
    "duplicate": "Ctrl+D",
    "select_all": "Ctrl+A",
    "delete": "Delete",

    # Холст и инструменты
    "auto_layout": "Ctrl+L",
    "zoom_in": "Ctrl+=",
    "zoom_out": "Ctrl+-",
    "zoom_reset": "Ctrl+0",
}

# Описания и группировка действий для UI настроек
ACTION_METADATA: dict[str, dict[str, str]] = {
    "add_story": {
        "title": "📝 Сюжет (Story)",
        "category": "Создание нод",
        "description": "Создать новую ноду сцены/диалога в позиции курсора мыши"
    },
    "add_choice": {
        "title": "🔀 Выбор (Choice)",
        "category": "Создание нод",
        "description": "Создать ноду развилки / выбора вариантов в позиции курсора мыши"
    },
    "add_condition": {
        "title": "❓ Условие (Condition)",
        "category": "Создание нод",
        "description": "Создать условную ноду ветвления If / Else в позиции курсора мыши"
    },
    "add_music": {
        "title": "🎵 Музыка / Звук",
        "category": "Создание нод",
        "description": "Создать ноду воспроизведения звука или музыки"
    },
    "add_pause": {
        "title": "⏱️ Пауза (Pause)",
        "category": "Создание нод",
        "description": "Создать ноду тайминга и задержки сцены"
    },
    "save_project": {
        "title": "💾 Сохранить проект",
        "category": "Файл и Проект",
        "description": "Сохранить текущий проект сценария в JSON файл"
    },
    "load_project": {
        "title": "📂 Открыть проект",
        "category": "Файл и Проект",
        "description": "Загрузить проект сценария из JSON файла"
    },
    "search": {
        "title": "🔍 Поиск и замена",
        "category": "Файл и Проект",
        "description": "Открыть окно поиска и замены текста по нодам"
    },
    "undo": {
        "title": "↩️ Отменить действие",
        "category": "Редактирование",
        "description": "Отменить последнее изменение графа (Undo)"
    },
    "redo": {
        "title": "↪️ Повторить действие",
        "category": "Редактирование",
        "description": "Повторить отменённое изменение графа (Redo)"
    },
    "copy": {
        "title": "📋 Копировать",
        "category": "Редактирование",
        "description": "Скопировать выбранные ноды в буфер обмена"
    },
    "paste": {
        "title": "📥 Вставить",
        "category": "Редактирование",
        "description": "Вставить ноды из буфера обмена со смещением"
    },
    "duplicate": {
        "title": "📑 Дублировать",
        "category": "Редактирование",
        "description": "Быстро создать копию выбранных нод на холсте"
    },
    "select_all": {
        "title": "☑️ Выделить всё",
        "category": "Редактирование",
        "description": "Выделить все ноды сценария на холсте"
    },
    "delete": {
        "title": "🗑️ Удалить выбранное",
        "category": "Редактирование",
        "description": "Удалить выбранные ноды или соединения"
    },
    "auto_layout": {
        "title": "📐 Авто-расстановка",
        "category": "Холст и Инструменты",
        "description": "Автоматически расставить ноды графа по уровням связей"
    },
    "zoom_in": {
        "title": "🔍+ Приблизить",
        "category": "Холст и Инструменты",
        "description": "Увеличить масштаб рабочей области холста"
    },
    "zoom_out": {
        "title": "🔍- Отдалить",
        "category": "Холст и Инструменты",
        "description": "Уменьшить масштаб рабочей области холста"
    },
    "zoom_reset": {
        "title": "🎯 Сброс масштаба",
        "category": "Холст и Инструменты",
        "description": "Сбросить масштаб холста на 100%"
    },
}


class KeyCombo(NamedTuple):
    ctrl: bool
    shift: bool
    alt: bool
    key: str  # e.g. "S", "1", "Delete", "=", "-"


def parse_hotkey_string(combo_str: str) -> KeyCombo | None:
    """Разбирает текстовое представление хоткея (например, 'Ctrl+Shift+Z' или '1') в KeyCombo."""
    if not combo_str or not combo_str.strip():
        return None
    parts = [p.strip() for p in combo_str.split("+") if p.strip()]
    if not parts:
        return None
    ctrl = any(p.lower() in ("ctrl", "control") for p in parts[:-1])
    shift = any(p.lower() == "shift" for p in parts[:-1])
    alt = any(p.lower() == "alt" for p in parts[:-1])
    main_raw = parts[-1]

    if len(main_raw) == 1:
        main_key = main_raw.upper()
    else:
        main_upper = main_raw.upper()
        if main_upper.startswith("F") and len(main_upper) in (2, 3) and main_upper[1:].isdigit():
            main_key = main_upper
        else:
            main_key = main_raw.capitalize()
    return KeyCombo(ctrl=ctrl, shift=shift, alt=alt, key=main_key)


def format_hotkey_from_event(event: Any) -> str | None:
    """Форматирует объект события нажатия клавиши Tkinter в понятную строку хоткея.
    Автоматически распознаёт клавиши как при английской, так и при русской раскладке.
    """
    ks = getattr(event, "keysym", "")
    kc = getattr(event, "keycode", 0)

    # Игнорируем изолированное нажатие модификаторов
    if ks in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R"):
        return None

    parts: list[str] = []
    if event.state & 4:
        parts.append("Ctrl")
    if event.state & 8 or event.state & 0x20000:
        parts.append("Alt")
    if event.state & 1:
        parts.append("Shift")

    key_name: str | None = None

    # 1. Латинские буквы A-Z по keycode (Windows layout-independent)
    if 65 <= kc <= 90:
        key_name = chr(kc)
    # 2. Кириллические keysyms (Linux / X11)
    elif ks.lower() in CYRILLIC_TO_LATIN:
        key_name = CYRILLIC_TO_LATIN[ks.lower()]
    # 3. Цифры 0-9
    elif 48 <= kc <= 57:
        key_name = chr(kc)
    elif 96 <= kc <= 105:
        key_name = str(kc - 96)
    # 4. Функциональные клавиши F1-F12
    elif 112 <= kc <= 123:
        key_name = f"F{kc - 111}"
    # 5. Специальные клавиши
    elif kc == 46 or ks == "Delete":
        key_name = "Delete"
    elif kc == 8 or ks in ("BackSpace", "Backspace"):
        key_name = "Backspace"
    elif kc == 13 or ks in ("Return", "Enter"):
        key_name = "Enter"
    elif kc == 32 or ks == "space":
        key_name = "Space"
    elif kc == 9 or ks == "Tab":
        key_name = "Tab"
    elif kc == 187 or ks in ("equal", "plus"):
        key_name = "="
    elif kc == 189 or ks in ("minus", "underscore"):
        key_name = "-"
    elif ks and ks != "??":
        if ks.upper().startswith("F") and len(ks) in (2, 3) and ks[1:].isdigit():
            key_name = ks.upper()
        else:
            key_name = ks.capitalize()
    elif 32 <= kc <= 126:
        key_name = chr(kc).upper()

    if not key_name:
        return None

    parts.append(key_name)
    return "+".join(parts)


def get_key_matchers(key: str) -> tuple[list[int], list[str]]:
    """Возвращает списки (keycodes, keysyms) для указанной клавиши, включая кириллические эквиваленты."""
    keycodes: list[int] = []
    keysyms: list[str] = []
    k_upper = key.upper()

    # Буквы A-Z
    if len(key) == 1 and "A" <= k_upper <= "Z":
        ch = k_upper.lower()
        keycodes.append(ord(k_upper))
        keysyms.extend([ch, k_upper])
        if ch in CYRILLIC_KEY_MAP:
            keysyms.extend(CYRILLIC_KEY_MAP[ch])

    # Цифры 0-9
    elif len(key) == 1 and "0" <= key <= "9":
        d = int(key)
        keycodes.extend([ord(key), 96 + d])  # Основной ряд и Numpad
        keysyms.append(key)

    # Функциональные клавиши F1-F12
    elif k_upper.startswith("F") and len(k_upper) in (2, 3) and k_upper[1:].isdigit():
        num = int(k_upper[1:])
        keycodes.append(111 + num)
        keysyms.extend([k_upper, k_upper.lower()])

    # Delete
    elif k_upper == "DELETE":
        keycodes.append(46)
        keysyms.append("Delete")

    # Backspace
    elif k_upper == "BACKSPACE":
        keycodes.append(8)
        keysyms.extend(["BackSpace", "Backspace"])

    # Enter / Return
    elif k_upper in ("ENTER", "RETURN"):
        keycodes.append(13)
        keysyms.extend(["Return", "Enter"])

    # Space
    elif k_upper == "SPACE":
        keycodes.append(32)
        keysyms.extend(["space", "Space"])

    # Tab
    elif k_upper == "TAB":
        keycodes.append(9)
        keysyms.extend(["Tab", "tab"])

    # Плюс / Равно
    elif k_upper in ("EQUAL", "="):
        keycodes.extend([187, 107])
        keysyms.extend(["equal", "plus"])

    # Минус / Подчёркивание
    elif k_upper in ("MINUS", "-"):
        keycodes.extend([189, 109])
        keysyms.extend(["minus", "underscore"])

    else:
        keysyms.extend([key, key.lower(), key.capitalize()])

    return keycodes, keysyms


class HotkeyManager:
    """Менеджер пользовательских сочетаний клавиш.
    Отвечает за чтение/запись в settings.json и быструю диспетчеризацию событий.
    """

    def __init__(self, config_file: str = SETTINGS_FILE):
        self.config_file = config_file
        self.hotkeys: dict[str, str] = self.load_hotkeys()
        self.actions: dict[str, Callable[..., Any]] = {}
        self._compiled_map: dict[tuple[bool, bool, bool, int | str], Callable[..., Any]] = {}

    def load_hotkeys(self) -> dict[str, str]:
        """Загружает сохранённые хоткеи из settings.json, дополняя значениями по умолчанию."""
        current = dict(DEFAULT_HOTKEYS)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "hotkeys" in data and isinstance(data["hotkeys"], dict):
                        current.update(data["hotkeys"])
            except Exception:
                pass
        return current

    def save_hotkeys(self, new_hotkeys: dict[str, str] | None = None) -> None:
        """Сохраняет хоткеи в settings.json, не перезаписывая остальные настройки."""
        if new_hotkeys is not None:
            self.hotkeys = dict(new_hotkeys)

        data: dict[str, Any] = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data["hotkeys"] = self.hotkeys
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def reset_to_defaults(self) -> None:
        """Сбрасывает все горячие клавиши к исходным настройкам."""
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        self.save_hotkeys()

    def register_action(
        self,
        action_id: str,
        handler: Callable[..., Any],
        title: str | None = None,
        category: str = "Общие",
        default_key: str = ""
    ) -> None:
        """Регистрирует действие и его обработчик."""
        self.actions[action_id] = handler
        if action_id not in ACTION_METADATA and title:
            ACTION_METADATA[action_id] = {
                "title": title,
                "category": category,
                "description": title
            }
        if action_id not in self.hotkeys:
            self.hotkeys[action_id] = default_key

    def compile(self) -> None:
        """Компилирует активные хоткеи в быстрый хеш-мап для O(1) поиска в on_key_press."""
        self._compiled_map.clear()

        for action_id, combo_str in self.hotkeys.items():
            handler = self.actions.get(action_id)
            if not handler or not combo_str:
                continue

            combo = parse_hotkey_string(combo_str)
            if not combo:
                continue

            keycodes, keysyms = get_key_matchers(combo.key)
            for kc in keycodes:
                self._compiled_map[(combo.ctrl, combo.shift, combo.alt, kc)] = handler
            for ks in keysyms:
                self._compiled_map[(combo.ctrl, combo.shift, combo.alt, ks)] = handler

        # Вторичные хоткеи для удобства (если не переназначены):
        # Redo через Ctrl+Shift+Z
        redo_handler = self.actions.get("redo")
        if redo_handler and (True, True, False, 90) not in self._compiled_map:
            self._compiled_map[(True, True, False, 90)] = redo_handler
            self._compiled_map[(True, True, False, "z")] = redo_handler
            self._compiled_map[(True, True, False, "Z")] = redo_handler
            self._compiled_map[(True, True, False, "Cyrillic_ya")] = redo_handler
            self._compiled_map[(True, True, False, "Cyrillic_YA")] = redo_handler

        # Zoom In через Ctrl+plus / Ctrl+=
        zoom_in_handler = self.actions.get("zoom_in")
        if zoom_in_handler:
            self._compiled_map.setdefault((True, False, False, 187), zoom_in_handler)
            self._compiled_map.setdefault((True, False, False, 107), zoom_in_handler)
            self._compiled_map.setdefault((True, False, False, "equal"), zoom_in_handler)
            self._compiled_map.setdefault((True, False, False, "plus"), zoom_in_handler)

    def dispatch(self, event: Any) -> bool:
        """Проверяет нажатие клавиши и вызывает действие. Возвращает True, если действие сработало."""
        is_ctrl = bool(event.state & 4)
        is_shift = bool(event.state & 1)
        is_alt = bool(event.state & 8) or bool(event.state & 0x20000)

        # 1. Поиск по keycode
        handler = self._compiled_map.get((is_ctrl, is_shift, is_alt, event.keycode))
        # 2. Если Shift не нажат, но активен CapsLock / NumLock
        if not handler and not is_shift:
            handler = self._compiled_map.get((is_ctrl, False, is_alt, event.keycode))
        # 3. Поиск по keysym
        if not handler:
            handler = self._compiled_map.get((is_ctrl, is_shift, is_alt, event.keysym))
        if not handler and not is_shift:
            handler = self._compiled_map.get((is_ctrl, False, is_alt, event.keysym))

        if handler:
            try:
                handler(event)
            except TypeError:
                handler()
            return True
        return False

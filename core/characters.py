"""
Dialogue Engine - Character Manager Core Logic.
Управление персонажами проекта, палитрами, пресетами эмоций и пакетными операциями.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from core.models import CharacterData, NodeData


# Предустановленные эстетичные цвета для персонажей
DEFAULT_CHARACTER_PALETTE: List[Tuple[str, str]] = [
    ("Синий (Ривер)", "#0080ff"),
    ("Бирюзовый (Ника)", "#00ffff"),
    ("Жёлтый (Джен)", "#ffff00"),
    ("Фиолетовый (Энджи)", "#c060f8"),
    ("Изумрудный", "#2ecc71"),
    ("Коралловый", "#e67e22"),
    ("Рубиновый", "#e74c3c"),
    ("Пурпурный (???)", "#8000ff"),
    ("Голубой (ТВ)", "#66ccff"),
    ("Светло-серый", "#dcdcdc"),
    ("Золотистый", "#f1c40f"),
    ("Мятный", "#1abc9c"),
]

# Стандартные эмоции для визуальных новелл
DEFAULT_EMOTIONS: List[str] = [
    "обычный",
    "радость",
    "грусть",
    "злость",
    "удивление",
    "смущение",
]


class CharacterManager:
    """Менеджер персонажей сценария."""

    def __init__(self, characters: Optional[List[CharacterData]] = None):
        self._characters: Dict[str, CharacterData] = {}
        if characters:
            self.load_from_characters(characters)

    def get(self, name: str) -> Optional[CharacterData]:
        """Возвращает персонажа по имени (без учета регистра при поиске, но с приоритетом точного совпадения)."""
        name_clean = name.strip()
        if name_clean in self._characters:
            return self._characters[name_clean]
        for k, v in self._characters.items():
            if k.lower() == name_clean.lower():
                return v
        return None

    def add(self, character: CharacterData) -> bool:
        """Добавляет нового персонажа. Возвращает False, если персонаж с таким именем уже существует."""
        name_clean = character.name.strip()
        if not name_clean:
            return False
        if self.get(name_clean) is not None:
            return False
        self._characters[name_clean] = character
        return True

    def update(self, old_name: str, character: CharacterData) -> bool:
        """Обновляет существующего персонажа, поддерживая безопасное переименование."""
        old_clean = old_name.strip()
        new_clean = character.name.strip()
        if not new_clean:
            return False

        # Если имя изменилось, проверяем, не занято ли новое имя
        if old_clean.lower() != new_clean.lower() and self.get(new_clean) is not None:
            return False

        # Удаляем старый ключ, если имя изменилось
        found_key = None
        for k in self._characters.keys():
            if k.lower() == old_clean.lower():
                found_key = k
                break

        if found_key:
            del self._characters[found_key]

        self._characters[new_clean] = character
        return True

    def delete(self, name: str) -> bool:
        """Удаляет персонажа по имени."""
        name_clean = name.strip()
        found_key = None
        for k in self._characters.keys():
            if k.lower() == name_clean.lower():
                found_key = k
                break
        if found_key:
            del self._characters[found_key]
            return True
        return False

    def list(self) -> List[CharacterData]:
        """Возвращает список всех персонажей."""
        return list(self._characters.values())

    def names(self) -> List[str]:
        """Возвращает отсортированный список имен персонажей."""
        return sorted(list(self._characters.keys()))

    def clear(self) -> None:
        """Очищает базу персонажей."""
        self._characters.clear()

    def load_from_characters(self, characters: List[CharacterData]) -> None:
        """Загружает персонажей из списка моделей."""
        self._characters.clear()
        for ch in characters:
            if ch.name.strip():
                self._characters[ch.name.strip()] = ch

    def to_list(self) -> List[CharacterData]:
        """Возвращает копию списка персонажей."""
        return [CharacterData.from_dict(c.to_dict()) for c in self._characters.values()]

    def scan_from_nodes(self, nodes: List[Any]) -> List[CharacterData]:
        """
        Сканирует узлы сценария, находит всех персонажей реплик и
        добавляет незарегистрированных в базу. Возвращает список вновь добавленных.
        """
        discovered: List[CharacterData] = []
        for n in nodes:
            node_type = getattr(n, "node_type", "")
            title = getattr(n, "title", "")
            custom_data = getattr(n, "custom_data", {})

            if node_type != "story":
                continue
            name = str(title).strip()
            if not name or name.startswith("#") or name in ("Сцена", "Персонаж", "start", "старт"):
                continue

            if self.get(name) is None:
                color = custom_data.get("header_text_color", "#ffffff") if isinstance(custom_data, dict) else "#ffffff"
                header_c = custom_data.get("header_color", "") if isinstance(custom_data, dict) else ""
                bg_c = custom_data.get("bg_color", "") if isinstance(custom_data, dict) else ""
                new_char = CharacterData(
                    name=name,
                    color=color or "#ffffff",
                    header_color=header_c,
                    bg_color=bg_c,
                    emotions=list(DEFAULT_EMOTIONS)
                )
                self.add(new_char)
                discovered.append(new_char)

        return discovered

    def batch_rename(self, old_name: str, new_name: str, nodes: List[Any]) -> int:
        """
        Пакетно переименовывает персонажа во всех узлах сценария.
        Возвращает количество обновленных узлов.
        """
        old_clean = old_name.strip()
        new_clean = new_name.strip()
        if not old_clean or not new_clean or old_clean == new_clean:
            return 0

        # Обновляем запись в самом менеджере, если такой персонаж есть
        char = self.get(old_clean)
        if char:
            char.name = new_clean
            self.update(old_clean, char)

        count = 0
        for n in nodes:
            node_type = getattr(n, "node_type", "")
            title = getattr(n, "title", "")
            if node_type == "story" and str(title).strip() == old_clean:
                n.title = new_clean
                if hasattr(n, "calculate_size"):
                    n.calculate_size()
                count += 1

        return count

    def apply_color_to_nodes(
        self,
        name: str,
        color: str,
        nodes: List[Any],
        header_color: Optional[str] = None,
        bg_color: Optional[str] = None
    ) -> int:
        """
        Применяет цвет персонажа ко всем соответствующим узлам на холсте.
        Возвращает количество обновленных узлов.
        """
        name_clean = name.strip()
        if not name_clean:
            return 0

        count = 0
        for n in nodes:
            node_type = getattr(n, "node_type", "")
            title = getattr(n, "title", "")
            if node_type == "story" and str(title).strip() == name_clean:
                if not hasattr(n, "custom_data") or n.custom_data is None:
                    n.custom_data = {}
                n.custom_data["header_text_color"] = color
                if header_color:
                    n.custom_data["header_color"] = header_color
                if bg_color:
                    n.custom_data["bg_color"] = bg_color
                if hasattr(n, "calculate_size"):
                    n.calculate_size()
                count += 1

        return count

    def count_repliques(self, name: str, nodes: List[Any]) -> int:
        """Считает количество реплик персонажа среди переданных узлов."""
        name_clean = name.strip().lower()
        count = 0
        for n in nodes:
            node_type = getattr(n, "node_type", "")
            title = getattr(n, "title", "")
            if node_type == "story" and str(title).strip().lower() == name_clean:
                count += 1
        return count

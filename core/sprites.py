"""
Dialogue Engine - Auto Sprite Resolver.
Автоматическое сопоставление персонажа и эмоции с файлами спрайтов на диске.
Позволяет активировать спрайты героев в диалогах без ручной расстановки медиа-блоков.
"""

from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple


# Таблица транслитерации для имен персонажей
CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}

# Известные соответствия имен персонажей
KNOWN_NAME_ALIASES: Dict[str, List[str]] = {
    "энджи": ["enjie", "endzhi", "angie"],
    "ника": ["nika", "veronika"],
    "ривер": ["river"],
    "джен": ["jen", "dzhen", "jennifer"],
    "телевизор": ["tv", "televizor"],
}

# Синонимы эмоций для сопоставления русских названий с файлами спрайтов
EMOTION_ALIASES: Dict[str, List[str]] = {
    "обычный": ["neutral", "normal", "idle", "default", "pose_01", "pose_1"],
    "нейтральный": ["neutral", "normal", "idle", "default", "pose_01"],
    "радость": ["happy", "smile", "joy"],
    "грусть": ["sad", "cry", "gloom"],
    "злость": ["angry", "rage"],
    "удивление": ["surprised", "shock"],
    "смущение": ["shy", "blush"],
}

IMAGE_EXTENSIONS = (".png", ".webp", ".jpg", ".jpeg", ".gif")


class SpriteResolver:
    """Сервис поиска и связывания спрайтов с персонажами и эмоциями."""

    @staticmethod
    def transliterate(text: str) -> str:
        """Транслитерирует строку с кириллицы в латиницу."""
        res = []
        for ch in text.lower():
            if ch in CYRILLIC_TO_LATIN:
                res.append(CYRILLIC_TO_LATIN[ch])
            elif ch.isalnum() or ch == '_':
                res.append(char := ch)
            elif ch.isspace() or ch in ('-', '.'):
                res.append('_')
        return "".join(res).strip('_')

    @classmethod
    def get_name_variants(cls, name: str) -> List[str]:
        """Возвращает список возможных вариантов написания имени персонажа."""
        raw = name.strip().lower()
        if not raw:
            return []

        variants = [raw]
        translit = cls.transliterate(raw)
        if translit and translit not in variants:
            variants.append(translit)

        # Проверяем базу известных синонимов
        for key, aliases in KNOWN_NAME_ALIASES.items():
            if raw == key or raw in aliases or translit in aliases:
                for a in aliases:
                    if a not in variants:
                        variants.append(a)
                if key not in variants:
                    variants.append(key)

        return variants

    @classmethod
    def get_emotion_variants(cls, emotion: str) -> List[str]:
        """Возвращает список возможных вариантов названия эмоции/позы."""
        raw = emotion.strip().lower()
        if not raw:
            return ["neutral", "normal", "idle", "default", "pose_01"]

        variants = [raw]
        translit = cls.transliterate(raw)
        if translit and translit not in variants:
            variants.append(translit)

        # Проверяем по базе синонимов
        for key, aliases in EMOTION_ALIASES.items():
            if raw == key or raw in aliases:
                for a in aliases:
                    if a not in variants:
                        variants.append(a)
                if key not in variants:
                    variants.append(key)

        # Если эмоция вида "pose_1" или "pose 1"
        m = re.match(r"(?:pose|поза)[_ -]?(\d+)", raw)
        if m:
            num = int(m.group(1))
            variants.extend([f"pose_{num:02d}", f"pose_{num}", f"{num:02d}", f"{num}"])

        return variants

    @staticmethod
    def get_sprites_root(editor: Any = None, project_path: Optional[str] = None) -> Optional[str]:
        """
        Находит корневую директорию спрайтов в проекте.
        Проверяет пути:
        1. Настройки fs_settings.json
        2. Рядом с файлом проекта (game/sprite, sprite/)
        3. Известные пути Violant/game/sprite
        """
        candidates: List[str] = []

        # 1. Из fs_settings.json
        cfg_paths = [
            os.path.join(os.path.dirname(__file__), "..", "plugins", "fs_settings.json"),
            os.path.join(os.getcwd(), "plugins", "fs_settings.json"),
        ]
        for cfg in cfg_paths:
            if os.path.exists(cfg):
                try:
                    with open(cfg, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("sprites"):
                            candidates.append(data["sprites"])
                except Exception:
                    pass

        # 2. Относительно файла проекта
        p_file = project_path or (getattr(editor, "current_file", None) if editor else None)
        if p_file and os.path.exists(p_file):
            proj_dir = os.path.dirname(os.path.abspath(p_file))
            candidates.extend([
                os.path.join(proj_dir, "sprite"),
                os.path.join(proj_dir, "sprites"),
                os.path.join(proj_dir, "game", "sprite"),
                os.path.join(proj_dir, "game", "sprites"),
                os.path.join(proj_dir, "images", "sprite"),
            ])

        # 3. Дефолтные пути
        candidates.extend([
            r"D:\projects\Violant\game\sprite",
            os.path.join(os.getcwd(), "sprite"),
            os.path.join(os.getcwd(), "game", "sprite"),
        ])

        for c in candidates:
            if c and os.path.isdir(c):
                return os.path.abspath(c).replace("\\", "/")

        return None

    @classmethod
    def find_all_character_sprites(
        cls,
        character_name: str,
        sprites_root: Optional[str] = None,
        editor: Any = None,
        project_path: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """
        Сканирует папку спрайтов и находит ВСЕ доступные спрайты для указанного персонажа.
        Возвращает список кортежей (label_эмоции, абсолютный_путь_к_файлу).
        """
        root = sprites_root or cls.get_sprites_root(editor=editor, project_path=project_path)
        if not root or not os.path.isdir(root):
            return []

        name_variants = cls.get_name_variants(character_name)
        results: List[Tuple[str, str]] = []

        # 1. Поиск в персональной подпапке персонажа (например, sprite/nika/)
        for name_var in name_variants:
            subfolder = os.path.join(root, name_var)
            if os.path.isdir(subfolder):
                try:
                    for f in sorted(os.listdir(subfolder)):
                        ext = os.path.splitext(f)[1].lower()
                        if ext in IMAGE_EXTENSIONS:
                            full_path = os.path.join(subfolder, f).replace("\\", "/")
                            # Извлекаем красивое имя эмоции
                            base = os.path.splitext(f)[0]
                            # Убираем префикс имени персонажа (nika_pose_01 -> pose_01)
                            for nv in name_variants:
                                if base.lower().startswith(f"{nv}_"):
                                    base = base[len(nv) + 1:]
                                    break
                            results.append((base, full_path))
                except Exception:
                    pass

        # 2. Поиск в корневой папке спрайтов (например, sprite/enjie_neutral.png)
        try:
            for f in sorted(os.listdir(root)):
                full_path = os.path.join(root, f).replace("\\", "/")
                if not os.path.isfile(full_path):
                    continue
                ext = os.path.splitext(f)[1].lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue

                base = os.path.splitext(f)[0].lower()
                for name_var in name_variants:
                    if base.startswith(f"{name_var}_") or base == name_var:
                        emo_label = base[len(name_var) + 1:] if base.startswith(f"{name_var}_") else "default"
                        # Избегаем дубликатов
                        if not any(r[1] == full_path for r in results):
                            results.append((emo_label, full_path))
                        break
        except Exception:
            pass

        return results

    @classmethod
    def resolve_sprite(
        cls,
        character_name: str,
        emotion: str = "",
        sprites_root: Optional[str] = None,
        editor: Any = None,
        project_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Автоматически находит наиболее подходящий файл спрайта для персонажа и эмоции.
        Возвращает абсолютный путь к файлу или None.
        """
        all_sprites = cls.find_all_character_sprites(
            character_name,
            sprites_root=sprites_root,
            editor=editor,
            project_path=project_path
        )
        if not all_sprites:
            return None

        # Если эмоция не указана — берем нейтральный/первый доступный спрайт
        if not emotion.strip():
            # Приоритет: neutral / pose_01 / default
            for emo_label, path in all_sprites:
                if emo_label.lower() in ("neutral", "normal", "idle", "default", "pose_01", "pose_1"):
                    return path
            return all_sprites[0][1]

        # Ищем точное или синонимичное совпадение эмоции
        emo_variants = cls.get_emotion_variants(emotion)
        for target_variant in emo_variants:
            for emo_label, path in all_sprites:
                lbl_clean = emo_label.lower()
                if lbl_clean == target_variant or target_variant in lbl_clean or lbl_clean in target_variant:
                    return path

        # Fallback: первый доступный спрайт
        return all_sprites[0][1]

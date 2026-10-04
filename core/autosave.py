"""
Dialogue Engine - Autosave and Crash Recovery Manager.
Автоматическое периодическое сохранение и обнаружение аварийных завершений работы.
"""

from __future__ import annotations
import hashlib
import os
import time
from typing import Optional, Tuple

from core.models import ProjectData
from core.serialization import ProjectSerializer, SerializationError


class AutosaveManager:
    """Управляет созданием снимков автосохранения и восстановлением после падений."""

    def __init__(self, autosave_dir: str = "Save/.autosave", interval_seconds: int = 30):
        self.autosave_dir = autosave_dir
        self.interval_seconds = interval_seconds
        self.last_save_time: float = time.time()
        os.makedirs(self.autosave_dir, exist_ok=True)

    def _get_autosave_filename(self, project_file: Optional[str]) -> str:
        """Генерирует стабильное имя файла автосохранения."""
        if project_file:
            # Хеш пути к файлу для надежного сопоставления
            base = os.path.basename(project_file)
            file_hash = hashlib.md5(project_file.encode("utf-8")).hexdigest()[:8]
            return os.path.join(self.autosave_dir, f"autosave_{base}_{file_hash}.json")
        return os.path.join(self.autosave_dir, "autosave_untitled.json")

    def save_snapshot(self, project: ProjectData, project_file: Optional[str]) -> Optional[str]:
        """Сохраняет снимок текущего состояния проекта."""
        target_path = self._get_autosave_filename(project_file)
        try:
            ProjectSerializer.save_to_file(project, target_path, create_backup=False)
            self.last_save_time = time.time()
            return target_path
        except Exception:
            return None

    def check_recovery(self, project_file: Optional[str]) -> Optional[Tuple[str, float]]:
        """
        Проверяет наличие более свежего автосохранения.
        Возвращает кортеж (путь_к_автосейву, время_модификации) если автосейв новее оригинального файла.
        """
        target_path = self._get_autosave_filename(project_file)
        if not os.path.exists(target_path):
            return None

        try:
            autosave_mtime = os.path.getmtime(target_path)
            if project_file and os.path.exists(project_file):
                orig_mtime = os.path.getmtime(project_file)
                # Если автосейв новее оригинального файла хотя бы на 5 секунд
                if autosave_mtime > orig_mtime + 5:
                    return (target_path, autosave_mtime)
                return None
            else:
                # Для безымянного проекта автосейв считается доступным
                return (target_path, autosave_mtime)
        except Exception:
            return None

    def clear_autosave(self, project_file: Optional[str]) -> None:
        """Удаляет файл автосохранения при штатном сохранении или закрытии без изменений."""
        target_path = self._get_autosave_filename(project_file)
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass

    def cleanup_old_snapshots(self, max_age_seconds: int = 7 * 86400) -> None:
        """Очищает устаревшие автосейвы старше max_age_seconds."""
        now = time.time()
        if not os.path.exists(self.autosave_dir):
            return
        for fname in os.listdir(self.autosave_dir):
            if fname.startswith("autosave_") and fname.endswith(".json"):
                fpath = os.path.join(self.autosave_dir, fname)
                try:
                    if now - os.path.getmtime(fpath) > max_age_seconds:
                        os.remove(fpath)
                except OSError:
                    pass

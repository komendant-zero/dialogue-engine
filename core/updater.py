"""
Dialogue Engine - GitHub Auto-Updater Module.
Обеспечивает автоматическое обновление движка через GitHub-репозиторий,
проверку версий, прогресс-бар в стиле Windows и безопасный перезапуск
с автоматическим сохранением открытого проекта.
"""

from __future__ import annotations
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple
import urllib.error
import urllib.request
import zipfile

from core.serialization import ProjectSerializer

logger = logging.getLogger("DialogueEngine.Updater")

GITHUB_REPO_URL = "https://github.com/komendant-zero/dialogue-engine.git"
GITHUB_API_COMMITS = "https://api.github.com/repos/komendant-zero/dialogue-engine/commits/master"
GITHUB_ZIP_URL = "https://github.com/komendant-zero/dialogue-engine/archive/refs/heads/master.zip"
DEFAULT_BRANCH = "master"
ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class EngineUpdater:
    """Сервис проверки и установки обновлений движка из GitHub."""

    @staticmethod
    def get_local_commit() -> Optional[str]:
        """Возвращает SHA-хеш текущего локального коммита через git."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=3,
                cwd=ENGINE_DIR
            )
            return res.stdout.strip()
        except Exception:
            return None

    @staticmethod
    def check_for_updates(timeout_sec: float = 3.5) -> Dict[str, Any]:
        """
        Проверяет наличие новых коммитов в GitHub-репозитории.
        Возвращает словарь с результатами проверки.
        """
        local_sha = EngineUpdater.get_local_commit()
        result: Dict[str, Any] = {
            "available": False,
            "local_sha": local_sha[:7] if local_sha else "unknown",
            "remote_sha": None,
            "commit_message": "",
            "behind_count": 0,
            "error": None,
            "offline": False
        }

        # 1. Попытка через Git CLI (наиболее надежно при наличии git)
        try:
            # git ls-remote не скачивает объекты, только читает хеш ветки
            ls_res = subprocess.run(
                ["git", "ls-remote", "origin", f"refs/heads/{DEFAULT_BRANCH}"],
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout_sec,
                cwd=ENGINE_DIR
            )
            lines = ls_res.stdout.strip().split()
            if lines:
                remote_sha = lines[0].strip()
                result["remote_sha"] = remote_sha[:7]

                if local_sha and remote_sha:
                    if local_sha != remote_sha:
                        # Запрашиваем fetch для точного подсчета
                        try:
                            subprocess.run(
                                ["git", "fetch", "origin", DEFAULT_BRANCH],
                                capture_output=True,
                                timeout=timeout_sec,
                                cwd=ENGINE_DIR
                            )
                            cnt_res = subprocess.run(
                                ["git", "rev-list", f"HEAD..origin/{DEFAULT_BRANCH}", "--count"],
                                capture_output=True,
                                text=True,
                                check=True,
                                timeout=2,
                                cwd=ENGINE_DIR
                            )
                            behind = int(cnt_res.stdout.strip() or "0")
                            result["behind_count"] = behind
                            result["available"] = (behind > 0)
                        except Exception:
                            result["available"] = True
                    else:
                        result["available"] = False
                    return result
        except Exception as e:
            # Если git не сработал или нет доступа, пробуем GitHub API
            pass

        # 2. Запасной вариант через GitHub REST API
        try:
            req = urllib.request.Request(
                GITHUB_API_COMMITS,
                headers={"User-Agent": "DialogueEngine-Updater", "Accept": "application/vnd.github.v3+json"}
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    remote_sha = data.get("sha", "")
                    commit_info = data.get("commit", {})
                    msg = commit_info.get("message", "").split("\n")[0]
                    result["remote_sha"] = remote_sha[:7]
                    result["commit_message"] = msg

                    if local_sha and remote_sha:
                        result["available"] = (local_sha != remote_sha)
                    return result
        except urllib.error.URLError as e:
            result["offline"] = True
            result["error"] = f"Нет соединения с GitHub: {e.reason}"
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def auto_save_project(editor: Any) -> Optional[str]:
        """
        Надежно сохраняет текущий проект перед обновлением.
        Если проект без имени, сохраняет аварийную копию в Save/.autosave.
        """
        if not editor:
            return None

        # Если файл уже привязан к диску, используем штатное сохранение
        if getattr(editor, "current_file", None):
            try:
                editor.save_project()
                return editor.current_file
            except Exception as e:
                logger.error(f"Не удалось штатно сохранить проект: {e}")

        # Для несохраненного проекта или дублирующей страховки
        try:
            autosave_dir = os.path.join(os.getcwd(), "Save", ".autosave")
            os.makedirs(autosave_dir, exist_ok=True)
            backup_path = os.path.join(autosave_dir, "pre_update_autosave.json")

            if hasattr(editor, "_export_to_project_data"):
                proj = editor._export_to_project_data()
                ProjectSerializer.save_to_file(proj, backup_path, create_backup=False)
                return backup_path
        except Exception as e:
            logger.error(f"Ошибка резервного автосохранения: {e}")

        return None

    @staticmethod
    def apply_git_pull(progress_cb: Optional[Callable[[str, float], None]] = None) -> Tuple[bool, str]:
        """Применяет обновление через git pull."""
        if progress_cb:
            progress_cb("Сохранение локальных настроек...", 25.0)

        # 1. Защита локальных изменений (stash)
        stashed = False
        try:
            stash_res = subprocess.run(["git", "stash"], capture_output=True, text=True, timeout=5, cwd=ENGINE_DIR)
            if "Saved working directory" in stash_res.stdout:
                stashed = True
        except Exception:
            pass

        if progress_cb:
            progress_cb("Загрузка обновлений из репозитория...", 50.0)

        # 2. git pull origin master
        try:
            pull_res = subprocess.run(
                ["git", "pull", "--ff-only", "origin", DEFAULT_BRANCH],
                capture_output=True,
                text=True,
                timeout=20,
                cwd=ENGINE_DIR
            )
            if pull_res.returncode != 0:
                # Если ff-only не сработал, пробуем обычный pull
                pull_res = subprocess.run(
                    ["git", "pull", "origin", DEFAULT_BRANCH],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    cwd=ENGINE_DIR
                )
        except Exception as e:
            if stashed:
                subprocess.run(["git", "stash", "pop"], capture_output=True, cwd=ENGINE_DIR)
            return False, f"Ошибка выполнения git pull: {e}"

        # 3. Восстанавливаем сохраненные локальные файлы
        if stashed:
            try:
                subprocess.run(["git", "stash", "pop"], capture_output=True, cwd=ENGINE_DIR)
            except Exception:
                pass

        if pull_res.returncode == 0:
            if progress_cb:
                progress_cb("Обновление файлов завершено успешно!", 100.0)
            return True, pull_res.stdout.strip()
        else:
            return False, pull_res.stderr.strip() or pull_res.stdout.strip()

    @staticmethod
    def apply_zip_download(progress_cb: Optional[Callable[[str, float], None]] = None) -> Tuple[bool, str]:
        """Запасной метод обновления: загрузка архива master.zip с GitHub."""
        try:
            if progress_cb:
                progress_cb("Загрузка архива обновления с GitHub...", 30.0)

            temp_zip = os.path.join(ENGINE_DIR, "update_temp.zip")
            req = urllib.request.Request(
                GITHUB_ZIP_URL,
                headers={"User-Agent": "DialogueEngine-Updater"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp, open(temp_zip, "wb") as out_f:
                shutil.copyfileobj(resp, out_f)

            if progress_cb:
                progress_cb("Распаковка и установка обновления...", 70.0)

            # Распаковываем
            extract_dir = os.path.join(ENGINE_DIR, "update_temp_dir")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(extract_dir)

            # Внутри архива папка вида dialogue-engine-master
            top_level = [os.path.join(extract_dir, d) for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
            src_folder = top_level[0] if top_level else extract_dir

            # Копируем поверх текущей директории кроме .git и Save
            for item in os.listdir(src_folder):
                if item in (".git", "Save", "update_temp.zip", "update_temp_dir"):
                    continue
                s_path = os.path.join(src_folder, item)
                d_path = os.path.join(ENGINE_DIR, item)
                if os.path.isdir(s_path):
                    shutil.copytree(s_path, d_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(s_path, d_path)

            # Чистим временные файлы
            try:
                os.remove(temp_zip)
                shutil.rmtree(extract_dir, ignore_errors=True)
            except Exception:
                pass

            if progress_cb:
                progress_cb("Установка завершена!", 100.0)
            return True, "Архив успешно установлен поверх проекта"
        except Exception as e:
            return False, f"Ошибка загрузки архива: {e}"

    @staticmethod
    def restart_engine(saved_project_path: Optional[str] = None) -> None:
        """Перезапускает движок с открытием сохраненного проекта."""
        main_script = os.path.join(ENGINE_DIR, "main.py")
        args = [sys.executable, main_script]
        if saved_project_path and os.path.exists(saved_project_path):
            args.append(saved_project_path)

        # Запускаем новый независимый процесс движка
        subprocess.Popen(args, cwd=ENGINE_DIR)
        # Завершаем текущий процесс
        time.sleep(0.1)
        os._exit(0)

    @classmethod
    def perform_full_update(
        cls,
        editor: Any = None,
        progress_cb: Optional[Callable[[str, float], None]] = None,
        restart_on_complete: bool = True
    ) -> Tuple[bool, str]:
        """
        Полный цикл обновления:
        1. Автосохранение текущего проекта
        2. Скачивание и применение изменений из GitHub
        3. Перезапуск движка с восстановлением проекта
        """
        saved_file = None
        if editor:
            if progress_cb:
                progress_cb("Автоматическое сохранение проекта...", 10.0)
            saved_file = cls.auto_save_project(editor)

        # 1. Попытка через git
        success, msg = cls.apply_git_pull(progress_cb)
        if not success:
            # 2. Запасная попытка через ZIP
            if progress_cb:
                progress_cb("Переключение на загрузку архива...", 20.0)
            success, msg = cls.apply_zip_download(progress_cb)

        if success and restart_on_complete:
            if progress_cb:
                progress_cb("Перезапуск Dialogue Engine...", 100.0)
            time.sleep(0.5)
            cls.restart_engine(saved_file)

        return success, msg

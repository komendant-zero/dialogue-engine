"""
Dialogue Engine - Project Serialization and Deserialization.
Обеспечивает надежное сохранение и загрузку проектов, атомную запись,
версионирование и валидацию целостности JSON.
"""

from __future__ import annotations
import json
import os
import shutil
import tempfile
import time
from typing import Any, Dict, Optional, Tuple

from core.models import CURRENT_FORMAT_VERSION, CharacterData, ConnectionData, NodeData, ProjectData, ProjectMetadata


class SerializationError(Exception):
    """Исключение при ошибках чтения или повреждении данных проекта."""
    pass


class ProjectSerializer:
    """Сервис сохранения и загрузки проектов."""

    @staticmethod
    def serialize_to_dict(project: ProjectData) -> Dict[str, Any]:
        data = project.to_dict()
        data["metadata"]["modified_at"] = time.time()
        return data

    @staticmethod
    def serialize_to_json(project: ProjectData, indent: int = 4) -> str:
        data = ProjectSerializer.serialize_to_dict(project)
        return json.dumps(data, ensure_ascii=False, indent=indent)

    @staticmethod
    def save_to_file(project: ProjectData, file_path: str, create_backup: bool = True) -> None:
        """
        Атомарно сохраняет проект в файл.
        Сначала пишет во временный файл, затем заменяет оригинал, чтобы избежать порчи при сбоях.
        """
        dir_name = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(dir_name, exist_ok=True)

        if create_backup and os.path.exists(file_path):
            backup_path = f"{file_path}.bak"
            try:
                shutil.copy2(file_path, backup_path)
            except Exception:
                pass

        json_content = ProjectSerializer.serialize_to_json(project)

        # Атомарная запись через tempfile в той же директории
        temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix="proj_tmp_", suffix=".json")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(json_content)
                f.flush()
                os.fsync(f.fileno())

            # Заменяем целевой файл
            if os.path.exists(file_path):
                os.replace(temp_path, file_path)
            else:
                os.rename(temp_path, file_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise SerializationError(f"Не удалось сохранить проект в '{file_path}': {e}") from e

    @staticmethod
    def deserialize_from_dict(data: Dict[str, Any]) -> ProjectData:
        """
        Парсит и валидирует словарь с данными проекта.
        Автоматически восстанавливает пропущенные поля и удаляет поврежденные связи.
        """
        if not isinstance(data, dict):
            raise SerializationError("Некорректный формат: корень документа должен быть JSON-объектом.")

        nodes_raw = data.get("nodes")
        if not isinstance(nodes_raw, list):
            nodes_raw = []

        conns_raw = data.get("connections")
        if not isinstance(conns_raw, list):
            conns_raw = []

        nodes: list[NodeData] = []
        seen_ids = set()

        for idx, item in enumerate(nodes_raw):
            if not isinstance(item, dict):
                continue
            try:
                node = NodeData.from_dict(item)
                # Защита от дубликатов ID
                if node.id in seen_ids:
                    node.id = f"{node.id}_{idx}"
                seen_ids.add(node.id)
                nodes.append(node)
            except Exception:
                continue

        connections: list[ConnectionData] = []
        for item in conns_raw:
            if not isinstance(item, dict):
                continue
            try:
                from_id = str(item.get("from", ""))
                to_id = str(item.get("to", ""))
                out_idx = int(item.get("out_idx", 0))

                # Очищаем связи с несуществующими узлами
                if from_id in seen_ids and to_id in seen_ids:
                    connections.append(ConnectionData(from_node=from_id, out_idx=out_idx, to_node=to_id))
            except Exception:
                continue

        meta_raw = data.get("metadata")
        metadata = ProjectMetadata.from_dict(meta_raw if isinstance(meta_raw, dict) else {})

        chars_raw = data.get("characters")
        characters: list[CharacterData] = []
        if isinstance(chars_raw, list):
            for item in chars_raw:
                if isinstance(item, dict) and item.get("name"):
                    try:
                        characters.append(CharacterData.from_dict(item))
                    except Exception:
                        continue

        return ProjectData(nodes=nodes, connections=connections, metadata=metadata, characters=characters)

    @staticmethod
    def load_from_json(json_str: str) -> ProjectData:
        """Загружает проект из строки JSON."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise SerializationError(f"Поврежденный JSON синтаксис: {e}") from e

        return ProjectSerializer.deserialize_from_dict(data)

    @staticmethod
    def load_from_file(file_path: str) -> ProjectData:
        """Загружает проект из файла на диске."""
        if not os.path.exists(file_path):
            raise SerializationError(f"Файл проекта не найден: '{file_path}'")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            # Попытка прочесть с cp1251 на случай старых файлов Windows
            try:
                with open(file_path, "r", encoding="cp1251") as f:
                    content = f.read()
            except Exception as e:
                raise SerializationError(f"Ошибка кодировки файла '{file_path}': {e}") from e
        except Exception as e:
            raise SerializationError(f"Не удалось прочитать файл '{file_path}': {e}") from e

        return ProjectSerializer.load_from_json(content)

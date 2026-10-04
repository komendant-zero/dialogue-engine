"""
Dialogue Engine - Plugin Manager with Health Monitoring and Error Isolation.
"""

from __future__ import annotations
import importlib.util
import inspect
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional, Type

from plugin_system.base import Plugin, PluginManifest, PluginStatus

logger = logging.getLogger("DialogueEngine.Plugins")


class PluginManager:
    """Управляет загрузкой, жизненным циклом и безопасной рассылкой событий плагинам."""

    def __init__(self, editor: Any, max_errors_before_disable: int = 5):
        self.editor = editor
        self.max_errors_before_disable = max_errors_before_disable
        self.plugins: List[Plugin] = []
        self._registered_classes: set[Type[Plugin]] = set()
        self._loaded_files: set[str] = set()

    def register(self, plugin_cls: Type[Plugin]) -> Optional[Plugin]:
        """Регистрирует класс плагина с изоляцией ошибок."""
        if plugin_cls in self._registered_classes:
            return None

        try:
            plugin = plugin_cls(self.editor)
            plugin.status = PluginStatus.LOADED
            self.plugins.append(plugin)
            self._registered_classes.add(plugin_cls)

            plugin.on_enable()
            plugin.status = PluginStatus.ACTIVE
            print(f"[PluginSystem] Loaded plugin: {plugin.name} v{plugin.version}")
            return plugin
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[PluginError] Failed to initialize plugin {plugin_cls.__name__}: {e}\n{tb}")
            return None

    def notify(self, event_type: str, data: Any = None) -> None:
        """Безопасно рассылает событие всем активным плагинам с изоляцией сбоев."""
        for plugin in list(self.plugins):
            if plugin.status == PluginStatus.DISABLED:
                continue

            try:
                plugin.on_event(event_type, data)
            except Exception as e:
                plugin.error_count += 1
                plugin.last_error = f"{e}\n{traceback.format_exc()}"
                print(f"[PluginError] Plugin '{plugin.name}' raised an error on '{event_type}': {e}")

                if plugin.error_count >= self.max_errors_before_disable:
                    plugin.status = PluginStatus.ERROR
                    print(f"[PluginSystem] Plugin '{plugin.name}' disabled after {plugin.error_count} errors.")

    def load_plugins_from_folder(self, folder_path: str) -> List[Plugin]:
        """Сканирует папку и безопасно загружает все модули плагинов."""
        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
                print(f"[PluginSystem] Created plugins directory: {folder_path}")
            except OSError as e:
                print(f"[PluginError] Could not create plugins directory: {e}")
                return []

        abs_folder = os.path.abspath(folder_path)
        if abs_folder not in sys.path:
            sys.path.insert(0, abs_folder)

        loaded: List[Plugin] = []
        for filename in sorted(os.listdir(folder_path)):
            if filename.endswith(".py") and not filename.startswith("__"):
                file_path = os.path.join(folder_path, filename)
                p = self._load_plugin_file(file_path, filename)
                if p:
                    loaded.extend(p)
        return loaded

    def _load_plugin_file(self, path: str, filename: str) -> List[Plugin]:
        module_name = filename[:-3]
        real_path = os.path.realpath(path)
        if real_path in self._loaded_files:
            return []

        loaded_in_file: List[Plugin] = []
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                # Регистрируем модуль в sys.modules для взаимных импортов
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                self._loaded_files.add(real_path)

                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin:
                        p = self.register(obj)
                        if p:
                            loaded_in_file.append(p)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[PluginError] Failed to load module file {filename}: {e}\n{tb}")

        return loaded_in_file

    def get_plugin(self, name: str) -> Optional[Plugin]:
        for p in self.plugins:
            if getattr(p, "name", "") == name or p.__class__.__name__ == name:
                return p
        return None

    def enable_plugin(self, name: str) -> bool:
        p = self.get_plugin(name)
        if p and p.status != PluginStatus.ACTIVE:
            try:
                p.on_enable()
                p.status = PluginStatus.ACTIVE
                p.error_count = 0
                return True
            except Exception as e:
                p.last_error = str(e)
                p.status = PluginStatus.ERROR
        return False

    def disable_plugin(self, name: str) -> bool:
        p = self.get_plugin(name)
        if p and p.status == PluginStatus.ACTIVE:
            try:
                p.on_disable()
            except Exception:
                pass
            p.status = PluginStatus.DISABLED
            return True
        return False

    def get_health_report(self) -> List[Dict[str, Any]]:
        """Возвращает отчет о состоянии всех плагинов."""
        report = []
        for p in self.plugins:
            manifest = p.get_manifest()
            report.append({
                "name": manifest.name,
                "version": manifest.version,
                "status": p.status.value,
                "errors": p.error_count,
                "last_error": p.last_error
            })
        return report

import os
import importlib.util
import inspect
import sys

class Plugin:
    """
    Базовый класс для всех плагинов.
    Плагины должны наследоваться от этого класса.
    """
    name = "BasePlugin"
    version = "1.0"
    
    def __init__(self, editor):
        self.editor = editor
    
    def on_enable(self):
        """Вызывается при загрузке плагина"""
        pass
        
    def on_event(self, event_type, data=None):
        """
        Обработка событий редактора.
        Типы событий: 'update', 'save', 'load', 'node_added', 'node_deleted'
        """
        pass

class PluginManager:
    def __init__(self, editor):
        self.editor = editor
        self.plugins = []

    def register(self, plugin_cls):
        """Регистрирует класс плагина вручную"""
        try:
            plugin = plugin_cls(self.editor)
            self.plugins.append(plugin)
            plugin.on_enable()
            print(f"[System] Plugin loaded: {plugin.name} v{plugin.version}")
        except Exception as e:
            print(f"[Error] Failed to load plugin {plugin_cls}: {e}")

    def notify(self, event_type, data=None):
        """Рассылает события всем активным плагинам"""
        for plugin in self.plugins:
            try:
                plugin.on_event(event_type, data)
            except Exception as e:
                print(f"[Error] Plugin {plugin.name} failed on event '{event_type}': {e}")

    def load_plugins_from_folder(self, folder_path):
        """
        Сканирует папку и загружает все .py файлы как плагины.
        """
        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path)
                print(f"[System] Created plugins directory: {folder_path}")
            except OSError as e:
                print(f"[Error] Could not create plugins directory: {e}")
            return

        # Добавляем путь к плагинам в sys.path, чтобы они могли импортировать модули
        sys.path.append(folder_path)

        for filename in os.listdir(folder_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                file_path = os.path.join(folder_path, filename)
                self._load_plugin_file(file_path, filename)

    def _load_plugin_file(self, path, filename):
        module_name = filename[:-3] # убираем .py
        
        try:
            # Динамическая загрузка модуля
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Ищем классы, наследующие Plugin внутри модуля
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin:
                        self.register(obj)
        except Exception as e:
            print(f"[Error] Failed to load module {filename}: {e}")
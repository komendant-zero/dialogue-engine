import tkinter as tk
from tkinter import messagebox, filedialog
from plugin_system import Plugin
import json
import os
import subprocess
import tempfile

SETTINGS_FILE = "settings.json"

class InteractivePlayerPlugin(Plugin):
    name = "Interactive VN Player (Ren'Py)"
    version = "2.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            toolbar = data
            tk.Button(
                toolbar,
                text="▶ Тест-Драйв",
                command=self.start_play,
                bg='#27ae60',
                fg='white',
                relief='flat',
                font=('Segoe UI', 9, 'bold'),
                padx=10,
                pady=5
            ).pack(side=tk.RIGHT, padx=5, pady=5)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_settings(self, settings):
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
        except:
            pass

    def find_renpy(self):
        import glob
        
        # 1. Ищем рядом с редактором
        if os.path.exists("renpy.exe"):
            return os.path.abspath("renpy.exe")
            
        # 2. Ищем в реестре (если установлена ассоциация файлов)
        try:
            import winreg
            # Ren'Py часто регистрирует себя
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Applications\renpy.exe\shell\open\command")
            val, _ = winreg.QueryValueEx(key, "")
            import shlex
            parts = shlex.split(val)
            if parts and os.path.exists(parts[0]):
                return parts[0]
        except Exception:
            pass

        # 3. Ищем в стандартных местах
        user_profile = os.environ.get('USERPROFILE', 'C:\\')
        search_dirs = [
            "C:\\",
            "C:\\Program Files",
            "C:\\Program Files (x86)",
            os.path.join(user_profile, "Desktop"),
            os.path.join(user_profile, "Downloads"),
            os.path.join(user_profile, "Documents")
        ]
        
        for base_dir in search_dirs:
            if not os.path.exists(base_dir):
                continue
                
            # Ищем папки вида renpy-8.1.1-sdk, renpy-7.5.3-sdk и т.д.
            for path in glob.glob(os.path.join(base_dir, "renpy-*")):
                exe_path = os.path.join(path, "renpy.exe")
                if os.path.exists(exe_path):
                    return exe_path
            
            # Проверяем папку просто renpy
            exe_path = os.path.join(base_dir, "renpy", "renpy.exe")
            if os.path.exists(exe_path):
                return exe_path
                
        return None

    def start_play(self):
        nodes = self.editor.nodes
        connections = self.editor.connections

        if not nodes:
            messagebox.showwarning("Пусто", "Нет узлов для воспроизведения!")
            return

        settings = self.load_settings()
        renpy_path = settings.get("renpy_path", "")

        if not renpy_path or not os.path.exists(renpy_path):
            renpy_path = self.find_renpy()
            
            if not renpy_path:
                messagebox.showinfo("Ren'Py не найден", "Не удалось найти Ren'Py автоматически.\nПожалуйста, укажите путь к исполняемому файлу (renpy.exe)")
                renpy_path = filedialog.askopenfilename(title="Выберите renpy.exe", filetypes=[("Ren'Py Executable", "renpy.exe*"), ("All Files", "*.*")])
                if not renpy_path:
                    return
            else:
                print(f"Ren'Py автоматически найден по пути: {renpy_path}")
                
            settings["renpy_path"] = renpy_path
            self.save_settings(settings)

        # Найти плагин экспорта
        exporter = None
        for p in self.editor.plugin_manager.plugins:
            if type(p).__name__ == "RenpyExporterPlugin":
                exporter = p
                break

        if not exporter:
            messagebox.showerror("Ошибка", "Плагин RenpyExporterPlugin не найден! Невозможно выполнить экспорт.")
            return

        # Создать временную директорию проекта Ren'Py
        temp_project_dir = os.path.join(tempfile.gettempdir(), "renpy_test_drive")
        game_dir = os.path.join(temp_project_dir, "game")
        
        if not os.path.exists(game_dir):
            os.makedirs(game_dir)

        # Вызываем экспорт
        success, msg = exporter.do_export(game_dir, nodes, connections)
        if not success:
            messagebox.showerror("Ошибка экспорта", msg)
            return

        import shutil
        project_dir = os.path.abspath(os.getcwd())
        
        # Копируем все .rpy файлы из проекта во временную папку, чтобы они скомпилировались
        for file in os.listdir(project_dir):
            if file.endswith('.rpy'):
                shutil.copy(os.path.join(project_dir, file), os.path.join(game_dir, file))

        # Создаем файл инициализации для путей
        project_dir = os.path.abspath(os.getcwd())
        init_file = os.path.join(game_dir, "test_drive_init.rpy")
        with open(init_file, "w", encoding="utf-8") as f:
            f.write("python early:\n")
            f.write(f'    config.searchpath.append(r"{project_dir}")\n\n')
            f.write("init python:\n")
            f.write("    # Отключаем подтверждение выхода и меню, так как в проекте пока нет экранов (screens.rpy)\n")
            f.write("    config.quit_action = Quit(confirm=False)\n")
            f.write("    config.game_menu_action = None\n")
            f.write("\ninit 99 python:\n")
            f.write("    config.window_icon = None\n")
            f.write("    gui.window_icon = None\n")
            f.write("\nlabel main_menu:\n")
            f.write("    return\n")

        # Запуск Ren'Py
        try:
            # Запускаем renpy.exe с путем к проекту
            subprocess.Popen([renpy_path, temp_project_dir])
        except Exception as e:
            messagebox.showerror("Ошибка запуска", f"Не удалось запустить Ren'Py:\n{e}")

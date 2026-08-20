import tkinter as tk
from tkinter import messagebox
from plugin_system import Plugin
import subprocess
import sys
import os

class DevReloaderPlugin(Plugin):
    name = "Dev Reloader"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            toolbar = data
            btn = tk.Button(
                toolbar, text="🔄 Перезапустить (Dev)", 
                command=self.restart_engine, 
                bg='#c0392b', fg='white', relief='flat', 
                padx=10, pady=5, font=('Segoe UI', 9, 'bold')
            )
            # Добавляем кнопку в правую часть тулбара
            btn.pack(side=tk.RIGHT, padx=5, pady=5)

    def restart_engine(self):
        # 1. Сначала сохраняем проект
        self.editor.save_project()

        # Если после сохранения файл так и не был выбран (пользователь отменил Save As)
        # можно всё равно перезапустить, но лучше предупредить
        if self.editor.is_dirty:
            if not messagebox.askyesno("Внимание", "Проект не был сохранен. Точно перезапустить движок с потерей изменений?"):
                return
        
        # 2. Формируем команду для запуска
        args = [sys.executable, sys.argv[0]]
        
        # Если проект был сохранен в файл, передаем его путь как аргумент,
        # чтобы при перезапуске проект сразу открылся (так как main.py это поддерживает)
        if hasattr(self.editor, 'current_file') and self.editor.current_file:
            args.append(self.editor.current_file)
            
        # 3. Перезапускаем процесс
        subprocess.Popen(args)
        
        # 4. Убиваем текущий
        self.editor.quit()
        sys.exit(0)

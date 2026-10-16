import tkinter as tk
from tkinter import messagebox
from plugin_system import Plugin
import os
import time

class ReloadPlugin(Plugin):
    name = "Project Reloader & Live Watcher"
    version = "1.1"

    def __init__(self, editor):
        super().__init__(editor)
        self._last_mtime = 0
        self._auto_watch_enabled = True
        self._watch_job = None

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            if hasattr(self.editor, 'project_menu'):
                self.editor.project_menu.add_command(label="🔄 Обновить из файла (F5)", command=self.reload_file)
                self.editor.bind("<F5>", lambda e: self.reload_file())
            else:
                toolbar = data
                tk.Button(
                    toolbar,
                    text="🔄 Обновить (F5)",
                    command=self.reload_file,
                    bg='#3498db',
                    fg='white',
                    relief='flat',
                    font=('Segoe UI', 9),
                    padx=8,
                    pady=3
                ).pack(side=tk.RIGHT, padx=3)
            
            self._start_watcher()

    def _start_watcher(self):
        if self._watch_job:
            try:
                self.editor.after_cancel(self._watch_job)
            except Exception:
                pass
        self._check_file_change()

    def _check_file_change(self):
        try:
            filepath = getattr(self.editor, 'current_file', None)
            if filepath and os.path.exists(filepath):
                current_mtime = os.path.getmtime(filepath)
                if self._last_mtime == 0:
                    self._last_mtime = current_mtime
                elif current_mtime > self._last_mtime + 0.1:
                    self._last_mtime = current_mtime
                    # Если холст чистый (нет несохранённых ручных правок пользователя), обновляем тихо
                    if not getattr(self.editor, 'is_dirty', False):
                        self._silent_reload(filepath)
                    else:
                        if hasattr(self.editor, 'status_bar'):
                            self.editor.status_bar.config(text="⚠️ Файл на диске обновлен. Нажмите F5 для перезагрузки.")
        except Exception:
            pass

        # Проверяем каждую секунду
        self._watch_job = self.editor.after(1000, self._check_file_change)

    def _silent_reload(self, filepath):
        try:
            if hasattr(self.editor, 'plugin_manager') and self.editor.plugin_manager:
                self.editor.plugin_manager.notify('clear_cache')
            self.editor.load_project(file_path=filepath)
            if hasattr(self.editor, 'status_bar'):
                self.editor.status_bar.config(text="✅ Проект автоматически синхронизирован с файлом")
        except Exception:
            pass

    def reload_file(self):
        if not hasattr(self.editor, 'current_file') or not self.editor.current_file:
            messagebox.showinfo("Инфо", "Сначала загрузите проект (.json), чтобы привязать файл.", parent=self.editor)
            return
            
        filepath = self.editor.current_file
        if not os.path.exists(filepath):
            messagebox.showerror("Ошибка", f"Файл не найден на диске:\n{filepath}", parent=self.editor)
            return
            
        if self.editor.is_dirty:
            resp = messagebox.askyesno("Внимание", "У вас есть несохраненные изменения в редакторе!\nПерезагрузка уничтожит их. Вы уверены, что хотите загрузить последнюю версию из файла?", parent=self.editor)
            if not resp:
                return
                
        try:
            if hasattr(self.editor, 'plugin_manager') and self.editor.plugin_manager:
                self.editor.plugin_manager.notify('clear_cache')
                    
            self.editor.load_project(file_path=filepath)
            self._last_mtime = os.path.getmtime(filepath)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить файл:\n{e}", parent=self.editor)


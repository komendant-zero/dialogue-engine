import tkinter as tk
from tkinter import messagebox
from plugin_system import Plugin
import os

class ReloadPlugin(Plugin):
    name = "Project Reloader"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            toolbar = data
            tk.Button(
                toolbar,
                text="🔄 Обновить из файла",
                command=self.reload_file,
                bg='#3498db',
                fg='white',
                relief='flat',
                font=('Segoe UI', 9, 'bold'),
                padx=10,
                pady=5
            ).pack(side=tk.RIGHT, padx=5, pady=5)

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
            # Очищаем кэши изображений, если загружены плагины
            import sys
            if 'media_node' in sys.modules:
                if hasattr(sys.modules['media_node'], 'IMAGE_CACHE'):
                    sys.modules['media_node'].IMAGE_CACHE.clear()
                if hasattr(sys.modules['media_node'], 'SIZE_CACHE'):
                    sys.modules['media_node'].SIZE_CACHE.clear()
                    
            self.editor.load_project(file_path=filepath)
            # Уведомление об успешном обновлении (можно закомментировать, если мешает)
            # messagebox.showinfo("Успех", "Проект успешно обновлен из файла!", parent=self.editor)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить файл:\n{e}", parent=self.editor)

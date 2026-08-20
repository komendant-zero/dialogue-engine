import tkinter as tk
from tkinter import messagebox
from plugin_system import Plugin
import subprocess
import threading
import sys
import os

class UpdaterPlugin(Plugin):
    name = "Auto Updater"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            toolbar = data
            btn = tk.Button(
                toolbar, text="🔄 Обновить", 
                command=self.update_engine, 
                bg='#e67e22', fg='white', relief='flat', 
                padx=10, pady=5, font=('Segoe UI', 9, 'bold')
            )
            # Добавляем кнопку в правую часть тулбара
            btn.pack(side=tk.RIGHT, padx=5, pady=5)

    def update_engine(self):
        if not messagebox.askyesno("Обновление", "Сохранить текущий проект и загрузить последнюю версию движка с GitHub?"):
            return

        # Сначала просим пользователя сохранить проект
        self.editor.save_project()

        # Создаем окно с прогрессом
        progress_win = tk.Toplevel(self.editor)
        progress_win.title("Обновление...")
        progress_win.geometry("300x100")
        progress_win.configure(bg='#2b2b2b')
        progress_win.transient(self.editor)
        progress_win.grab_set()

        lbl = tk.Label(progress_win, text="Загрузка обновления через git pull...\nПожалуйста, подождите.", bg='#2b2b2b', fg='white', font=("Segoe UI", 10))
        lbl.pack(expand=True, fill=tk.BOTH)

        def task():
            try:
                # Используем shell=True, чтобы git.exe точно нашелся в системе
                result = subprocess.run("git pull origin master", capture_output=True, text=True, shell=True, check=True)
                output = result.stdout.strip()
                
                self.editor.after(0, lambda: self.on_update_success(output, progress_win))
            except subprocess.CalledProcessError as e:
                self.editor.after(0, lambda: self.on_update_error(e.stderr or e.stdout, progress_win))
            except Exception as e:
                self.editor.after(0, lambda: self.on_update_error(str(e), progress_win))

        # Запускаем в отдельном потоке, чтобы интерфейс не зависал
        threading.Thread(target=task, daemon=True).start()

    def on_update_success(self, output, progress_win):
        progress_win.destroy()
        
        if "Already up to date." in output or "Уже обновлено." in output:
            messagebox.showinfo("Обновление", "У вас уже установлена самая последняя версия движка!")
            return
            
        msg = f"Движок успешно обновлен!\n\nGit output:\n{output}\n\nДвижок будет перезапущен."
        messagebox.showinfo("Готово", msg)
        
        # Перезапускаем текущий Python-процесс с тем же скриптом
        subprocess.Popen([sys.executable, sys.argv[0]])
        self.editor.quit()
        sys.exit(0)

    def on_update_error(self, error_text, progress_win):
        progress_win.destroy()
        messagebox.showerror("Ошибка обновления", f"Не удалось обновить движок (проверьте интернет или конфликты git):\n\n{error_text}")

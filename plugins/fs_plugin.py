import tkinter as tk
from tkinter import ttk, filedialog
import os
import json
from plugin_system import Plugin

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'fs_settings.json')

class FileSystemPlugin(Plugin):
    name = "Файловая Система (Drag & Drop)"
    version = "1.0"

    def on_enable(self):
        self.settings = {
            "backgrounds": "",
            "sprites": "",
            "music": "",
            "sounds": "",
            "voice": ""
        }
        self.load_settings()
        self.current_category = "backgrounds"
        self.drag_data = {"item": None}
        self.cached_files = set()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.settings.update(json.load(f))
            except:
                pass

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[FS Plugin] Failed to save settings: {e}")

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            # Добавляем боковую панель
            self.editor.canvas.pack_forget()
            
            self.sidebar = tk.Frame(self.editor, width=220, bg='#252526', highlightbackground='#333', highlightthickness=1)
            self.sidebar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Возвращаем холст на место
            self.editor.canvas.pack(fill=tk.BOTH, expand=True)
            
            # Заголовок
            header_frame = tk.Frame(self.sidebar, bg='#333')
            header_frame.pack(fill=tk.X)
            tk.Label(header_frame, text="Файловая система", bg='#333', fg='white', font=("Segoe UI", 10, "bold"), pady=8).pack()
            tk.Button(header_frame, text="⚙ Настроить папки", command=self.open_settings, bg='#007acc', fg='white', relief='flat').pack(fill=tk.X, padx=5, pady=4)
            
            # Выбор категории
            cat_frame = tk.Frame(self.sidebar, bg='#252526')
            cat_frame.pack(fill=tk.X, padx=5, pady=5)
            
            self.cat_var = tk.StringVar(value="backgrounds")
            cats = [("🖼 Фоны", "backgrounds"), ("🧍 Спрайты", "sprites"), ("🎵 Музыка", "music"), ("🔊 Звуки", "sounds"), ("🗣 Озвучка", "voice")]
            
            self.cat_buttons = {}
            for text, val in cats:
                btn = tk.Button(cat_frame, text=text, anchor='w', command=lambda v=val: self.set_category(v), 
                                bg='#333333', fg='white', relief='flat', padx=10, pady=4)
                btn.pack(side=tk.TOP, fill=tk.X, pady=1)
                self.cat_buttons[val] = btn
                
            self.update_buttons_visual()

            # Список файлов
            list_frame = tk.Frame(self.sidebar, bg='#1e1e1e')
            list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.listbox = tk.Listbox(list_frame, bg='#1e1e1e', fg='#d4d4d4', selectbackground='#007acc', 
                                      relief='flat', yscrollcommand=scrollbar.set, font=("Segoe UI", 9))
            self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=self.listbox.yview)
            
            # Привязка drag-n-drop
            self.listbox.bind("<ButtonPress-1>", self.on_drag_start)
            self.listbox.bind("<B1-Motion>", self.on_drag_motion)
            self.listbox.bind("<ButtonRelease-1>", self.on_drag_release)
            
            self.refresh_list()
            self.editor.after(1000, self.auto_refresh)

    def auto_refresh(self):
        try:
            cat = self.cat_var.get()
            path = self.settings.get(cat, "")
            if path and os.path.exists(path):
                current_files = set(f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)))
                if current_files != getattr(self, 'cached_files', set()):
                    self.refresh_list()
        except:
            pass
        if hasattr(self, 'editor') and hasattr(self.editor, 'after'):
            self.editor.after(1000, self.auto_refresh)

    def set_category(self, cat):
        self.cat_var.set(cat)
        self.update_buttons_visual()
        self.refresh_list()
        
    def update_buttons_visual(self):
        curr = self.cat_var.get()
        for val, btn in self.cat_buttons.items():
            if val == curr:
                btn.config(bg='#007acc')
            else:
                btn.config(bg='#333333')

    def open_settings(self):
        win = tk.Toplevel(self.editor)
        win.title("Пути к медиафайлам")
        win.geometry("500x260")
        win.configure(bg='#252526')
        win.transient(self.editor)
        win.grab_set()
        
        cats = [("Фоны (Backgrounds):", "backgrounds"), 
                ("Спрайты (Sprites):", "sprites"), 
                ("Музыка (Music):", "music"), 
                ("Звуки (Sounds):", "sounds"),
                ("Озвучка (Voice):", "voice")]
                
        self.path_vars = {}
        
        for i, (label, key) in enumerate(cats):
            tk.Label(win, text=label, bg='#252526', fg='white', font=("Segoe UI", 9)).grid(row=i, column=0, padx=10, pady=10, sticky='e')
            var = tk.StringVar(value=self.settings.get(key, ""))
            self.path_vars[key] = var
            tk.Entry(win, textvariable=var, width=35, bg='#3c3c3c', fg='white', relief='flat').grid(row=i, column=1, padx=5, pady=10)
            
            def browse(k=key, v=var):
                d = filedialog.askdirectory(initialdir=v.get() if os.path.exists(v.get()) else ".")
                if d:
                    v.set(d)
                    
            tk.Button(win, text="Обзор", command=browse, bg='#333', fg='white', relief='flat').grid(row=i, column=2, padx=10, pady=10)

        def save():
            for k, v in self.path_vars.items():
                self.settings[k] = v.get()
            self.save_settings()
            self.refresh_list()
            win.destroy()

        tk.Button(win, text="Сохранить пути", command=save, bg='#007acc', fg='white', relief='flat', width=20, pady=5).grid(row=4, column=0, columnspan=3, pady=15)

    def refresh_list(self):
        selection = self.listbox.curselection()
        sel_val = self.listbox.get(selection[0]) if selection else None
        
        self.listbox.delete(0, tk.END)
        cat = self.cat_var.get()
        path = self.settings.get(cat, "")
        
        if not path or not os.path.exists(path):
            self.listbox.insert(tk.END, "(Папка не задана или не найдена)")
            self.cached_files = set()
            return
            
        try:
            files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
            self.cached_files = set(files)
            allowed = []
            if cat in ["backgrounds", "sprites"]:
                allowed = ['.png', '.jpg', '.jpeg', '.webp', '.bmp']
            elif cat in ["music", "sounds", "voice"]:
                allowed = ['.mp3', '.ogg', '.wav']
                
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if not allowed or ext in allowed:
                    self.listbox.insert(tk.END, f)
                    
            if sel_val:
                try:
                    idx = self.listbox.get(0, tk.END).index(sel_val)
                    self.listbox.selection_set(idx)
                except ValueError:
                    pass
        except Exception as e:
            self.listbox.insert(tk.END, f"(Ошибка чтения: {e})")
            self.cached_files = set()

    def on_drag_start(self, event):
        # Determine which item was clicked based on y coordinate
        index = self.listbox.nearest(event.y)
        if index < 0:
            self.drag_data["item"] = None
            return
            
        # Optional: check if the click is actually on the item
        bbox = self.listbox.bbox(index)
        if not bbox or not (bbox[1] <= event.y <= bbox[1] + bbox[3]):
            self.drag_data["item"] = None
            return

        val = self.listbox.get(index)
        if val.startswith("("): # our error/empty messages
            self.drag_data["item"] = None
            return
            
        self.drag_data["item"] = val
        self.drag_data["cat"] = self.cat_var.get()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(index)
        
    def on_drag_motion(self, event):
        pass # Optional visual feedback

    def on_drag_release(self, event):
        if not self.drag_data.get("item"):
            return
            
        x, y = event.x_root, event.y_root
        canvas = self.editor.canvas
        
        try:
            cx = canvas.winfo_rootx()
            cy = canvas.winfo_rooty()
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            
            # Если отпустили над холстом
            if cx <= x <= cx + cw and cy <= y <= cy + ch:
                canvas_x = canvas.canvasx(x - cx)
                canvas_y = canvas.canvasy(y - cy)
                
                self.create_node_from_drop(self.drag_data["item"], self.drag_data["cat"], canvas_x, canvas_y)
        except:
            pass
            
        self.drag_data["item"] = None

    def create_node_from_drop(self, filename, category, x, y):
        base_path = self.settings.get(category, "")
        full_path = os.path.join(base_path, filename).replace("\\", "/")
        name_no_ext = os.path.splitext(filename)[0]

        if category in ["music", "sounds", "voice"]:
            if category == "music": mode = 'bg'
            elif category == "sounds": mode = 'sfx'
            else: mode = 'voice'
            icon = "🔁" if mode == 'bg' else "🗣️"
            content = f"{icon} {mode.upper()}\n📂: {filename}"
            custom_data = {
                'music_mode': mode,
                'music_file': full_path,
                'bg_color': '#196f3d',
                'header_color': '#0d4528'
            }
            self.editor.add_node('music', x=x, y=y, title=filename, content=content, custom_data=custom_data)
            
        elif category in ["backgrounds", "sprites"]:
            mode = "background" if category == "backgrounds" else "sprite"
            data_dict = {
                "image_path": full_path,
                "mode": mode,
                "position": "center",
                "transition": "none"
            }
            content = json.dumps(data_dict, ensure_ascii=False)
            self.editor.add_node('media', x=x, y=y, title=name_no_ext, content=content)

import tkinter as tk
from tkinter import filedialog
from plugin_system import Plugin
import json
import sys
import os

class EyeBlinkPlugin(Plugin):
    name = "EyeBlink Animation"
    version = "1.0"

    def __init__(self, editor):
        super().__init__(editor)
        main_module = sys.modules['__main__']
        self.NodeClass = getattr(main_module, 'Node', None)
        self.EditorClass = getattr(main_module, 'ScenarioEditor', None)
        self.COLORS = getattr(main_module, 'COLORS', {})

        if self.NodeClass:
            self.original_draw = self.NodeClass.draw
            self.original_calculate_size = self.NodeClass.calculate_size
        if self.EditorClass:
            self.original_edit_node = self.EditorClass.edit_node

    def on_enable(self):
        plugin_self = self

        def new_draw(node_self, canvas):
            if node_self.node_type != 'blink_def':
                plugin_self.original_draw(node_self, canvas)
                return

            x, y, w, h = node_self.x, node_self.y, node_self.width, node_self.height

            try:
                data = json.loads(node_self.content)
            except Exception:
                data = {}

            # Background
            canvas.create_rectangle(x, y, x+w, y+h, fill='#34495e', outline=plugin_self.COLORS.get('grid_bold', '#555'), width=2, tags=("node", node_self.id))
            
            # Header
            header_height = 25
            canvas.create_rectangle(x, y, x+w, y+header_height, fill='#2980b9', outline="", tags=("node", node_self.id))
            canvas.create_text(x+10, y+12, text=f"👁 {node_self.title}", fill="white", anchor="w", font=("Segoe UI", 9, "bold"), tags=("node", node_self.id))

            # Content
            info = f"Min Pause: {data.get('min_pause', 2.0)}s\nMax Pause: {data.get('max_pause', 4.0)}s\n[ATL Animation]"
            canvas.create_text(x + w/2, y + header_height + (h - header_height)/2, text=info, fill="#ecf0f1", font=("Segoe UI", 8), justify="center", tags=("node", node_self.id))

            # No ports needed for definition nodes, but we draw them to avoid errors if user tries to connect
            node_self.draw_input_port(canvas, x, y + h/2)
            node_self.draw_port(canvas, x+w, y + h/2, 0)

        def new_calculate_size(node_self):
            if node_self.node_type != 'blink_def':
                plugin_self.original_calculate_size(node_self)
                return
            node_self.width = 160
            node_self.height = 100

        def new_edit_node(editor_self, node):
            if node.node_type == 'blink_def':
                BlinkEditorDialog(editor_self, node, plugin_self.editor.redraw)
            else:
                plugin_self.original_edit_node(editor_self, node)

        self.NodeClass.draw = new_draw
        self.NodeClass.calculate_size = new_calculate_size
        self.EditorClass.edit_node = new_edit_node
        print(f"[{self.name}] Logic injected.")

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            if not hasattr(self.editor, 'plugin_menu'):
                self.editor.plugin_menu_btn = tk.Menubutton(
                    data, text="🧩 Компоненты ▾", bg='#444', fg='white',
                    relief='flat', font=('Segoe UI', 9, 'bold'), padx=10, pady=5
                )
                self.editor.plugin_menu_btn.pack(side=tk.LEFT, padx=5, pady=5)
                self.editor.plugin_menu = tk.Menu(self.editor.plugin_menu_btn, tearoff=0, bg='#444', fg='white')
                self.editor.plugin_menu_btn["menu"] = self.editor.plugin_menu

            self.editor.plugin_menu.add_command(label="👁 Моргание (Настройка)", command=self.create_blink_node)

        # Export logic
        elif event_type == 'renpy_export_init':
            f = data['file']
            nodes = data['nodes']
            for node in nodes:
                if node.node_type == 'blink_def':
                    try:
                        cfg = json.loads(node.content)
                        char_name = node.title
                        open_img = cfg.get("open_image", "open.png")
                        closed_img = cfg.get("closed_image", "closed.png")
                        min_p = cfg.get("min_pause", 2.0)
                        max_p = cfg.get("max_pause", 4.0)
                        
                        f.write(f"# --- Анимация моргания: {char_name} ---\n")
                        f.write(f"image {char_name}:\n")
                        f.write(f'    "{open_img}"\n')
                        f.write(f'    choice:\n')
                        f.write(f'        pause {min_p}\n')
                        
                        # Добавим промежуточный шаг если макс значительно больше мин
                        mid_p = min_p + (max_p - min_p) / 2.0
                        if mid_p > min_p:
                            f.write(f'    choice:\n')
                            f.write(f'        pause {mid_p}\n')
                        
                        f.write(f'    choice:\n')
                        f.write(f'        pause {max_p}\n')
                        f.write(f'    "{closed_img}"\n')
                        f.write(f'    pause 0.1\n')
                        f.write(f'    repeat\n\n')
                    except Exception as e:
                        f.write(f"# [Ошибка экспорта моргания: {e}]\n\n")

        elif event_type == 'renpy_export_check':
            if data['node'].node_type == 'blink_def':
                data['skip'] = True


    def create_blink_node(self):
        default_data = {
            "open_image": "open.png",
            "closed_image": "closed.png",
            "min_pause": 2.0,
            "max_pause": 4.0
        }
        self.editor.add_node(
            ntype='blink_def',
            title="sylvie blink",
            content=json.dumps(default_data)
        )


class BlinkEditorDialog:
    def __init__(self, parent, node, callback):
        self.node = node
        self.callback = callback

        try:
            self.data = json.loads(node.content)
        except Exception:
            self.data = {
                "open_image": "",
                "closed_image": "",
                "min_pause": 2.0,
                "max_pause": 4.0
            }

        self.win = tk.Toplevel(parent)
        self.win.title("Настройки Моргания")
        self.win.geometry("400x450")
        self.win.configure(bg='#2b2b2b')
        self.win.transient(parent)
        self.win.grab_set()

        lbl_style = {'bg': '#2b2b2b', 'fg': 'white', 'font': ('Segoe UI', 10)}

        tk.Label(self.win, text="Имя анимации в Ren'Py (напр. sylvie blink):", **lbl_style).pack(pady=5)
        self.e_title = tk.Entry(self.win, bg='#444', fg='white')
        self.e_title.insert(0, node.title)
        self.e_title.pack(fill=tk.X, padx=20)
        
        # Open Eye
        tk.Label(self.win, text="Имя картинки 'Открытые глаза':", **lbl_style).pack(pady=(15,5))
        self.e_open = tk.Entry(self.win, bg='#444', fg='white')
        self.e_open.insert(0, self.data.get("open_image", ""))
        self.e_open.pack(fill=tk.X, padx=20)

        # Closed Eye
        tk.Label(self.win, text="Имя картинки 'Закрытые глаза':", **lbl_style).pack(pady=(15,5))
        self.e_closed = tk.Entry(self.win, bg='#444', fg='white')
        self.e_closed.insert(0, self.data.get("closed_image", ""))
        self.e_closed.pack(fill=tk.X, padx=20)

        # Pauses
        f_pauses = tk.Frame(self.win, bg='#2b2b2b')
        f_pauses.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Label(f_pauses, text="Мин. пауза (сек):", **lbl_style).grid(row=0, column=0, padx=5, sticky='e')
        self.e_min = tk.Entry(f_pauses, bg='#444', fg='white', width=10)
        self.e_min.insert(0, str(self.data.get("min_pause", 2.0)))
        self.e_min.grid(row=0, column=1)

        tk.Label(f_pauses, text="Макс. пауза (сек):", **lbl_style).grid(row=0, column=2, padx=5, sticky='e')
        self.e_max = tk.Entry(f_pauses, bg='#444', fg='white', width=10)
        self.e_max.insert(0, str(self.data.get("max_pause", 4.0)))
        self.e_max.grid(row=0, column=3)

        tk.Button(self.win, text="💾 Сохранить", command=self.save, bg='#27ae60', fg='white', width=20).pack(side=tk.BOTTOM, pady=20)

    def save(self):
        self.node.title = self.e_title.get()
        self.data["open_image"] = self.e_open.get()
        self.data["closed_image"] = self.e_closed.get()
        
        try:
            self.data["min_pause"] = float(self.e_min.get())
        except ValueError:
            self.data["min_pause"] = 2.0
            
        try:
            self.data["max_pause"] = float(self.e_max.get())
        except ValueError:
            self.data["max_pause"] = 4.0

        self.node.content = json.dumps(self.data, ensure_ascii=False)
        self.node.calculate_size()
        self.callback()
        self.win.destroy()

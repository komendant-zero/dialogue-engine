import tkinter as tk
from tkinter import ttk
from plugin_system import Plugin
import json
import sys

class AnimationPlugin(Plugin):
    name = "AnimationNode"
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
            if node_self.node_type != 'animation':
                plugin_self.original_draw(node_self, canvas)
                return

            x, y, w, h = node_self.x, node_self.y, node_self.width, node_self.height

            try:
                data = json.loads(node_self.content)
            except Exception:
                data = {}

            anim = data.get("animation", "fade")
            duration = data.get("duration", 0.5)
            target = data.get("target", "screen")

            # Background
            canvas.create_rectangle(x, y, x+w, y+h, fill='#d35400', outline=plugin_self.COLORS.get('grid_bold', '#555'), width=2, tags=("node", node_self.id))
            
            # Header
            header_height = 25
            canvas.create_rectangle(x, y, x+w, y+header_height, fill='#e67e22', outline="", tags=("node", node_self.id))
            canvas.create_text(x+10, y+12, text=f"✨ {node_self.title}", fill="white", anchor="w", font=("Segoe UI", 9, "bold"), tags=("node", node_self.id))

            # Content
            info = f"Type: {anim}\nTarget: {target}\nTime: {duration}s"
            canvas.create_text(x + w/2, y + header_height + (h - header_height)/2, text=info, fill="white", font=("Segoe UI", 9), justify="center", tags=("node", node_self.id))

            # Ports
            node_self.draw_input_port(canvas, x, y + h/2)
            node_self.draw_port(canvas, x+w, y + h/2, 0)

        def new_calculate_size(node_self):
            if node_self.node_type != 'animation':
                plugin_self.original_calculate_size(node_self)
                return
            node_self.width = 160
            node_self.height = 90

        def new_edit_node(editor_self, node):
            if node.node_type == 'animation':
                AnimationEditorDialog(editor_self, node, plugin_self.editor.redraw)
            else:
                plugin_self.original_edit_node(editor_self, node)

        self.NodeClass.draw = new_draw
        self.NodeClass.calculate_size = new_calculate_size
        self.EditorClass.edit_node = new_edit_node
        print(f"[{self.name}] Logic injected.")

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            if not hasattr(self.editor, 'anim_menu'):
                self.editor.anim_menu_btn = tk.Menubutton(
                    data, text="🎬 Анимации ▾", bg='#8e44ad', fg='white',
                    relief='flat', font=('Segoe UI', 9, 'bold'), padx=10, pady=5
                )
                self.editor.anim_menu_btn.pack(side=tk.LEFT, padx=5, pady=5)
                self.editor.anim_menu = tk.Menu(self.editor.anim_menu_btn, tearoff=0, bg='#444', fg='white')
                self.editor.anim_menu_btn["menu"] = self.editor.anim_menu

            self.editor.anim_menu.add_command(label="✨ Анимация", command=self.create_anim_node)

        # Export logic
        elif event_type == 'renpy_export_node':
            node = data['node']
            if node.node_type == 'animation':
                f = data['file']
                connections = data['connections']
                
                try:
                    cfg = json.loads(node.content)
                    target = cfg.get("target", "screen")
                    anim = cfg.get("animation", "fade")
                    duration = float(cfg.get("duration", 0.5))
                except:
                    target = "screen"
                    anim = "fade"
                    duration = 0.5
                
                if target == "black_screen (Затемнение)":
                    f.write(f'    scene black with Dissolve({duration})\n')
                else:
                    # Generic screen transition
                    if anim.lower() != 'none':
                        if duration != 0.5 and (anim.lower() == 'dissolve' or anim.lower() == 'fade'):
                            f.write(f'    with Dissolve({duration})\n')
                        else:
                            f.write(f'    with {anim}\n')
                
                out_conns = [c for c in connections if c['from'] == node.id]
                if out_conns:
                    target_id = out_conns[0]['to']
                    f.write(f'    jump node_{target_id}\n')
                else:
                    f.write('    return\n')
                
                data['handled'] = True

    def create_anim_node(self):
        default_data = {
            "animation": "fade",
            "duration": 0.5,
            "target": "screen"
        }
        self.editor.add_node(
            ntype='animation',
            title="Animation",
            content=json.dumps(default_data)
        )

class AnimationEditorDialog:
    def __init__(self, parent, node, callback):
        self.node = node
        self.callback = callback

        try:
            self.data = json.loads(node.content)
        except Exception:
            self.data = {
                "animation": "fade",
                "duration": 0.5,
                "target": "screen"
            }

        self.data.setdefault("animation", "fade")
        self.data.setdefault("duration", 0.5)
        self.data.setdefault("target", "screen")

        self.win = tk.Toplevel(parent)
        self.win.title("Настройки Анимации")
        self.win.geometry("300x400")
        self.win.configure(bg='#2b2b2b')
        self.win.transient(parent)
        self.win.grab_set()

        lbl_style = {'bg': '#2b2b2b', 'fg': 'white', 'font': ('Segoe UI', 10)}

        tk.Label(self.win, text="Название узла:", **lbl_style).pack(pady=5)
        self.e_title = tk.Entry(self.win, bg='#444', fg='white')
        self.e_title.insert(0, node.title)
        self.e_title.pack(fill=tk.X, padx=20)
        
        tk.Label(self.win, text="Что анимируем (Цель):", **lbl_style).pack(pady=(15,5))
        self.e_target = ttk.Combobox(self.win, values=["screen", "black_screen (Затемнение)", "master", "background", "sprite"])
        self.e_target.set(self.data["target"])
        self.e_target.pack(fill=tk.X, padx=20)

        tk.Label(self.win, text="Тип анимации:", **lbl_style).pack(pady=(15, 5))
        transitions = [
            "none", "dissolve", "fade", "pixellate",
            "move", "moveinright", "moveinleft", "moveintop", "moveinbottom",
            "moveoutright", "moveoutleft", "moveouttop", "moveoutbottom",
            "ease", "easeinright", "easeinleft", "easeintop", "easeinbottom",
            "easeoutright", "easeoutleft", "easeouttop", "easeoutbottom",
            "zoomin", "zoomout", "zoominout",
            "vpunch", "hpunch",
            "blinds", "squares",
            "wipeleft", "wiperight", "wipeup", "wipedown",
            "slideleft", "slideright", "slideup", "slidedown",
            "slideawayleft", "slideawayright", "slideawayup", "slideawaydown",
            "pushright", "pushleft", "pushup", "pushdown",
            "irisin", "irisout"
        ]
        self.e_anim = ttk.Combobox(self.win, values=transitions)
        self.e_anim.set(self.data["animation"])
        self.e_anim.pack(fill=tk.X, padx=20)

        tk.Label(self.win, text="Длительность (сек):", **lbl_style).pack(pady=(15, 5))
        self.e_duration = tk.Entry(self.win, bg='#444', fg='white')
        self.e_duration.insert(0, str(self.data["duration"]))
        self.e_duration.pack(fill=tk.X, padx=20)

        tk.Button(self.win, text="💾 Сохранить", command=self.save, bg='#27ae60', fg='white', width=20).pack(side=tk.BOTTOM, pady=20)

    def save(self):
        self.node.title = self.e_title.get()
        self.data["animation"] = self.e_anim.get()
        self.data["target"] = self.e_target.get()
        try:
            self.data["duration"] = float(self.e_duration.get())
        except ValueError:
            self.data["duration"] = 0.5

        self.node.content = json.dumps(self.data, ensure_ascii=False)
        self.node.calculate_size()
        self.callback()
        self.win.destroy()

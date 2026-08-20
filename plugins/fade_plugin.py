import tkinter as tk
from plugin_system import Plugin
import json
import sys

class FadePlugin(Plugin):
    name = "Fade To Black Node"
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
            if node_self.node_type != 'fade_node':
                plugin_self.original_draw(node_self, canvas)
                return

            x, y, w, h = node_self.x, node_self.y, node_self.width, node_self.height

            # Background (Black for fade)
            canvas.create_rectangle(x, y, x+w, y+h, fill='#111111', outline='#ffffff', width=2, tags=("node", node_self.id))
            
            # Header
            header_height = 25
            canvas.create_rectangle(x, y, x+w, y+header_height, fill='#000000', outline="", tags=("node", node_self.id))
            canvas.create_text(x+10, y+12, text="⬛ Затемнение", fill="white", anchor="w", font=("Segoe UI", 9, "bold"), tags=("node", node_self.id))

            # Content
            canvas.create_text(x + w/2, y + header_height + (h - header_height)/2, text="(Уход в черный экран)", fill="#cccccc", font=("Segoe UI", 8), justify="center", tags=("node", node_self.id))

            # Ports
            node_self.draw_input_port(canvas, x, y + h/2)
            node_self.draw_port(canvas, x+w, y + h/2, 0)

        def new_calculate_size(node_self):
            if node_self.node_type != 'fade_node':
                plugin_self.original_calculate_size(node_self)
                return
            node_self.width = 160
            node_self.height = 70

        def new_edit_node(editor_self, node):
            if node.node_type == 'fade_node':
                # No complex edit needed, maybe just title
                pass
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

            self.editor.anim_menu.add_command(label="⬛ Затемнение", command=self.create_fade_node)

        # Export logic
        elif event_type == 'renpy_export_node':
            node = data['node']
            if node.node_type == 'fade_node':
                f = data['file']
                connections = data['connections']
                
                f.write('    scene black with fade\n')
                
                # Пишем переход к следующей ноде
                out_conns = [c for c in connections if c['from'] == node.id]
                if out_conns:
                    target_id = out_conns[0]['to']
                    f.write(f'    jump node_{target_id}\n')
                else:
                    f.write('    return\n')
                
                data['handled'] = True

    def create_fade_node(self):
        self.editor.add_node(
            ntype='fade_node',
            title="Затемнение",
            content="{}"
        )
